# -*- coding: utf-8 -*-
"""
迁移测试脚本 - 支持 JSON 格式导入
使用方法：python migration_test_FP_json.py <file_path>
支持 .json 和 .csv 格式文件
"""
import logging
import time
import uuid
import random
import string
import csv
import json
import pymysql
import secrets
from pymysql.constants import CLIENT
from datetime import datetime, timedelta

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
    return ''.join(random.choices(string.ascii_letters + string.digits, k=k))


def generate_random_hex(k=32):
    return ''.join(random.choices('0123456789abcdef', k=k))


def escape_sql(value):
    """转义 SQL 字符串中的单引号"""
    if value is None:
        return ''
    return str(value).replace("'", "''")


def check_and_execute(executor, sql, step_name):
    log.info(f"执行: {step_name}")
    res = executor.execute_sql(sql)
    if not res['success']:
        log.error(f"{step_name} 失败，终止当前行处理。错误: {res['error']}")
        raise Exception(f"SQL Failed: {step_name}")
    log.info(f"{step_name} 成功")
    return res


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


# ================= 主逻辑 =================
def run_application(file_path):
    log.info(f"\n=== 开始执行run_application ===")
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
            # 跳过创建回滚备份表（无权限）
            pass

            for row_idx, data in enumerate(data_list):
                log.info(f"\n{'='*20} 正在处理第 {row_idx+1} 条数据 {'='*20}")

                # ================== 数据提取 ==================
                if isinstance(data, dict) and 'brn' in data:
                    # JSON 格式数据提取
                    phone_number = data.get('application', {}).get('mobile_phone')
                    business_registration_number = data.get('brn')
                    company_registration_date = data.get('application', {}).get('company_registration_date')
                    company_eng_name = data.get('application', {}).get('company_english_name')
                    amzs = data.get('amzs', [])
                    amazon_seller_id = amzs[0].get('amazon_seller_id') if amzs else None
                    psp_id = amzs[0].get('psp_id') if amzs else None
                    psp_name = amzs[0].get('psp_name') if amzs else None
                    Contact_User_email = data.get('application', {}).get('contact_user_email')

                    # 董事信息
                    directors = data.get('application', {}).get('directors', [])
                    Director_1_en_Name = directors[0].get('full_name_en') if directors else None
                    Director_1_cn_Name = directors[0].get('full_name_cn') if directors else None
                    Director_1_birth_date = directors[0].get('birthday') if directors else None

                    # 股东信息（动态数组）
                    shareholders = data.get('application', {}).get('shareholders', [])

                    # 银行信息
                    banks = data.get('limit', {}).get('banks', [])
                    Bank_account_Number = banks[0].get('bank_account_number') if banks else None
                    Bank_account = banks[0].get('bank_name') if banks else None
                    Bank_account_Number_address = banks[0].get('bank_address') if banks else None
                    Bank_account_Name = banks[0].get('bank_account_name') if banks else None
                    Swift_Code = banks[0].get('swift_code') if banks else None
                    Branch_Code = banks[0].get('branch_code') if banks else None

                    # 额度信息
                    limit = data.get('limit', {})
                    underwrittenAmount = limit.get('underwritten_amount', '0')
                    signedLimit = limit.get('signed_limit', '0')
                    approvedLimit = limit.get('approved_limit', '0')
                    activate_limit = limit.get('activate_limit', '0')
                    approved_limit_num = float(approvedLimit) if str(approvedLimit).strip() else 0
                    activate_limit_num = float(activate_limit) if str(activate_limit).strip() else 0
                    available_limit = min(approved_limit_num, activate_limit_num)
                    baseRate = limit.get('base_rate', '0')
                    marginRate = limit.get('margin_rate', '0')
                    offerStartDate = limit.get('offer_start_date')
                    offerEndDate = limit.get('offer_end_date')

                    # Lender 信息
                    lender_credit_id = data.get('lender_credit_id', '')
                    lender_company_id = data.get('application', {}).get('lender_company_id', '')
                    lender_approved_offer_id = data.get('lender_approved_offer_id', '')

                    # Drawdown 信息（动态数组）
                    drawdowns = data.get('drawdowns', [])

                else:
                    # CSV 格式数据提取（保持原有逻辑）
                    phone_number = data.get('phone_number')
                    business_registration_number = data.get('business_registration_number')
                    company_registration_date = data.get('Company Registration Date')
                    company_eng_name = data.get('company_eng_name')
                    amazon_seller_id = data.get('amazon_seller_id')
                    psp_id = data.get('psp_id')
                    psp_name = data.get('psp_name')
                    Contact_User_email = data.get('Contact_User_email')
                    Director_1_en_Name = data.get('Director_1_en_Name')
                    Director_1_cn_Name = data.get('Director_1_CN_Name')
                    Director_1_birth_date = data.get('Director_1_Birthday')

                    # 股东信息（CSV 格式）
                    shareholders = []
                    for i in range(1, 4):
                        cn_name = data.get(f'Shareholder_{i}_cn_Name')
                        en_name = data.get(f'Shareholder_{i}_en_Name')
                        birth_date = data.get(f'Shareholder_{i}_birth_date')
                        if cn_name or en_name:
                            shareholders.append({
                                'full_name_cn': cn_name,
                                'full_name_en': en_name,
                                'birthday': birth_date,
                                'ownership_percent': '30.00'
                            })

                    # 银行信息
                    Bank_account_Number = data.get('Bank_account_Number')
                    Bank_account = data.get('Bank_account')
                    Bank_account_Number_address = data.get('Bank_account_Number_address')
                    Bank_account_Name = data.get('Bank_account_Name')
                    Swift_Code = data.get('Swift_Code')
                    Branch_Code = data.get('Branch_Code')

                    # 额度信息
                    underwrittenAmount = data.get('underwrittenAmount', '0')
                    signedLimit = data.get('signedLimit', '0')
                    approvedLimit = data.get('approvedLimit', '0')
                    activate_limit = data.get('activate_limit', '0')
                    approved_limit_num = float(approvedLimit) if str(approvedLimit).strip() else 0
                    activate_limit_num = float(activate_limit) if str(activate_limit).strip() else 0
                    available_limit = min(approved_limit_num, activate_limit_num)
                    baseRate = data.get('baseRate', '0')
                    marginRate = data.get('marginRate', '0')
                    offerStartDate = data.get('offerStartDate')
                    offerEndDate = data.get('offerEndDate')
                    lender_credit_id = data.get('lender_credit_id', '')
                    lender_company_id = data.get('lender_company_id', '')
                    lender_approved_offer_id = data.get('lender_approved_offer_id', '')

                    # Drawdown 信息（CSV 格式）
                    drawdowns = []
                    for i in range(1, 4):
                        amount = data.get(f'drawdown_amount_{i}', '0')
                        if amount and str(amount).strip() and str(amount).strip() != '0':
                            drawdown_data = {
                                'drawdown_id': f"2017{''.join(secrets.choice(string.digits) for _ in range(18))}",
                                'drawdown_amount': amount,
                                'drawdown_start_datetime': data.get(f'actual_drawdown_date_{i}', ''),
                                'new_repayment_date': data.get(f'new_repayment_date_{i}', ''),
                                'repayments': []
                            }
                            repayment_principal = data.get(f'repayment_{i}_principal', '0')
                            repayment_date = data.get(f'repayment_{i}_date', '')
                            if repayment_principal and str(repayment_principal).strip() and str(repayment_principal).strip() != '0':
                                drawdown_data['repayments'].append({
                                    'repayment_principal': repayment_principal,
                                    'repayment_date': repayment_date
                                })
                            drawdowns.append(drawdown_data)

                # 确保股东至少有3个（不足则补空）
                while len(shareholders) < 3:
                    shareholders.append({
                        'full_name_cn': '',
                        'full_name_en': '',
                        'birthday': '',
                        'ownership_percent': '0'
                    })

                # 生成随机ID
                shareholder_ids = [generate_random_str() for _ in range(3)]
                drawdown_count = len(drawdowns)
                loan_ids = [f"EFL{''.join(secrets.choice(string.digits) for _ in range(17))}" for _ in range(drawdown_count)]
                drawdown_ids = [generate_random_str() for _ in range(drawdown_count)]

                ids = {
                    'random_id': generate_random_str(),
                    'random_id1': generate_random_str(),
                    'random_id2': generate_random_str(),
                    'random_id3': generate_random_str(),
                    'entity_id': generate_random_hex(),  # 添加 entity_id，用于插入新 Entity 记录
                    'hex_id': generate_random_hex(),
                    'insert_psp_id': generate_random_str(),
                    'limit_app_id': generate_random_str(),
                    'credit_offer_id': generate_random_str(),
                    'limit_application_unique_id': f"EFAL{''.join(secrets.choice(string.digits) for _ in range(17))}",
                    'L_approved_offer_id': f"lender-EFA{''.join(secrets.choice(string.digits) for _ in range(17))}",
                    'loan_ids': loan_ids,
                    'drawdown_ids': drawdown_ids,
                    'shareholder_ids': shareholder_ids,
                    'doc_front': str(uuid.uuid4()),
                    'doc_back': str(uuid.uuid4()),
                    'notify_id_1': generate_random_hex(),
                    'notify_id_2': generate_random_hex(),
                    'sql9_10_id': generate_random_hex(),
                    'sql11_12_id': generate_random_hex(),
                    'limit_application_id': generate_random_hex(),
                    'random_id_LAA': generate_random_str(),
                }
                log.info(f"生成的随机数合集: ids generated")

                # 查询用户
                res1 = check_and_execute(executor, f"SELECT * FROM dpu_users WHERE phone_number='{phone_number}'", "Step 1: 查询用户")
                if not res1['data']:
                    log.warning(f"未找到手机号为 {phone_number} 的用户，跳过此行")
                    continue
                merchant_id = res1['data'][0][1]
                log.info(f"Step 1: merchant_id 为 {merchant_id}")

                # 查询 AMZ Token
                res01 = check_and_execute(executor, f"SELECT * FROM dpu_auth_token WHERE authorization_id='{amazon_seller_id}'", "Step 2: 查询AMZ Token")
                if not res01['data']:
                    log.warning(f"未找到AMZ Seller ID 为 {amazon_seller_id} 的AMZ Token，跳过此行")
                    continue
                merchant_account_id = res01['data'][0][2]
                log.info(f"Step 2: merchant_account_id 为 {merchant_account_id}")

                # ==================== Step 4-5：3PL 更新 ====================
                res_3pl_token = executor.execute_sql(
                    f"SELECT merchant_account_id FROM dpu_auth_token WHERE authorization_party='3PL' AND merchant_id='{merchant_id}'"
                )
                if res_3pl_token['data']:
                    original_3pl_merchant_account_id = res_3pl_token['data'][0][0]
                    log.info(f"3PL 当前 merchant_account_id: {original_3pl_merchant_account_id}")
                    # 检查是否已经是正确的 merchant_account_id，如果是则跳过更新
                    if original_3pl_merchant_account_id == merchant_account_id:
                        log.info("Step 4-5: 3PL merchant_account_id 已是正确值，跳过更新")
                    else:
                        check_and_execute(executor, f"UPDATE dpu_auth_token SET merchant_account_id='{merchant_account_id}' WHERE authorization_party='3PL' and merchant_id='{merchant_id}'",
                                          "Step 4：更新dpu_auth_token中3PL的merchant_account_id")
                        check_and_execute(executor, f"update dpu_shops set merchant_account_id='{merchant_account_id}' WHERE emarketplace_data_type='3PL'and merchant_id='{merchant_id}'",
                                          "Step 5：更新dpu_shops中3PL的merchant_account_id")
                else:
                    log.info("Step 4-5: 未找到 3PL 记录，跳过更新")

                # ==================== Step 6：插入 PSP 记录 ====================
                # 检查 psp_id 是否为 null，如果为 null 则跳过
                if psp_id:
                    sql_psp = build_insert_sql('dpu_auth_token', {
                        'authorization_id': psp_id,
                        'authorization_party': 'PSP',
                        'consented_at': '2026-01-16 15:48:10',
                        'create_by': 'SYSTEM',
                        'created_at': '2026-01-16 15:48:10',
                        'id': ids['insert_psp_id'],
                        'last_update_on': "X'0a0a83ee'",
                        'merchant_account_id': merchant_account_id,
                        'merchant_id': merchant_id,
                        'name': psp_name,
                        'status': 'ACTIVE',
                        'update_by': 'SYSTEM',
                        'updated_at': '2026-01-16 15:48:10',
                    })
                    check_and_execute(executor, sql_psp, "Step 6: 向dpu_auth_token插入PSP记录")
                else:
                    log.info("Step 6: psp_id 为 null，跳过 PSP 记录插入")

                # ==================== Step 7：更新 Merchant Account Limit ====================
                sql_mal = f"""UPDATE `dpu_merchant_account_limit`
                            SET
                            `created_at` = '2026-01-16 11:17:45',
                            `currency` = 'USD',
                            `finance_product` = 'LINE_OF_CREDIT',
                            `indicative_limit` = '240000.00',
                            `indicative_limit_update_at` = '2026-01-16 11:17:45',
                            `lender_code` = 'FUNDPARK',
                            `merchant_account_id` = '{merchant_account_id}',
                            `platform_sync_status` = 'PENDING',
                            `psp_status` = 'SUCCESS',
                            `updated_at` = '2026-01-16 07:48:26'
                             WHERE `merchant_id` = '{merchant_id}';"""
                check_and_execute(executor, sql_mal, "Step 7: 更新Merchant Account Limit")

                # ==================== 查询 Application（Step 8 保留查询逻辑，后续步骤需要这些变量） ====================
                res_app = executor.execute_sql(f"SELECT * FROM dpu_application WHERE merchant_id='{merchant_id}'")
                application_id = ''
                application_unique_id = ''
                if res_app['data']:
                    application_id = res_app['data'][0][0]
                    application_unique_id = res_app['data'][0][1]
                    log.info(f"Step 8: 查询到 application_id={application_id}, application_unique_id={application_unique_id}")
                else:
                    log.warning(f"Step 8: 未找到 Application 记录")

                # ==================== Step 9：插入/更新 Entity（需要在更新 Application 之前执行） ====================
                res_entity = executor.execute_sql(f"SELECT * FROM dpu_entity WHERE merchant_id='{merchant_id}'")
                if not res_entity['data']:
                    # 不存在则插入
                    log.info(f"Step 9: 未找到 Entity 记录，插入新记录")

                    # 检查表是否有 extend_json 字段（兼容不同环境）
                    res_columns = executor.execute_sql("SHOW COLUMNS FROM dpu_entity LIKE 'extend_json'")
                    has_extend_json = bool(res_columns['data'])

                    entity_fields = {
                        'additional_info': None,
                        'business_registration_number': business_registration_number,
                        'chi_name': None,
                        'city': '',
                        'company_registration_date': company_registration_date if company_registration_date else '2015-08-12',
                        'company_type': 'Private company limited by shares',
                        'country_list_of_top_3_buyers': 'United States Of America,Canada,Mexico',
                        'country_list_of_top_3_suppliers': 'China',
                        'country_of_source_of_funds': 'Hong Kong',
                        'created_at': '2026-01-21 18:49:21',
                        'created_by': '1039000002',
                        'draft_status': 'SUBMITTED',
                        'en_name_consistent': 0,
                        'encryption_status': 'ENCRYPTED',
                        'eng_name': company_eng_name,
                        'id': ids['entity_id'],
                        'industry': 'Toys & Leisure Products',
                        'initial_source_of_wealth': 'savings',
                        'is_total_equity_over75': 1,
                        'last_submitted_reg_no': business_registration_number,
                        'last_update_on': "X'33a3987643'",
                        'main_product': 'Toys',
                        'merchant_id': merchant_id,
                        'ongoing_source_of_wealth': 'operationProfit',
                        'postcode': '',
                        'registered_country_code': 'CN',
                        'registered_office_address1': 'Unit 808, 8/F, Innovation Plaza, 12 Science Park Road, Hong Kong Science Park, Sha Tin',
                        'registered_office_address2': None,
                        'sanction_status': 'NOT_HIT',
                        'source_of_funds': 'bizOperations',
                        'submission_count': 1,
                        'updated_at': '2026-01-22 02:00:38',
                        'updated_by': '1039000002',
                    }

                    # 仅当表中存在 extend_json 字段时才添加
                    if has_extend_json:
                        entity_fields['extend_json'] = '{}'
                        log.info("Step 9: 检测到 extend_json 字段，将包含在插入中")
                    else:
                        log.info("Step 9: 未检测到 extend_json 字段，跳过该字段")

                    sql_entity = build_insert_sql('dpu_entity', entity_fields)
                    check_and_execute(executor, sql_entity, "Step 9.1: 插入Entity")
                else:
                    # 存在则更新
                    existing_entity_id = res_entity['data'][0][18]  # 获取已存在的 entity id
                    existing_submission_count = res_entity['data'][0][30]  # 获取当前 submission_count
                    ids['entity_id'] = existing_entity_id  # 使用已存在的 entity id
                    log.info(f"Step 9: 查询到 entity_id={existing_entity_id}，更新记录")
                    # 处理 submission_count 为 None 的情况
                    new_submission_count = (existing_submission_count or 0) + 1
                    sql_entity_update = f"""UPDATE `dpu_entity`
                                    SET `business_registration_number` = '{escape_sql(business_registration_number)}',
                                        `eng_name` = '{escape_sql(company_eng_name)}',
                                        `main_product` = 'Toys',
                                        `last_update_on` = '3a987643',
                                        `updated_at` = '2026-01-22 02:00:38',
                                        `updated_by` = '1039000002',
                                        `submission_count` = {new_submission_count}
                                    WHERE `merchant_id` = '{merchant_id}'"""
                    check_and_execute(executor, sql_entity_update, "Step 9.2: 更新Entity")

                # ==================== Step 11-15：股东信息和身份证文档 ====================
                # Step 11-13：查询并插入股东信息
                res_nature_person = executor.execute_sql(f"SELECT * FROM dpu_nature_person WHERE merchant_id='{merchant_id}'")
                if res_nature_person['data']:
                    log.info("Step 11-13: dpu_nature_person 表中已有数据，跳过插入股东信息")
                else:
                    # 插入股东信息（动态处理）
                    for idx, shareholder in enumerate(shareholders[:3]):
                        if not shareholder.get('full_name_en') and not shareholder.get('full_name_cn'):
                            continue
                        cn_name = shareholder.get('full_name_cn', '')
                        en_name = shareholder.get('full_name_en', '')
                        birth_date = shareholder.get('birthday', '')
                        ownership = shareholder.get('ownership_percent', '30.00')
                        sql_dpu_nature_person = build_insert_sql('dpu_nature_person', {
                            'id': ids['shareholder_ids'][idx],
                            'merchant_id': merchant_id,
                            'entity_id': ids['entity_id'],
                            'nature_person_type': 'SHAREHOLDER',
                            'chi_name': cn_name,
                            'eng_name': en_name,
                            'birthday': birth_date,
                            'percentage_of_shares': ownership,
                            'id_type': 'PASSPORT',
                            'id_number': '',
                            'nationality': 'HK',
                            'sanction_status': 'NOT_HIT',
                            'created_at': '2026-01-16 11:17:45',
                            'updated_at': '2026-01-16 11:17:45',
                            'created_by': 'SYSTEM',
                            'updated_by': 'SYSTEM',
                        })
                        check_and_execute(executor, sql_dpu_nature_person, f"Step {11+idx}: 插入Shareholder第{idx+1}条记录")

                # Step 14-15：查询并插入身份证文档
                res_person_documents = executor.execute_sql(f"SELECT * FROM dpu_nature_person_documents WHERE merchant_id='{merchant_id}'")
                if res_person_documents['data']:
                    log.info("Step 14-15: dpu_nature_person_documents 表中已有数据，跳过插入身份证文档")
                else:
                    # 插入第1个股东的身份证文档（正面）
                    if shareholders[0].get('full_name_en') or shareholders[0].get('full_name_cn'):
                        sql_dpu_nature_person_documents_front = build_insert_sql('dpu_nature_person_documents', {
                            'id': ids['doc_front'],
                            'merchant_id': merchant_id,
                            'entity_id': ids['entity_id'],
                            'nature_person_id': ids['shareholder_ids'][0],
                            'doc_type': 'ID_FRONT',
                            'file_url': '/placeholder/id_front.pdf',
                            'status': 'CONSUMED',
                            'content_file_type': 'PDF',
                            'doc_name': 'id_front.pdf',
                            'created_at': '2026-01-16 11:17:45',
                            'updated_at': '2026-01-16 11:17:45',
                            'create_by': 'SYSTEM',
                            'update_by': 'SYSTEM',
                        })
                        check_and_execute(executor, sql_dpu_nature_person_documents_front, "Step 14: 插入dpu_nature_person_documents (正面)")

                        # 插入第1个股东的身份证文档（背面）
                        sql_dpu_nature_person_documents_back = build_insert_sql('dpu_nature_person_documents', {
                            'id': ids['doc_back'],
                            'merchant_id': merchant_id,
                            'entity_id': ids['entity_id'],
                            'nature_person_id': ids['shareholder_ids'][0],
                            'doc_type': 'ID_BACK',
                            'file_url': '/placeholder/id_back.pdf',
                            'status': 'CONSUMED',
                            'content_file_type': 'PDF',
                            'doc_name': 'id_back.pdf',
                            'created_at': '2026-01-16 11:17:45',
                            'updated_at': '2026-01-16 11:17:45',
                            'create_by': 'SYSTEM',
                            'update_by': 'SYSTEM',
                        })
                        check_and_execute(executor, sql_dpu_nature_person_documents_back, "Step 15: 插入dpu_nature_person_documents (背面)")

                # ==================== Step 16：更新 Application（在 Entity 处理之后执行，确保使用正确的 entity_id） ====================
                if res_app['data']:
                    check_and_execute(executor, f"UPDATE dpu_application SET entity_id = '{ids['entity_id']}', application_status = 'APPROVED' WHERE merchant_id='{merchant_id}'", "Step 16：更新Application状态")

                # 更新 dpu_merchants_limit
                sql_dpu_merchants_limit = f"""UPDATE `dpu_merchants_limit`
                                                            SET
                                                            `activated_limit` = '{activate_limit}',
                                                            `activated_limit_update_at` = '2026-01-16 15:48:39',
                                                            `application_flow` = 'main',
                                                            `approved_limit` = '{approvedLimit}',
                                                            `approved_limit_update_at` = '2026-01-16 14:19:09',
                                                            `available_limit` = '{available_limit}',
                                                            `available_limit_update_at` = '2026-01-16 15:48:39',
                                                            `charge_bases` = 'Float',
                                                            `created_at` = '2026-01-16 11:17:18',
                                                            `currency` = 'USD',
                                                            `finance_product` = 'LINE_OF_CREDIT',
                                                            `frozen_limit` = NULL,
                                                            `frozen_limit_update_at` = NULL,
                                                            `indicative_limit` = '240000.00',
                                                            `indicative_limit_update_at` = '2026-02-03 10:12:32',
                                                            `lender_code` = 'FUNDPARK',
                                                            `lender_id` = NULL,
                                                            `margin_rate` = '{marginRate}',
                                                            `rate_type` = 'SOFR',
                                                            `signed_limit` = '{signedLimit}',
                                                            `signed_limit_update_at` = '2026-01-16 15:48:39',
                                                            `underwritten_limit` = '{underwrittenAmount}',
                                                            `underwritten_limit_update_at` = '2026-01-16 14:19:09',
                                                            `updated_at` = '2026-02-03 10:12:32',
                                                            `utilization_limit` = NULL,
                                                            `utilization_limit_update_at` = NULL
                                                             WHERE `merchant_id` = '{merchant_id}';"""
                check_and_execute(executor, sql_dpu_merchants_limit, "Step 17：更新dpu_merchants_limit")

                # Step 18：查询 dpu_bank_account，决定 UPDATE 或 INSERT
                res_bank_account = executor.execute_sql(f"SELECT * FROM dpu_bank_account WHERE merchant_id='{merchant_id}'")
                if res_bank_account['data']:
                    # 存在记录，执行 UPDATE
                    sql_dpu_bank_account = f"""UPDATE `dpu_bank_account`
                        SET `bank_account_name` = '{escape_sql(Bank_account_Name)}',
                            `bank_account_number` = '{escape_sql(Bank_account_Number)}',
                            `bank_code` = '{escape_sql(Branch_Code)}',
                            `bank_name` = '{escape_sql(Bank_account)}',
                            `branch_code` = '{escape_sql(Branch_Code)}',
                            `status` = 'PRIMARY',
                            `swift_code` = '{escape_sql(Swift_Code)}',
                            `updated_at` = '2026-01-22 10:40:05',
                            `bank_address` = '{escape_sql(Bank_account_Number_address)}',
                            `last_update_on` = X'35382e3135322e3131382e3637'
                        WHERE `merchant_id` = '{merchant_id}'"""
                    check_and_execute(executor, sql_dpu_bank_account, "Step 18：更新dpu_bank_account")
                else:
                    # 不存在记录，执行 INSERT
                    sql_dpu_bank_account = build_insert_sql('dpu_bank_account', {
                        'bank_account_name': Bank_account_Name,
                        'bank_account_number': Bank_account_Number,
                        'bank_code': Branch_Code,
                        'bank_name': Bank_account,
                        'branch_code': Branch_Code,
                        'created_at': '2026-01-22 10:40:05',
                        'created_by': '1039000002',
                        'effective_from': '2026-01-22 10:40:05',
                        'effective_to': '2026-01-22 10:40:05',
                        'id': ids['random_id'],
                        'last_update_on': "X'35382e3135322e3131382e3637'",
                        'merchant_id': merchant_id,
                        'phone_number': '19073511039',
                        'status': 'PRIMARY',
                        'swift_code': Swift_Code,
                        'updated_at': '2026-01-22 10:40:05',
                        'updated_by': None,
                        'bank_address': Bank_account_Number_address,
                    })
                    check_and_execute(executor, sql_dpu_bank_account, "Step 18：插入dpu_bank_account")

                # ==================== Step 19-22：插入/更新 notify_event_dependency ====================
                # 定义 notify_event_dependency 的数据配置
                notify_dependency_configs = [
                    {
                        'name': 'Step 19',
                        'event_type': 'FP_FIRST_KYC_START',
                        'dependency_type': 'AMAZON_3PL_SP_DATA_ALIGNMENT',
                        'event_id': ids['sql9_10_id'],
                        'id': ids['random_id']
                    },
                    {
                        'name': 'Step 20',
                        'event_type': 'FP_FIRST_KYC_START',
                        'dependency_type': 'OWS_SANCTIONS_SCREENING',
                        'event_id': ids['sql9_10_id'],
                        'id': ids['random_id1']
                    },
                    {
                        'name': 'Step 21',
                        'event_type': 'FP_FIRST_CREDIT_MODEL_START',
                        'dependency_type': 'AMAZON_3PL_SP_DATA_ALIGNMENT',
                        'event_id': ids['sql11_12_id'],
                        'id': ids['random_id2']
                    },
                    {
                        'name': 'Step 22',
                        'event_type': 'FP_FIRST_CREDIT_MODEL_START',
                        'dependency_type': 'OWS_SANCTIONS_SCREENING',
                        'event_id': ids['sql11_12_id'],
                        'id': ids['random_id3']
                    },
                ]

                for config in notify_dependency_configs:
                    # 先查询是否已存在记录
                    res = executor.execute_sql(
                        f"SELECT * FROM dpu_notify_event_dependency WHERE biz_id='{application_unique_id}' AND event_type='{config['event_type']}' AND dependency_type='{config['dependency_type']}'"
                    )
                    if res['data']:
                        # 存在记录，执行 UPDATE
                        sql = f"""UPDATE `dpu_notify_event_dependency`
                            SET `dependency_status` = 'READY',
                                `dependency_value` = 'READY',
                                `update_time` = '2026-01-22 02:40:05'
                            WHERE `biz_id` = '{application_unique_id}'
                                AND `event_type` = '{config['event_type']}'
                                AND `dependency_type` = '{config['dependency_type']}'"""
                        check_and_execute(executor, sql, f"{config['name']}：更新dpu_notify_event_dependency ({config['dependency_type']})")
                    else:
                        # 不存在记录，执行 INSERT
                        sql = build_insert_sql('dpu_notify_event_dependency', {
                            'biz_id': application_unique_id,
                            'create_time': '2026-01-22 02:40:05',
                            'dependency_finish_time': None,
                            'dependency_status': 'READY',
                            'dependency_type': config['dependency_type'],
                            'dependency_value': 'READY',
                            'event_id': config['event_id'],
                            'event_type': config['event_type'],
                            'ext_json': None,
                            'id': config['id'],
                            'update_time': '2026-01-22 02:40:05',
                        })
                        check_and_execute(executor, sql, f"{config['name']}：插入dpu_notify_event_dependency ({config['dependency_type']})")

                # ==================== Step 23-24：插入/更新 notify_event ====================
                # 定义 notify_event 的数据配置
                notify_event_configs = [
                    {
                        'name': 'Step 23',
                        'event_type': 'FP_FIRST_CREDIT_MODEL_START',
                        'id': ids['notify_id_1']
                    },
                    {
                        'name': 'Step 24',
                        'event_type': 'FP_FIRST_KYC_START',
                        'id': ids['notify_id_2']
                    },
                ]

                for config in notify_event_configs:
                    # 先查询是否已存在记录
                    res = executor.execute_sql(
                        f"SELECT * FROM dpu_notify_event WHERE biz_id='{application_unique_id}' AND event_type='{config['event_type']}'"
                    )
                    if res['data']:
                        # 存在记录，执行 UPDATE
                        sql = f"""UPDATE `dpu_notify_event`
                            SET `notify_status` = 'SUCCESS',
                                `retry_count` = 0,
                                `update_time` = '2026-01-22 02:40:05'
                            WHERE `biz_id` = '{application_unique_id}'
                                AND `event_type` = '{config['event_type']}'"""
                        check_and_execute(executor, sql, f"{config['name']}：更新dpu_notify_event ({config['event_type']})")
                    else:
                        # 不存在记录，执行 INSERT
                        sql = build_insert_sql('dpu_notify_event', {
                            'biz_id': application_unique_id,
                            'create_time': '2026-01-22 02:40:05',
                            'event_type': config['event_type'],
                            'ext_json': None,
                            'id': config['id'],
                            'next_retry_time': None,
                            'notify_status': 'SUCCESS',
                            'retry_count': 0,
                            'update_time': '2026-01-22 02:40:05',
                        })
                        check_and_execute(executor, sql, f"{config['name']}：插入dpu_notify_event ({config['event_type']})")

                # Step 25：查询 dpu_credit_offer，决定 UPDATE 或 INSERT
                res_credit_offer = executor.execute_sql(f"SELECT * FROM dpu_credit_offer WHERE merchant_id='{merchant_id}'")
                if res_credit_offer['data']:
                    # 存在记录，执行 UPDATE
                    sql_dpu_credit_offer = f"""UPDATE `dpu_credit_offer`
                        SET `application_id` = '{application_id}',
                            `application_unique_id` = '{application_unique_id}',
                            `approved_limit_amount` = '{approvedLimit}',
                            `base_rate` = '{baseRate}',
                            `e_sign_status` = 'SUCCESS',
                            `lender_approved_offer_id` = '{lender_approved_offer_id}',
                            `lender_code` = 'FUNDPARK',
                            `lender_company_id` = '{lender_company_id}',
                            `lender_credit_id` = '{lender_credit_id}',
                            `limit_application_id` = '{ids['limit_application_id']}',
                            `margin_rate` = '{marginRate}',
                            `signed_limit_amount` = '{signedLimit}',
                            `status` = 'ACCEPTED',
                            `updated_at` = '2026-01-16 15:48:39'
                        WHERE `merchant_id` = '{merchant_id}'"""
                    check_and_execute(executor, sql_dpu_credit_offer, "Step 25：更新dpu_credit_offer")
                else:
                    # 不存在记录，执行 INSERT
                    sql_dpu_credit_offer = build_insert_sql('dpu_credit_offer', {
                        'application_id': application_id,
                        'application_unique_id': application_unique_id,
                        'approved_limit_amount': approvedLimit,
                        'approved_limit_currency': 'USD',
                        'base_rate': baseRate,
                        'base_rate_type': 'SOFR',
                        'created_at': '2026-01-16 11:33:29',
                        'created_by': 'SYSTEM',
                        'e_sign_status': 'SUCCESS',
                        'finance_product': 'LINE_OF_CREDIT',
                        'id': ids['credit_offer_id'],
                        'lender_approved_offer_id': lender_approved_offer_id,
                        'lender_code': 'FUNDPARK',
                        'lender_company_id': lender_company_id,
                        'lender_credit_id': lender_credit_id,
                        'limit_application_id': ids['limit_application_id'],
                        'margin_rate': marginRate,
                        'max_tenor': 24,
                        'merchant_id': merchant_id,
                        'min_tenor': 3,
                        'offer_end_date': '2024-10-15',
                        'offer_start_date': '2023-10-16',
                        'offer_term': 90,
                        'offer_term_unit': 'Days',
                        'rate_type': 'Float',
                        'signed_limit_amount': signedLimit,
                        'signed_limit_currency': 'USD',
                        'status': 'ACCEPTED',
                        'updated_at': '2026-01-16 15:48:39',
                        'updated_by': 'SYSTEM',
                    })
                    check_and_execute(executor, sql_dpu_credit_offer, "Step 25：插入dpu_credit_offer")

                # Step 26：查询 dpu_limit_application，决定 UPDATE 或 INSERT
                res_limit_application = executor.execute_sql(f"SELECT * FROM dpu_limit_application WHERE merchant_id='{merchant_id}'")
                if res_limit_application['data']:
                    # 存在记录，执行 UPDATE
                    sql_dpu_limit_application = f"""UPDATE `dpu_limit_application`
                        SET `currency` = 'USD',
                            `lender_code` = 'FUNDPARK',
                            `limit_application_unique_id` = '{ids['limit_application_unique_id']}',
                            `product` = 'LINE_OF_CREDIT',
                            `status` = 'RECEIVED',
                            `underwritten_limit` = '{underwrittenAmount}',
                            `update_by` = '5058000001',
                            `updated_at` = '2026-01-16 14:19:17'
                        WHERE `merchant_id` = '{merchant_id}'"""
                    check_and_execute(executor, sql_dpu_limit_application, "Step 26：更新dpu_limit_application")
                else:
                    # 不存在记录，执行 INSERT
                    sql_dpu_limit_application = build_insert_sql('dpu_limit_application', {
                        'activated_limit': None,
                        'available_limit': None,
                        'create_by': 'SYSTEM',
                        'created_at': '2026-01-16 11:32:31',
                        'currency': 'USD',
                        'id': ids['limit_application_id'],
                        'last_update_on': "X'0a0a83ee'",
                        'lender_code': 'FUNDPARK',
                        'limit_application_unique_id': ids['limit_application_unique_id'],
                        'merchant_id': merchant_id,
                        'product': 'LINE_OF_CREDIT',
                        'status': 'RECEIVED',
                        'underwritten_limit': underwrittenAmount,
                        'update_by': '5058000001',
                        'updated_at': '2026-01-16 14:19:17',
                    })
                    check_and_execute(executor, sql_dpu_limit_application, "Step 26：插入dpu_limit_application")

                # Step 27：查询 dpu_limit_application_account，决定 UPDATE 或 INSERT
                res_limit_application_account = executor.execute_sql(f"SELECT * FROM dpu_limit_application_account WHERE merchant_id='{merchant_id}'")
                if res_limit_application_account['data']:
                    # 存在记录，执行 UPDATE
                    sql_dpu_limit_application_account = f"""UPDATE `dpu_limit_application_account`
                        SET `activated_limit` = '{approvedLimit}',
                            `approved_limit` = '{approvedLimit}',
                            `authorization_id` = '{amazon_seller_id}',
                            `currency` = 'USD',
                            `indicative_limit` = '240000.00',
                            `limit_application_id` = '{ids['limit_application_id']}',
                            `limit_application_unique_id` = '{ids['limit_application_unique_id']}',
                            `merchant_account_id` = '{merchant_account_id}',
                            `psp_status` = 'INITIAL',
                            `signed_limit` = '{signedLimit}',
                            `underwritten_limit` = '{underwrittenAmount}',
                            `update_by` = 'SYSTEM',
                            `updated_at` = '2026-01-16 22:18:51'
                        WHERE `merchant_id` = '{merchant_id}'"""
                    check_and_execute(executor, sql_dpu_limit_application_account, "Step 27：更新dpu_limit_application_account")
                else:
                    # 不存在记录，执行 INSERT
                    sql_dpu_limit_application_account = build_insert_sql('dpu_limit_application_account', {
                        'activated_limit': approvedLimit,
                        'approved_limit': approvedLimit,
                        'authorization_id': amazon_seller_id,
                        'create_by': 'SYSTEM',
                        'created_at': '2026-01-16 19:32:31',
                        'currency': 'USD',
                        'frozen_limit': None,
                        'id': ids['random_id_LAA'],
                        'indicative_limit': '240000.00',
                        'last_update_on': "X'0a0a83ee'",
                        'limit_application_id': ids['limit_application_id'],
                        'limit_application_unique_id': ids['limit_application_unique_id'],
                        'merchant_account_id': merchant_account_id,
                        'merchant_id': merchant_id,
                        'psp_status': 'INITIAL',
                        'signed_limit': signedLimit,
                        'underwritten_limit': underwrittenAmount,
                        'update_by': 'SYSTEM',
                        'updated_at': '2026-01-16 22:18:51',
                        'utilization_limit': None,
                    })
                    check_and_execute(executor, sql_dpu_limit_application_account, "Step 27：插入dpu_limit_application_account")

                # 插入 drawdown（动态处理）
                available_limit_current = available_limit
                for idx, dd in enumerate(drawdowns):
                    drawdown_amount = dd.get('drawdown_amount', '0')
                    if not drawdown_amount or str(drawdown_amount).strip() == '' or str(drawdown_amount).strip() == '0':
                        continue

                    # 计算还款总额（在插入 drawdown 之前计算）
                    repayments = dd.get('repayments', [])
                    total_repayment = sum(float(r.get('repayment_principal', 0)) for r in repayments)
                    outstanding_amount = float(drawdown_amount) - total_repayment

                    drawdown_id = dd.get('drawdown_id', f"2017{''.join(secrets.choice(string.digits) for _ in range(18))}")
                    # 处理 drawdown_start_datetime：如果只有日期没有时间，自动添加 00:00:00
                    raw_start_datetime = dd.get('drawdown_start_datetime', '2026-01-26 00:00:00')
                    if ' ' not in str(raw_start_datetime):
                        drawdown_start_datetime = f"{raw_start_datetime} 00:00:00"
                    else:
                        drawdown_start_datetime = raw_start_datetime
                    # 计算 new_repayment_date = drawdown_start_datetime + 90天
                    start_date_obj = datetime.strptime(drawdown_start_datetime, '%Y-%m-%d %H:%M:%S')
                    new_repayment_date = (start_date_obj + timedelta(days=90)).strftime('%Y-%m-%d')
                    # 计算总利率：baseRate + marginRate
                    total_interest_rate_val = float(baseRate) + float(marginRate)
                    loan_id = loan_ids[idx] if idx < len(loan_ids) else f"EFL{''.join(secrets.choice(string.digits) for _ in range(17))}"
                    drawdown_sql_id = drawdown_ids[idx] if idx < len(drawdown_ids) else generate_random_str()

                    sql_dpu_drawdown = build_insert_sql('dpu_drawdown', {
                        'account_name': Bank_account_Name,
                        'account_number': Bank_account_Number,
                        'account_platform': Bank_account,
                        'actual_drawdown_date': '2026-01-26 00:00:00',
                        'bank_address': Bank_account_Number_address,
                        'base_interest_rate': baseRate,
                        'base_rate_type': 'SOFR',
                        'branch_code': Branch_Code,
                        'charge_bases': 'Float',
                        'created_at': '2026-02-03 19:54:48',
                        'currency': 'USD',
                        'drawdown_amount': drawdown_amount,
                        'drawdown_complete_datetime': drawdown_start_datetime,
                        'drawdown_failed_reason': None,
                        'drawdown_start_datetime': None,
                        'drawdown_submit_datetime': '2026-02-03 19:54:48',
                        'fee_or_charge_amount': marginRate,
                        'fee_or_charge_currency': 'USD',
                        'fee_or_charge_date': '2023-10-16 00:00:00',
                        'fee_or_charge_type': 'PROCESSING_FEE',
                        'finance_product': 'LINE_OF_CREDIT',
                        'fixed_rate': None,
                        'id': drawdown_sql_id,
                        'lender_approved_offer_id': lender_approved_offer_id,
                        'lender_code': 'FUNDPARK',
                        'lender_drawdown_id': 'DRA1',
                        'lender_id': None,
                        'lender_loan_id': drawdown_id,
                        'loan_id': loan_id,
                        'margin_interest_rate': marginRate,
                        'marketplace_country': None,
                        'merchant_id': merchant_id,
                        'new_repayment_date': new_repayment_date,
                        'outstanding_amount': outstanding_amount,
                        'overdue_days': None,
                        'phone_number': None,
                        'repayment_method': 'ANYTIME',
                        'repayment_status': 'REPAID' if abs(total_repayment - float(drawdown_amount)) < 0.01 else 'OUTSTANDING',
                        'repayment_term': '90',
                        'status': 'APPROVED',
                        'swift_code': Swift_Code,
                        'tenor': None,
                        'term': 90,
                        'term_unit': 'Days',
                        'total_interest_rate': total_interest_rate_val,
                        'updated_at': '2026-02-03 19:54:54',
                    })
                    check_and_execute(executor, sql_dpu_drawdown, f"Step {28+idx}: 插入第{idx+1}笔drawdown记录")

                    # 插入 repayment 记录（如果存在）
                    for repayment_idx, rp in enumerate(repayments):
                        repayment_principal = float(rp.get('repayment_principal', 0))
                        if repayment_principal <= 0:
                            continue

                        repayment_date_str = rp.get('repayment_date', '')
                        if repayment_date_str and ' ' not in repayment_date_str:
                            repayment_complete_datetime = f"{repayment_date_str} 15:20:05"
                        else:
                            repayment_complete_datetime = repayment_date_str or "2026-02-24 15:20:05"

                        # 直接使用 migration_data.json 中的 repaymentInterest，不通过计算
                        repayment_interest = rp.get('repaymentInterest', '0')
                        interest_paid_amount = float(repayment_interest) if repayment_interest else 0.0

                        # 总还款额 = 本金 + 利息 + 费用
                        total_paid_amount = repayment_principal + interest_paid_amount

                        # 生成 repayment 相关 ID
                        repayment_id = generate_random_hex(32)
                        lender_repayment_id = f"LRPECFFC{ repayment_idx + 1}-{secrets.choice(string.digits)}"

                        sql_dpu_repayment = build_insert_sql('dpu_repayment', {
                            'id': repayment_id,
                            'merchant_id': merchant_id,
                            'dpu_loan_id': loan_id,
                            'lender_loan_id': drawdown_id,
                            'lender_company_id': lender_company_id,
                            'lender_credit_id': lender_credit_id,
                            'lender_approve_offer_id': None,
                            'lender_drawdown_id': 'DRA1',
                            'lender_repayment_id': lender_repayment_id,
                            'last_updated_on': repayment_complete_datetime,
                            'last_updated_by': 'system',
                            'repayment_status': 'COMPLETED',
                            'failure_reason': None,
                            'fund_source': 'BankTransfer',
                            'submit_date_time': repayment_complete_datetime,  
                            'failure_date_time': None,
                            'complete_date_time': repayment_complete_datetime,
                            'total_paid_amount_currency': 'USD',
                            'total_paid_amount_value': total_paid_amount,
                            'principal_paid_amount_currency': 'USD',
                            'principal_paid_amount_value': repayment_principal,
                            'interest_paid_amount_currency': 'USD',
                            'interest_paid_amount_value': interest_paid_amount,
                            'fee_paid_amount_currency': 'USD',
                            'fee_paid_amount_value': 0.00,
                            'outstanding_amount_currency': 'USD',
                            'outstanding_amount_value': 0.00,
                            'event_id': str(uuid.uuid4()),
                            'created_at': repayment_complete_datetime,
                            'updated_at': repayment_complete_datetime,
                        })
                        check_and_execute(executor, sql_dpu_repayment, f"Step {28+idx}.{repayment_idx+1}: 插入第{repayment_idx+1}笔repayment记录")

                    # 计算可用额度变化
                    available_limit_current = available_limit_current - float(drawdown_amount) + total_repayment

                # 更新最终可用额度和使用额度
                # utilization_limit = 每笔 drawdown 的未偿还本金之和
                if drawdowns:
                    # 重新计算所有 drawdown 的 outstanding_amount 总和
                    total_utilization = 0
                    for dd in drawdowns:
                        drawdown_amount = float(dd.get('drawdown_amount', 0))
                        repayments = dd.get('repayments', [])
                        total_repayment = sum(float(r.get('repayment_principal', 0)) for r in repayments)
                        outstanding_amount = drawdown_amount - total_repayment
                        total_utilization += outstanding_amount

                    sql_update_limit = f"""update `dpu_merchants_limit` set `available_limit` = '{available_limit_current}', `utilization_limit` = '{total_utilization}', `utilization_limit_update_at` = now(), `updated_at` = now() where `merchant_id` = '{merchant_id}'"""
                    check_and_execute(executor, sql_update_limit, "Step 36: 更新最终可用额度和使用额度")

    except Exception as e:
        log.error(f"处理数据时出错: {e}")
        raise


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        # 默认使用 migration_data.json
        file_path = 'migration_data.json'
    else:
        file_path = sys.argv[1]
    run_application(file_path)
