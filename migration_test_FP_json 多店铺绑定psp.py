# -*- coding: utf-8 -*-
"""
多店铺PSP绑定脚本
功能：插入PSP记录到auto token表，并更新dpu_merchant_account_limit表的psp_status状态
使用方法：python migration_test_FP_json 多店铺绑定psp.py <file_path>
支持 .json 和 .csv 格式文件
"""
import logging
import csv
import json
import random
import string
from datetime import datetime
import pymysql
from pymysql.constants import CLIENT

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
    "reg": {
        "host": "aurora-dpu-reg.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_reg",
        "password": "r4asUYBX3R6LNdp",
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
            log.error(f"SQL执行异常: {e}\nSQL: {sql[:100]}...")
            result['error'] = str(e)
        return result


def generate_random_str(k=32):
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=k))
  

def build_insert_sql(table, fields, ignore=False):
    """
    构建 INSERT INTO ... SET 格式的SQL语句，字段名和值在同一行显示

    参数:
        table: 表名
        fields: 字典，键为字段名，值为字段值
        ignore: 是否使用 INSERT IGNORE

    返回:
        SQL字符串
    """
    ignore_str = "IGNORE " if ignore else ""
    set_clauses = []
    for field, value in fields.items():
        if value is None:
            set_clauses.append(f"    `{field}` = NULL")
        elif isinstance(value, str) and value.startswith("X'") and value.endswith("'"):
            # 十六进制值
            set_clauses.append(f"    `{field}` = {value}")
        elif isinstance(value, (int, float)):
            # 数字值不需要引号
            set_clauses.append(f"    `{field}` = {value}")
        else:
            # 字符串值需要转义和引号
            escaped = str(value).replace("'", "''")
            set_clauses.append(f"    `{field}` = '{escaped}'")

    return f"INSERT {ignore_str}INTO `{table}` SET\n" + ",\n".join(set_clauses)


def check_and_execute(executor, sql, step_name):
    """执行SQL并记录日志"""
    log.info(f"执行: {step_name}")
    res = executor.execute_sql(sql)
    if not res['success']:
        log.error(f"{step_name} 失败，终止当前行处理。错误: {res['error']}")
        raise Exception(f"SQL Failed: {step_name}")
    log.info(f"{step_name} 成功")
    return res


