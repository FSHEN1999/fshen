# -*- coding: utf-8 -*-
"""
回滚脚本 - 删除迁移数据（匹配 migration_test_FP_json用户1-无法支持多店铺.py）
使用方法：python rollback_migration.py <phone_number> [env]
默认环境: preprod

支持的回滚操作：
1. 删除 dpu_repayment（还款记录）
2. 删除 dpu_drawdown（放款记录）
3. 删除 dpu_limit_application_account
4. 删除 dpu_limit_application
5. 删除 dpu_credit_offer
6. 删除 dpu_notify_event（FP_FIRST_CREDIT_MODEL_START, FP_FIRST_KYC_START）
7. 删除 dpu_notify_event_dependency（4条记录）
8. 删除 dpu_nature_person_documents
9. 删除 dpu_nature_person（股东信息）
10. 删除 dpu_bank_account
11. 回滚 dpu_application 状态
12. 删除 dpu_auth_token (PSP)
13. 回滚 dpu_merchant_account_limit
14. 回滚 dpu_merchants_limit 额度
15. 回滚 3PL merchant_account_id（清空）
16. 删除 dpu_entity
"""
import logging
import pymysql
import sys
from pymysql.constants import CLIENT

# ================= 配置区域 =================
# 默认环境：sit, uat, preprod, dev
ENV = "preprod"

# 多环境数据库配置
DATABASE_CONFIG = {
    "sit": {
        "host": "aurora-dpu-sit.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_sit",
        "password": "20250818dpu_sit",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
        "connect_timeout": 1500,
        "read_timeout": 15,
    },
    "uat": {
        "host": "aurora-dpu-uat.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_uat",
        "password": "20250818dpu_uat",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
        "connect_timeout": 1500,
        "read_timeout": 15,
    },
    "preprod": {
        "host": "43.199.241.190",
        "user": "dpu_preprod",
        "password": "OWBSNfx8cC5c#Or0",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
        "connect_timeout": 1500,
        "read_timeout": 15,
    },
    "dev": {
        "host": "localhost",
        "user": "root",
        "password": "password",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
        "connect_timeout": 1500,
        "read_timeout": 15,
    },
}

# 初始化日志
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


class ExecuteSql:
    def __init__(self, env=ENV):
        self.env = env
        self.conn = pymysql.connect(**DATABASE_CONFIG[env], autocommit=True, client_flag=CLIENT.INTERACTIVE)
        self.cursor = self.conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def execute_sql(self, sql):
        result = {'success': False, 'data': None, 'affected_rows': 0, 'error': None, 'sql': sql}
        try:
            rows = self.cursor.execute(sql)
            result['affected_rows'] = rows
            if sql.strip().lower().startswith("select"):
                result['data'] = self.cursor.fetchall()
            result['success'] = True
        except Exception as e:
            log.error(f"SQL执行异常: {e}")
            result['error'] = str(e)
        return result


def check_and_execute(executor, sql, step_name):
    log.info(f"执行: {step_name}")
    res = executor.execute_sql(sql)
    if not res['success']:
        log.warning(f"{step_name} 失败（可能不存在）: {res['error']}")
    else:
        log.info(f"{step_name} 成功，影响行数: {res['affected_rows']}")
    return res


