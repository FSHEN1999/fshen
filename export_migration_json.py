# -*- coding: utf-8 -*-
"""
数据抽取脚本 - 从数据库抽取迁移数据并生成JSON格式
使用方法：python export_migration_json.py <phone_number>
根据手机号码查询并生成JSON数据
"""
import logging
import json
import pymysql
from pymysql.constants import CLIENT
from typing import Optional, Dict, List, Any

# ================= 配置区域 =================
# 环境选择：sit, uat, preprod, dev
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
log.info(f"当前环境: {ENV}")
log.info(f"数据库主机: {DATABASE_CONFIG[ENV]['host']}")


# ================= 数据库操作类 =================
class DatabaseExecutor:
    """数据库执行器，支持上下文管理"""

    def __init__(self, env: str = ENV):
        self.env = env
        self.conn = None
        self.cursor = None

    def connect(self):
        """建立数据库连接"""
        self.conn = pymysql.connect(**DATABASE_CONFIG[self.env], autocommit=True, client_flag=CLIENT.INTERACTIVE)
        self.cursor = self.conn.cursor()
        return self

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def execute_query(self, sql: str) -> Optional[List[tuple]]:
        """
        执行查询SQL并返回结果

        参数:
            sql: SQL查询语句

        返回:
            查询结果列表，如果执行失败返回None
        """
        try:
            self.cursor.execute(sql)
            return self.cursor.fetchall()
        except Exception as e:
            log.error(f"SQL查询异常: {e}\nSQL: {sql[:200]}...")
            return None

    def execute_query_dict(self, sql: str) -> Optional[List[Dict[str, Any]]]:
        """
        执行查询SQL并返回字典格式结果

        参数:
            sql: SQL查询语句

        返回:
            字典格式的查询结果列表
        """
        try:
            self.cursor.execute(sql)
            columns = [desc[0] for desc in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except Exception as e:
            log.error(f"SQL查询异常: {e}\nSQL: {sql[:200]}...")
            return None


# ================= 数据抽取类 =================
class MigrationDataExporter:
    """迁移数据导出器"""

    def __init__(self, env: str = ENV):
        self.env = env

    def export_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        根据手机号码导出迁移数据

        参数:
            phone_number: 手机号码

        返回:
            JSON格式的数据字典
        """
        with DatabaseExecutor(self.env) as db:
            # Step 1: 查询 merchant_id
            log.info(f"Step 1: 查询手机号 {phone_number} 对应的 merchant_id")
            user_sql = f"SELECT id, merchant_id FROM dpu_users WHERE phone_number = '{phone_number}'"
            user_data = db.execute_query(user_sql)

            if not user_data:
                log.error(f"未找到手机号为 {phone_number} 的用户")
                return None

            merchant_id = user_data[0][1]
            log.info(f"找到 merchant_id: {merchant_id}")

            # Step 2: 查询 entity 获取 brn
            log.info("Step 2: 查询 dpu_entity 获取 business_registration_number")
            entity_sql = f"SELECT business_registration_number FROM dpu_entity WHERE merchant_id = '{merchant_id}'"
            entity_data = db.execute_query(entity_sql)

            brn = None
            if entity_data:
                brn = entity_data[0][0]
                log.info(f"找到 business_registration_number: {brn}")
            else:
                log.warning(f"未找到 merchant_id {merchant_id} 对应的 entity 记录")

            # Step 3: 查询 application 获取 dpu_application_id
            log.info("Step 3: 查询 dpu_application 获取 application_unique_id")
            app_sql = f"SELECT id, application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}'"
            app_data = db.execute_query(app_sql)

            dpu_application_id = None
            if app_data:
                dpu_application_id = app_data[0][1]
                log.info(f"找到 application_unique_id: {dpu_application_id}")
            else:
                log.warning(f"未找到 merchant_id {merchant_id} 对应的 application 记录")

            # Step 4: 查询 drawdowns
            log.info("Step 4: 查询 dpu_drawdown 获取 drawdown 列表")
            drawdown_sql = f"""
                SELECT lender_loan_id, loan_id
                FROM dpu_drawdown
                WHERE merchant_id = '{merchant_id}'
                ORDER BY created_at DESC
            """
            drawdown_data = db.execute_query_dict(drawdown_sql)

            drawdowns = []
            if drawdown_data:
                for dd in drawdown_data:
                    if dd.get('lender_loan_id') and dd.get('loan_id'):
                        drawdowns.append({
                            "drawdown_id": dd['lender_loan_id'],
                            "dpu_loan_id": dd['loan_id']
                        })
                log.info(f"找到 {len(drawdowns)} 笔 drawdown 记录")
            else:
                log.warning(f"未找到 merchant_id {merchant_id} 对应的 drawdown 记录")

            # 组装最终JSON数据
            result = {
                "brn": brn,
                "merchant_id": merchant_id,
                "dpu_application_id": dpu_application_id,
                "drawdowns": drawdowns
            }

            return result

    def export_by_merchant_id(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 merchant_id 直接导出迁移数据

        参数:
            merchant_id: 商户ID

        返回:
            JSON格式的数据字典
        """
        with DatabaseExecutor(self.env) as db:
            log.info(f"根据 merchant_id {merchant_id} 导出数据")

            # Step 1: 查询 entity 获取 brn
            log.info("Step 1: 查询 dpu_entity 获取 business_registration_number")
            entity_sql = f"SELECT business_registration_number FROM dpu_entity WHERE merchant_id = '{merchant_id}'"
            entity_data = db.execute_query(entity_sql)

            brn = None
            if entity_data:
                brn = entity_data[0][0]
                log.info(f"找到 business_registration_number: {brn}")
            else:
                log.warning(f"未找到 merchant_id {merchant_id} 对应的 entity 记录")

            # Step 2: 查询 application 获取 dpu_application_id
            log.info("Step 2: 查询 dpu_application 获取 application_unique_id")
            app_sql = f"SELECT id, application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}'"
            app_data = db.execute_query(app_sql)

            dpu_application_id = None
            if app_data:
                dpu_application_id = app_data[0][1]
                log.info(f"找到 application_unique_id: {dpu_application_id}")
            else:
                log.warning(f"未找到 merchant_id {merchant_id} 对应的 application 记录")

            # Step 3: 查询 drawdowns
            log.info("Step 3: 查询 dpu_drawdown 获取 drawdown 列表")
            drawdown_sql = f"""
                SELECT lender_loan_id, loan_id
                FROM dpu_drawdown
                WHERE merchant_id = '{merchant_id}'
                ORDER BY created_at DESC
            """
            drawdown_data = db.execute_query_dict(drawdown_sql)

            drawdowns = []
            if drawdown_data:
                for dd in drawdown_data:
                    if dd.get('lender_loan_id') and dd.get('loan_id'):
                        drawdowns.append({
                            "drawdown_id": dd['lender_loan_id'],
                            "dpu_loan_id": dd['loan_id']
                        })
                log.info(f"找到 {len(drawdowns)} 笔 drawdown 记录")
            else:
                log.warning(f"未找到 merchant_id {merchant_id} 对应的 drawdown 记录")

            # 组装最终JSON数据
            result = {
                "brn": brn,
                "merchant_id": merchant_id,
                "dpu_application_id": dpu_application_id,
                "drawdowns": drawdowns
            }

            return result

    def export_batch_by_phone(self, phone_numbers: List[str]) -> List[Dict[str, Any]]:
        """
        批量导出多个手机号码的迁移数据

        参数:
            phone_numbers: 手机号码列表

        返回:
            JSON格式的数据字典列表
        """
        results = []
        for phone in phone_numbers:
            log.info(f"\n{'='*50}")
            log.info(f"处理手机号: {phone}")
            log.info(f"{'='*50}")
            data = self.export_by_phone(phone)
            if data:
                results.append(data)
        return results

    def export_all(self) -> List[Dict[str, Any]]:
        """
        导出所有用户的迁移数据

        返回:
            JSON格式的数据字典列表
        """
        with DatabaseExecutor(self.env) as db:
            log.info("查询所有用户数据")
            sql = "SELECT DISTINCT phone_number FROM dpu_users ORDER BY phone_number"
            users = db.execute_query(sql)

            phone_numbers = [u[0] for u in users] if users else []
            log.info(f"共找到 {len(phone_numbers)} 个用户")

            return self.export_batch_by_phone(phone_numbers)


# ================= 主函数 =================
def print_split_jsons(phone_number: str):
    """
    根据手机号查询数据，每笔 drawdown 单独打印一段 JSON

    参数:
        phone_number: 手机号码
    """
    with DatabaseExecutor(ENV) as db:
        # Step 1: 查询 merchant_id
        log.info(f"查询手机号: {phone_number}")
        user_sql = f"SELECT id, merchant_id FROM dpu_users WHERE phone_number = '{phone_number}'"
        user_data = db.execute_query(user_sql)

        if not user_data:
            log.error(f"未找到手机号为 {phone_number} 的用户")
            return

        merchant_id = user_data[0][1]
        log.info(f"找到 merchant_id: {merchant_id}")

        # Step 2: 查询 entity 获取 brn
        entity_sql = f"SELECT business_registration_number FROM dpu_entity WHERE merchant_id = '{merchant_id}'"
        entity_data = db.execute_query(entity_sql)
        brn = entity_data[0][0] if entity_data else None

        # Step 3: 查询 application 获取 dpu_application_id
        app_sql = f"SELECT id, application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}'"
        app_data = db.execute_query(app_sql)
        dpu_application_id = app_data[0][1] if app_data else None

        # Step 4: 查询 drawdowns
        drawdown_sql = f"""
            SELECT lender_loan_id, loan_id
            FROM dpu_drawdown
            WHERE merchant_id = '{merchant_id}'
            ORDER BY created_at DESC
        """
        drawdown_data = db.execute_query(drawdown_sql)

        if not drawdown_data:
            log.warning(f"未找到 drawdown 记录")
            return

        log.info(f"找到 {len(drawdown_data)} 笔 drawdown 记录")
        print("\n" + "=" * 60)

        # 每笔 drawdown 单独打印一段 JSON
        for idx, dd in enumerate(drawdown_data, 1):
            drawdown_id = dd[0]
            dpu_loan_id = dd[1]

            result = {
                "brn": brn,
                "merchant_id": merchant_id,
                "dpu_application_id": dpu_application_id,
                "drawdowns": [
                    {
                        "drawdown_id": drawdown_id,
                        "dpu_loan_id": dpu_loan_id
                    }
                ]
            }

            print(f"\n第 {idx} 笔 JSON:")
            print("-" * 40)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("-" * 40)

        print("\n" + "=" * 60)
        log.info(f"共输出 {len(drawdown_data)} 段 JSON")


def main():
    """主函数，交互式输入手机号并打印JSON"""
    import sys

    # 如果有命令行参数，使用参数作为手机号
    if len(sys.argv) >= 2 and not sys.argv[1].startswith('--'):
        phone_number = sys.argv[1]
        print_split_jsons(phone_number)
    else:
        # 交互式输入
        log.info(f"当前环境: {ENV}")
        log.info(f"数据库主机: {DATABASE_CONFIG[ENV]['host']}")

        while True:
            print("\n" + "=" * 60)
            phone_number = input("请输入手机号 (输入 'q' 退出): ").strip()

            if phone_number.lower() == 'q':
                log.info("退出程序")
                break

            if not phone_number:
                log.warning("手机号不能为空，请重新输入")
                continue

            print_split_jsons(phone_number)


if __name__ == '__main__':
    main()