# ================= 主逻辑 =================
def run_application(file_path):
    log.info(f"\n=== 开始执行多店铺PSP绑定 ===")

    try:
        # 判断文件类型，支持 CSV 和 JSON
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data_list = json.load(jsonfile)
                if not isinstance(data_list, list):
                    data_list = [data_list]  # 如果是单个对象，转为列表
        else:
            # 兼容原有的 CSV 格式
            with open(file_path, 'r', newline='', encoding='gbk') as csvfile:
                reader = csv.DictReader(csvfile)
                data_list = list(reader)

        with ExecuteSql() as executor:
            for row_idx, data in enumerate(data_list):
                log.info(f"\n{'='*20} 正在处理第 {row_idx+1} 条数据 {'='*20}")

                # ================== 数据提取 ==================
                if isinstance(data, dict) and 'amzs' in data:
                    # JSON 格式数据提取
                    # 从application对象中提取mobile_phone
                    application = data.get('application', {})
                    phone_number = application.get('mobile_phone')
                    amzs = data.get('amzs', [])
                    # 支持多店铺（多个amz记录）
                    amz_list = amzs if amzs else []
                    # 提取limit对象（用于Step 6）
                    limit_data = data.get('limit', {})

                else:
                    # CSV 格式数据提取（保持原有逻辑）
                    phone_number = data.get('phone_number')
                    # CSV格式单店铺
                    amz_list = [{
                        'amazon_seller_id': data.get('amazon_seller_id'),
                        'psp_id': data.get('psp_id'),
                        'psp_name': data.get('psp_name'),
                    }] if data.get('amazon_seller_id') else []
                    # CSV格式无limit数据，使用空字典
                    limit_data = {}

                if not phone_number:
                    log.warning(f"未找到手机号，跳过此行")
                    continue

                if not amz_list:
                    log.warning(f"未找到Amazon店铺信息，跳过此行")
                    continue

                # ================== Step 1: 查询用户 ==================
                res1 = check_and_execute(
                    executor,
                    f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}'",
                    "Step 1: 查询用户"
                )
                if not res1['data']:
                    log.warning(f"未找到手机号为 {phone_number} 的用户，跳过此行")
                    continue
                merchant_id = res1['data'][0][0]
                log.info(f"Step 1: merchant_id 为 {merchant_id}")

                # ================== 遍历每个店铺进行PSP绑定 ==================
                for shop_idx, amz in enumerate(amz_list):
                    log.info(f"\n--- 处理第 {shop_idx+1} 个店铺 ---")

                    amazon_seller_id = amz.get('amazon_seller_id')
                    psp_id = amz.get('psp_id')
                    psp_name = amz.get('psp_name')

                    if not amazon_seller_id:
                        log.warning(f"第 {shop_idx+1} 个店铺缺少 amazon_seller_id，跳过")
                        continue

                    # ================== Step 2: 查询AMZ Token ==================
                    res01 = check_and_execute(
                        executor,
                        f"SELECT merchant_account_id FROM dpu_auth_token WHERE authorization_id='{amazon_seller_id}'",
                        f"Step 2.{shop_idx+1}: 查询AMZ Token"
                    )
                    if not res01['data']:
                        log.warning(f"未找到AMZ Seller ID 为 {amazon_seller_id} 的AMZ Token，跳过此店铺")
                        continue
                    merchant_account_id = res01['data'][0][0]
                    log.info(f"Step 2.{shop_idx+1}: merchant_account_id 为 {merchant_account_id}")

                    # ================== Step 3: 插入PSP记录到auto token表 ==================
                    if psp_id:
                        # 先查询PSP记录是否已存在
                        res_psp_check = executor.execute_sql(
                            f"""SELECT id FROM dpu_auth_token
                                WHERE merchant_account_id='{merchant_account_id}'
                                AND authorization_id='{psp_id}'
                                AND authorization_party='PSP'"""
                        )
                        if res_psp_check['data']:
                            log.info(f"Step 3.{shop_idx+1}: PSP记录已存在 (merchant_account_id={merchant_account_id}, authorization_id={psp_id})，跳过插入")
                        else:
                            insert_psp_id = generate_random_str()
                            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            sql_psp = build_insert_sql('dpu_auth_token', {
                                'authorization_id': psp_id,
                                'authorization_party': 'PSP',
                                'consented_at': current_time,
                                'create_by': 'SYSTEM',
                                'created_at': current_time,
                                'id': insert_psp_id,
                                'last_update_on': "X'0a0a83ee'",
                                'merchant_account_id': merchant_account_id,
                                'merchant_id': merchant_id,
                                'name': psp_name,
                                'status': 'ACTIVE',
                                'update_by': 'SYSTEM',
                                'updated_at': current_time,
                            })
                            check_and_execute(executor, sql_psp, f"Step 3.{shop_idx+1}: 向dpu_auth_token插入PSP记录")
                            log.info(f"Step 3.{shop_idx+1}: 成功插入PSP记录 (psp_id={psp_id})")
                    else:
                        log.info(f"Step 3.{shop_idx+1}: psp_id 为空，跳过PSP记录插入")

                    # ================== Step 5: 插入dpu_limit_application表 ==================
                    # # 生成必要的ID
                    # # id格式：32位小写十六进制字符串
                    # limit_application_id = ''.join(random.choices('0123456789abcdef', k=32))
                    # # limit_application_unique_id格式：EFAL前缀 + 17位数字
                    # limit_application_unique_id = 'EFAL' + ''.join(random.choices(string.digits, k=17))
                    # # 从JSON的limit对象中获取underwrittenAmount，如果没有则使用默认值
                    # underwrittenAmount = limit_data.get('underwritten_amount', '240000.00')

                    # # 直接插入dpu_limit_application表
                    # current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # sql_limit_application = build_insert_sql('dpu_limit_application', {
                    #     'activated_limit': None,
                    #     'available_limit': None,
                    #     'create_by': 'SYSTEM',
                    #     'created_at': current_time,
                    #     'currency': 'USD',
                    #     'id': limit_application_id,
                    #     'last_update_on': "X'0a0a83ee'",
                    #     'lender_code': 'FUNDPARK',
                    #     'limit_application_unique_id': limit_application_unique_id,
                    #     'merchant_id': merchant_id,
                    #     'product': 'LINE_OF_CREDIT',
                    #     'status': 'RECEIVED',
                    #     'underwritten_limit': underwrittenAmount,
                    #     'update_by': '5058000001',
                    #     'updated_at': current_time,
                    # })
                    # check_and_execute(executor, sql_limit_application, f"Step 5.{shop_idx+1}: 向dpu_limit_application插入记录")
                    # log.info(f"Step 5.{shop_idx+1}: 成功插入dpu_limit_application记录")

                    # ================== Step 6: 插入dpu_limit_application_account表 ==================
                    # 从dpu_limit_application表查询获取limit_application_unique_id和limit_application_id
                    res_la = executor.execute_sql(
                        f"""SELECT id, limit_application_unique_id, underwritten_limit
                            FROM dpu_limit_application
                            WHERE merchant_id='{merchant_id}'"""
                    )
                    if res_la['data']:
                        limit_application_id = res_la['data'][0][0]
                        limit_application_unique_id = res_la['data'][0][1]
                        underwrittenAmount = res_la['data'][0][2] or limit_data.get('underwritten_amount', '240000.00')
                        log.info(f"Step 6.{shop_idx+1}: 从dpu_limit_application获取到 limit_application_unique_id={limit_application_unique_id}")
                    else:
                        log.warning(f"Step 6.{shop_idx+1}: 未找到merchant_id={merchant_id}的dpu_limit_application记录，跳过此店铺")
                        continue

                    random_id_LAA = ''.join(random.choices('0123456789abcdef', k=32))
                    # 从JSON的limit对象中获取limit值，如果没有则使用默认值
                    approvedLimit = limit_data.get('approved_limit', '240000.00')
                    signedLimit = limit_data.get('signed_limit', '240000.00')
                    activatedLimit = limit_data.get('activate_limit', None)

                    # 检查是否已存在记录
                    laa_check_sql = f"SELECT * FROM dpu_limit_application_account WHERE merchant_account_id='{merchant_account_id}'"
                    res_laa_check = executor.execute_sql(laa_check_sql)
                    if res_laa_check['data']:
                        log.info(f"Step 6.{shop_idx+1}: dpu_limit_application_account记录已存在，跳过插入")
                    else:
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        sql_dpu_limit_application_account = build_insert_sql('dpu_limit_application_account', {
                            'activated_limit': activatedLimit,
                            'approved_limit': approvedLimit,
                            'authorization_id': amazon_seller_id,
                            'create_by': 'SYSTEM',
                            'created_at': current_time,
                            'currency': 'USD',
                            'frozen_limit': None,
                            'id': random_id_LAA,
                            'indicative_limit': '240000.00',
                            'last_update_on': "X'0a0a83ee'",
                            'limit_application_id': limit_application_id,
                            'limit_application_unique_id': limit_application_unique_id,
                            'merchant_account_id': merchant_account_id,
                            'merchant_id': merchant_id,
                            'psp_status': 'INITIAL',
                            'signed_limit': signedLimit,
                            'underwritten_limit': underwrittenAmount,
                            'update_by': 'SYSTEM',
                            'updated_at': current_time,
                            'utilization_limit': None,
                        })
                        check_and_execute(executor, sql_dpu_limit_application_account, f"Step 6.{shop_idx+1}: 向dpu_limit_application_account插入记录")
                        log.info(f"Step 6.{shop_idx+1}: 成功插入dpu_limit_application_account记录")

                # ================== Step 4: 更新dpu_merchant_account_limit的psp_status + 额度拆分 ==================
                # 注意：此步骤在所有店铺处理完后统一执行一次
                log.info(f"\n--- Step 4: 统一更新psp_status并执行额度拆分 ---")
                res_mal_check = executor.execute_sql(
                    f"""SELECT merchant_account_id, psp_status
                        FROM dpu_merchant_account_limit
                        WHERE merchant_id='{merchant_id}'"""
                )
                if res_mal_check['data']:
                    # 计算需要拆分的记录总数
                    total_records = len(res_mal_check['data'])
                    log.info(f"Step 4: 检测到 {total_records} 条merchant_account_limit记录，额度将除以 {total_records}")

                    # 从JSON的limit对象获取总额度
                    total_underwritten = float(limit_data.get('underwritten_amount', '240000.00'))
                    total_approved = float(limit_data.get('approved_limit', '240000.00'))
                    total_signed = float(limit_data.get('signed_limit', '240000.00'))
                    total_activated = float(limit_data.get('activate_limit', '0'))

                    # 计算available_limit：取approved_limit和activate_limit中的较小值
                    total_available = min(total_approved, total_activated)

                    # 计算每条记录分配的额度（保留2位小数）
                    split_underwritten = f"{total_underwritten / total_records:.2f}"
                    split_approved = f"{total_approved / total_records:.2f}"
                    split_signed = f"{total_signed / total_records:.2f}"
                    split_activated = f"{total_activated / total_records:.2f}" if total_activated else 'NULL'
                    split_available = f"{total_available / total_records:.2f}" if total_available else 'NULL'

                    log.info(f"Step 4: 从JSON获取总额度并平均分配:")
                    log.info(f"  underwritten_amount: {total_underwritten} → 每条 {split_underwritten}")
                    log.info(f"  approved_limit: {total_approved} → 每条 {split_approved}")
                    log.info(f"  signed_limit: {total_signed} → 每条 {split_signed}")
                    log.info(f"  activate_limit: {total_activated} → 每条 {split_activated}")
                    log.info(f"  available_limit: {total_available} → 每条 {split_available}")

                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # 遍历每条记录进行更新
                    for record in res_mal_check['data']:
                        record_merchant_account_id = record[0]
                        current_psp_status = record[1]

                        if current_psp_status == 'SUCCESS':
                            log.info(f"Step 4: merchant_account_id={record_merchant_account_id} 的 psp_status 已是 SUCCESS，仅更新limit")
                        else:
                            log.info(f"Step 4: merchant_account_id={record_merchant_account_id} 的 psp_status 非SUCCESS，更新psp_status和limit")

                        sql_mal = f"""UPDATE `dpu_merchant_account_limit`
                                    SET
                                        `created_at` = '{current_time}',
                                        `currency` = 'USD',
                                        `finance_product` = 'LINE_OF_CREDIT',
                                        `indicative_limit` = '240000.00',
                                        `indicative_limit_update_at` = '{current_time}',
                                        `lender_code` = 'FUNDPARK',
                                        `merchant_account_id` = '{record_merchant_account_id}',
                                        `platform_sync_status` = 'PENDING',
                                        `psp_status` = 'SUCCESS',
                                        `updated_at` = '{current_time}',
                                        `underwritten_limit` = {split_underwritten},
                                        `underwritten_limit_update_at` = '{current_time}',
                                        `approved_limit` = {split_approved},
                                        `approved_limit_update_at` = '{current_time}',
                                        `signed_limit` = {split_signed},
                                        `signed_limit_update_at` = '{current_time}',
                                        `activated_limit` = {split_activated},
                                        `activated_limit_update_at` = '{current_time}',
                                        `available_limit` = {split_available},
                                        `available_limit_update_at` = '{current_time}'
                                    WHERE `merchant_account_id` = '{record_merchant_account_id}';"""
                        check_and_execute(executor, sql_mal, f"Step 4: 更新Merchant Account Limit（psp_status + 额度拆分）")
                        log.info(f"Step 4: 成功更新 merchant_account_id={record_merchant_account_id} 的 psp_status 为 SUCCESS 并完成额度拆分")
                    log.info(f"Step 4: 额度拆分完成，共更新 {total_records} 条记录")
                else:
                    log.warning(f"Step 4: 未找到merchant_id={merchant_id}的记录")

                log.info(f"\n{'='*20} 第 {row_idx+1} 条数据处理完成 {'='*20}\n")

    except Exception as e:
        log.error(f"处理数据时出错: {e}")
        raise


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        # 默认使用 migration_data多店铺.json
        file_path = 'migration_data多店铺.json'
    else:
        file_path = sys.argv[1]
    run_application(file_path)