def rollback(phone_number, env=ENV):
    log.info(f"\n=== 开始回滚，手机号: {phone_number}，环境: {env} ===")

    with ExecuteSql(env=env) as executor:
        # 查询 merchant_id
        res = executor.execute_sql(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}'")
        if not res['data']:
            log.error(f"未找到手机号为 {phone_number} 的用户")
            return
        merchant_id = res['data'][0][0]
        log.info(f"merchant_id: {merchant_id}")

        # 查询 SP (Selling Partner) 的 merchant_account_id
        res = executor.execute_sql(f"SELECT merchant_account_id FROM dpu_auth_token WHERE merchant_id='{merchant_id}' AND authorization_party='SP' LIMIT 1")
        if not res['data']:
            log.warning(f"未找到 SP merchant_account_id")
            merchant_account_id = None
        else:
            merchant_account_id = res['data'][0][0]
            log.info(f"SP merchant_account_id: {merchant_account_id}")

        # 查询 entity_id
        res = executor.execute_sql(f"SELECT id FROM dpu_entity WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1")
        entity_id = res['data'][0][0] if res['data'] else None
        if entity_id:
            log.info(f"entity_id: {entity_id}")

        # 查询 application_id 和 application_unique_id
        res = executor.execute_sql(f"SELECT application_id, application_unique_id, application_status FROM dpu_application WHERE merchant_id='{merchant_id}'")
        application_id = res['data'][0][0] if res['data'] else None
        application_unique_id = res['data'][0][1] if res['data'] else None
        application_status = res['data'][0][2] if res['data'] else None
        if application_id:
            log.info(f"application_id: {application_id}, application_unique_id: {application_unique_id}, application_status: {application_status}")

        log.info("\n" + "="*60)
        log.info("开始删除数据（按依赖关系逆序）")
        log.info("="*60)

        # 1. 删除 repayment（先删除还款记录）
        res_loan_ids = executor.execute_sql(f"SELECT loan_id FROM dpu_drawdown WHERE merchant_id='{merchant_id}' AND lender_code='FUNDPARK'")
        if res_loan_ids['data']:
            loan_ids = [row[0] for row in res_loan_ids['data']]
            for loan_id in loan_ids:
                check_and_execute(executor,
                    f"DELETE FROM dpu_repayment WHERE dpu_loan_id='{loan_id}'",
                    f"删除 dpu_repayment (loan_id: {loan_id})")

        # 2. 删除 drawdown（放款记录）
        check_and_execute(executor,
            f"DELETE FROM dpu_drawdown WHERE merchant_id='{merchant_id}' AND lender_code='FUNDPARK'",
            "删除 dpu_drawdown")

        # 3. 删除 limit_application_account
        check_and_execute(executor,
            f"DELETE FROM dpu_limit_application_account WHERE merchant_id='{merchant_id}'",
            "删除 dpu_limit_application_account")

        # 4. 删除 limit_application
        check_and_execute(executor,
            f"DELETE FROM dpu_limit_application WHERE merchant_id='{merchant_id}'",
            "删除 dpu_limit_application")

        # 5. 删除 credit_offer
        check_and_execute(executor,
            f"DELETE FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' AND lender_code='FUNDPARK'",
            "删除 dpu_credit_offer")

        # 6. 删除 notify_event（FP_FIRST_CREDIT_MODEL_START, FP_FIRST_KYC_START）
        if application_unique_id:
            event_types = [
                "FP_FIRST_CREDIT_MODEL_START",
                "FP_FIRST_KYC_START",
            ]
            for event_type in event_types:
                check_and_execute(executor,
                    f"DELETE FROM dpu_notify_event WHERE biz_id='{application_unique_id}' AND event_type='{event_type}'",
                    f"删除 dpu_notify_event ({event_type})")

        # 7. 删除 notify_event_dependency（4条记录）
        if application_unique_id:
            # 迁移脚本插入的4条 dependency 记录
            dependency_configs = [
                ('FP_FIRST_KYC_START', 'AMAZON_3PL_SP_DATA_ALIGNMENT'),
                ('FP_FIRST_KYC_START', 'OWS_SANCTIONS_SCREENING'),
                ('FP_FIRST_CREDIT_MODEL_START', 'AMAZON_3PL_SP_DATA_ALIGNMENT'),
                ('FP_FIRST_CREDIT_MODEL_START', 'OWS_SANCTIONS_SCREENING'),
            ]
            for event_type, dependency_type in dependency_configs:
                check_and_execute(executor,
                    f"DELETE FROM dpu_notify_event_dependency WHERE biz_id='{application_unique_id}' AND event_type='{event_type}' AND dependency_type='{dependency_type}'",
                    f"删除 dpu_notify_event_dependency ({event_type}/{dependency_type})")

        # 8. 删除股东身份证文档
        if entity_id:
            check_and_execute(executor,
                f"DELETE FROM dpu_nature_person_documents WHERE entity_id='{entity_id}' AND merchant_id='{merchant_id}'",
                "删除 dpu_nature_person_documents")

        # 9. 删除股东信息
        if entity_id:
            check_and_execute(executor,
                f"DELETE FROM dpu_nature_person WHERE entity_id='{entity_id}' AND merchant_id='{merchant_id}' AND nature_person_type='SHAREHOLDER'",
                "删除 dpu_nature_person (股东信息)")

        # 10. 删除银行账户
        check_and_execute(executor,
            f"DELETE FROM dpu_bank_account WHERE merchant_id='{merchant_id}'",
            "删除 dpu_bank_account")

        # 11. 回滚 application 状态（清空 entity_id，状态改为 INITIAL）
        check_and_execute(executor,
            f"UPDATE dpu_application SET application_status='INITIAL', entity_id=NULL WHERE merchant_id='{merchant_id}'",
            "回滚 dpu_application 状态（清空 entity_id）")

        # 12. 删除 PSP 记录
        check_and_execute(executor,
            f"DELETE FROM dpu_auth_token WHERE merchant_id='{merchant_id}' AND authorization_party='PSP'",
            "删除 dpu_auth_token (PSP)")

        # 13. 回滚 merchant_account_limit（恢复迁移前的状态）
        check_and_execute(executor,
            f"UPDATE dpu_merchant_account_limit SET psp_status='INITIAL', platform_sync_status='PENDING' WHERE merchant_id='{merchant_id}'",
            "回滚 dpu_merchant_account_limit")

        # 14. 回滚 dpu_merchants_limit 额度（清空所有迁移设置的额度）
        check_and_execute(executor,
            f"""UPDATE dpu_merchants_limit SET
                `activated_limit` = NULL,
                `activated_limit_update_at` = NULL,
                `approved_limit` = NULL,
                `approved_limit_update_at` = NULL,
                `available_limit` = NULL,
                `available_limit_update_at` = NULL,
                `signed_limit` = NULL,
                `signed_limit_update_at` = NULL,
                `underwritten_limit` = NULL,
                `underwritten_limit_update_at` = NULL,
                `margin_rate` = NULL,
                `utilization_limit` = NULL,
                `utilization_limit_update_at` = NULL
                WHERE merchant_id='{merchant_id}'""",
            "回滚 dpu_merchants_limit 额度")

        # 15. 回滚 3PL merchant_account_id（清空）
        check_and_execute(executor,
            f"UPDATE dpu_auth_token SET merchant_account_id=NULL WHERE authorization_party='3PL' AND merchant_id='{merchant_id}'",
            "回滚 dpu_auth_token (3PL merchant_account_id)")

        check_and_execute(executor,
            f"UPDATE dpu_shops SET merchant_account_id=NULL WHERE emarketplace_data_type='3PL' AND merchant_id='{merchant_id}'",
            "回滚 dpu_shops (3PL merchant_account_id)")

        # 16. 删除 Entity 记录（迁移脚本 Step 9 插入/更新的）
        if entity_id:
            # 检查是否有其他记录依赖此 entity_id
            res_check = executor.execute_sql(
                f"SELECT COUNT(*) FROM dpu_application WHERE entity_id='{entity_id}'"
            )
            has_dependency = res_check['data'] and res_check['data'][0][0] > 0

            if not has_dependency:
                check_and_execute(executor,
                    f"DELETE FROM dpu_entity WHERE id='{entity_id}' AND merchant_id='{merchant_id}'",
                    "删除 dpu_entity")
            else:
                log.warning("dpu_entity 存在其他依赖，跳过删除")

        log.info("\n" + "="*60)
        log.info("回滚完成！")
        log.info("="*60)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("使用方法: python rollback_migration.py <phone_number> [env]")
        print("环境选项: sit, uat, preprod, dev (默认: preprod)")
        print("示例: python rollback_migration.py 18617143306 uat")
        sys.exit(1)

    phone_number = sys.argv[1]
    env = sys.argv[2] if len(sys.argv) >= 3 else "preprod"

    # 验证环境参数
    if env not in DATABASE_CONFIG:
        print(f"错误: 无效的环境参数 '{env}'")
        print(f"支持的环境: {', '.join(DATABASE_CONFIG.keys())}")
        sys.exit(1)

    rollback(phone_number, env)