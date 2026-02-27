# -*- coding: utf-8 -*-
import logging
import time
import uuid
import random
import string
import csv
import pymysql
import secrets
from pymysql.constants import CLIENT

# ================= 配置区域 =================
# 建议将配置项提取出来，方便修改
DB_CONFIG = {
    "host": "aurora-dpu-sit.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
    "user": "dpu_sit",
    "password": "20250818dpu_sit",
    "database": "dpu_seller_center",
    "port": 3306,
    "charset": "utf8mb4",
    "connect_timeout": 1500,
    "read_timeout": 15,
}

# 初始化日志
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ================= 数据库操作类 =================
class ExecuteSql:
    def __init__(self):
        self.conn = pymysql.connect(**DB_CONFIG, autocommit=True, client_flag=CLIENT.INTERACTIVE)
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

# ================= 辅助函数 =================
def generate_random_str(k=32):
    """生成随机字符串"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=k))

def generate_random_hex(k=32):
    """生成随机16进制字符串"""
    return ''.join(random.choices(string.hexdigits, k=k)).lower()

def check_and_execute(executor, sql, step_name):
    """封装执行、日志和错误检查逻辑"""
    res = executor.execute_sql(sql)
    if not res['success']:
        log.error(f"{step_name} 失败，终止当前行处理。错误: {res['error']}")
        raise Exception(f"SQL Failed: {step_name}")
    log.info(f"{step_name} 成功")
    return res

# ================= 主逻辑 =================
def run_application(file_path):
    log.info(f"\n=== 开始执行run_application ===")
    try:
        with open(file_path, 'r', newline='', encoding='gbk') as csvfile:
            reader = csv.DictReader(csvfile)
            with ExecuteSql() as executor:
                for row_idx, row in enumerate(reader):
                    log.info(f"\n{'='*20} 正在处理第 {row_idx+1} 行数据 {'='*20}")
                    # 1. 读取数据 (增加 .get 防止 KeyError)
                    phone_number = row.get('phone_number')
                    business_registration_number = row.get('business_registration_number')
                    company_registration_date = row.get('Company Registration Date')
                    company_eng_name = row.get('company_eng_name')
                    amazon_seller_id = row.get('amazon_seller_id')
                    psp_id = row.get('psp_id')
                    psp_name = row.get('psp_name')
                    Contact_User_email = row.get('Contact_User_email')
                    Director_1_en_Name = row.get('Director_1_en_Name')
                    Director_1_birth_date = row.get('Director_1_birth_date')
                    #股东1信息
                    Shareholder_1_cn_Name = row.get('Shareholder_1_cn_Name')
                    Shareholder_1_en_Name = row.get('Shareholder_1_en_Name')
                    Shareholder_1_birth_date = row.get('Shareholder_1_birth_date')
                    #股东2信息
                    Shareholder_2_cn_Name = row.get('Shareholder_2_cn_Name')
                    Shareholder_2_en_Name = row.get('Shareholder_2_en_Name')
                    Shareholder_2_birth_date = row.get('Shareholder_2_birth_date')
                    #股东3信息
                    Shareholder_3_cn_Name = row.get('Shareholder_3_cn_Name')
                    Shareholder_3_en_Name = row.get('Shareholder_3_en_Name')
                    Shareholder_3_birth_date = row.get('Shareholder_3_birth_date')
                    Bank_account_Number = row.get('Bank_account_Number')   # 银行账号
                    Bank_account = row.get('Bank_account')   # 银行账号开户行
                    Bank_account_Number_address = row.get('Bank_account_Number_address') # 银行账号开户行地址
                    Bank_account_Name = row.get('Bank_account_Name')  # 开户企业名称
                    Swift_Code = row.get('Swift_Code')
                    Branch_Code = row.get('Branch_Code')
                    # 提取各种额度
                    underwrittenAmount = row.get('underwrittenAmount', '0')
                    signedLimit = row.get('signedLimit', '0')
                    approvedLimit = row.get('approvedLimit', '0')
                    activate_limit = row.get('activate_limit', '0')
                    approved_limit_num = float(approvedLimit) if str(approvedLimit).strip() else 0
                    activate_limit_num = float(activate_limit) if str(activate_limit).strip() else 0
                    # 计算可用提现金额
                    available_limit = min(approved_limit_num, activate_limit_num)   #总的提现额度
                    baseRate = row.get('baseRate', '0')
                    marginRate = row.get('marginRate', '0')
                    lender_credit_id = row.get('lender_credit_id', '')
                    lender_company_id = row.get('lender_company_id', '')
                    lender_approved_offer_id = row.get('lender_approved_offer_id', '')
                    offerStartDate = row.get('offerStartDate')
                    offerEndDate = row.get('offerEndDate')

                    # 1. 处理提现金额和还款日期
                    #第一笔借款记录
                    drawdown_amount_1= row.get('drawdown_amount_1', '0') # 第一笔提现金额
                    actual_drawdown_date_1 = row.get('actual_drawdown_date_1', '')  # 第一笔实际提现日期
                    new_repayment_date_1 = row.get('new_repayment_date_1', '')      # 第一笔新还款日期
                    #第一笔还款
                    repayment_1_principal = row.get('repayment_1_principal', '0') # 第一笔还款金额
                    repayment_1_date = row.get('repayment_1_date', '')      # 第一笔还款日期

                    # 处理第一笔借款的还款金额（确保非空字符串才能转换）
                    repayment_1_principal_num = float(repayment_1_principal) if (repayment_1_principal is not None and str(repayment_1_principal).strip()) else 0

                    if (drawdown_amount_1 is not None and str(drawdown_amount_1).strip() != ''):
                        available_limit_1 = float(available_limit) - float(drawdown_amount_1) + repayment_1_principal_num  # 第一笔借款完成之后--可用提现金额
                        print('available_limit_1为', available_limit_1)

                    else:
                        print(f"drawdown_amount_1: '{drawdown_amount_1}'为空，跳过计算")
                        print("其中一个提现金额为空，跳过计算")



                    #第二笔借款记录
                    drawdown_amount_2= row.get('drawdown_amount_2', '0')  # 第二笔提现金额
                    actual_drawdown_date_2 = row.get('actual_drawdown_date_2', '')  # 第二笔实际提现日期
                    new_repayment_date_2 = row.get('new_repayment_date_2', '')      # 第二笔新还款日期
                    #第二笔还款
                    repayment_2_principal = row.get('repayment_2_principal', '0') # 第二笔还款金额
                    repayment_2_date = row.get('repayment_2_date', '')      # 第二笔还款日期

                    # 2. 生成所有需要的随机ID
                    ids = {
                        'random_id': generate_random_str(),
                        'random_id1': generate_random_str(),
                        'random_id2': generate_random_str(),
                        'random_id3': generate_random_str(),
                        'random_id4': generate_random_str(),  # Step 33 使用
                        'random_id5': generate_random_str(),  # Step 34 使用
                        'app_entity_id': generate_random_str(),
                        'entity_id': generate_random_hex(),
                        'insert_psp_id': generate_random_str(),
                        'limit_app_id': generate_random_str(),
                        'credit_offer_id': generate_random_str(),
                        'limit_application_unique_id': f"EFAL{''.join(secrets.choice(string.digits) for _ in range(17))}",
                        'L_approved_offer_id': f"lender-EFA{''.join(secrets.choice(string.digits) for _ in range(17))}",   #测试用，到时需要修改
                        'loan_id': f"EFL{''.join(secrets.choice(string.digits) for _ in range(17))}",  #第一笔提现loan_id
                        'loan_id1': f"EFL{''.join(secrets.choice(string.digits) for _ in range(17))}",  #第二笔提现loan_id
                        'doc_front': str(uuid.uuid4()),
                        'doc_back': str(uuid.uuid4()),
                        'notify_id_1': generate_random_hex(),
                        'notify_id_2': generate_random_hex(),
                        'notify_id_3': generate_random_hex(),
                        'sql9_10_id': generate_random_hex(),
                        'sql11_12_id': generate_random_hex(),
                        'random_limit_application_unique_id': generate_random_hex(),
                        'limit_application_id': generate_random_hex(),
                        'random_id_LAA': generate_random_str(),
                    }
                    print('生成的随机数合集:', ids)

                    # --- 🥚🥚🥚 查询用户 ---
                    res1 = check_and_execute(executor, f"SELECT * FROM dpu_users WHERE phone_number='{phone_number}'", "Step 1: 查询用户")
                    if not res1['data']:
                        log.warning(f"未找到手机号为 {phone_number} 的用户，跳过此行")
                        continue
                    merchant_id = res1['data'][0][1]
                    log.info(f"Step 1: 找到手机号为 {phone_number} 的用户，merchant_id 为 {merchant_id}")

                    # --- 🥚🥚🥚 查询 AMZ Token ---
                    res01 = check_and_execute(executor, f"SELECT * FROM dpu_auth_token WHERE authorization_id='{amazon_seller_id}'", "Step 2: 查询AMZ Token")
                    if not res01['data']:
                        log.warning(f"Step 3:未找到AMZ Seller ID 为 {amazon_seller_id} 的AMZ Token，跳过此行")
                        continue
                    merchant_account_id = res01['data'][0][2]
                    log.info(f"Step 3: 找到AMZ Seller_ID 为 {amazon_seller_id} 的AMZ_AuthToken，merchant_account_id 为 {merchant_account_id}")

                    # --- 🥚🥚🥚 更新/插入 PSP 相关 ---
                    check_and_execute(executor, f"UPDATE dpu_auth_token SET merchant_account_id='{merchant_account_id}' WHERE authorization_party='3PL' and merchant_id='{merchant_id}'",
                                      "Step 4：更新dpu_auth_token中3PL的merchant_account_id与SP一致")

                    check_and_execute(executor, f"update dpu_shops set merchant_account_id='{merchant_account_id}' WHERE emarketplace_data_type='3PL'and merchant_id='{merchant_id}'",
                                      "Step 5：更新dpu_shops中3PL的merchant_account_id与SP一致")

                    sql_psp = f"""INSERT INTO `dpu_auth_token` (`authorization_id`, `authorization_party`, `consented_at`, `create_by`, `created_at`, `id`, `last_update_on`, `merchant_account_id`, `merchant_id`, `name`, `status`, `update_by`, `updated_at`) 
                                 VALUES ('{psp_id}', 'PSP', '2026-01-16 15:48:10', 'SYSTEM', '2026-01-16 15:48:10', '{ids['insert_psp_id']}', X'0a0a83ee', '{merchant_account_id}', '{merchant_id}', '{psp_name}', 'ACTIVE', 'SYSTEM', '2026-01-16 15:48:10')"""
                    check_and_execute(executor, sql_psp, "Step 6: 向dpu_auth_token插入PSP记录")

                    sql_mal = f"""UPDATE `dpu_merchant_account_limit` 
                                        SET 
                                        `created_at` = '2026-01-16 11:17:45',
                                        `currency` = 'USD',
                                        `finance_product` = 'LINE_OF_CREDIT',
                                        `indicative_limit` = '0.00',
                                        `indicative_limit_update_at` = '2026-01-16 11:17:45',
                                        `lender_code` = 'FUNDPARK',
                                        `merchant_account_id` = '{merchant_account_id}',
                                        `platform_sync_status` = 'PENDING',
                                        `psp_status` = 'SUCCESS',
                                        `updated_at` = '2026-01-16 07:48:26'
                                         WHERE `merchant_id` = '{merchant_id}';"""
                    check_and_execute(executor, sql_mal, "Step 7: 插入Merchant Account Limit")

                    # --- 🥚🥚🥚更新 Application ---
                    res2 = check_and_execute(executor, f"SELECT * FROM dpu_application WHERE merchant_id='{merchant_id}'", "Step 8: 查询Application")

                    application_id = ''
                    application_unique_id = ''
                    if res2['data']:
                        application_id = res2['data'][0][0]
                        application_unique_id = res2['data'][0][1]
                        check_and_execute(executor, f"UPDATE dpu_application SET entity_id = '{ids['app_entity_id']}', application_status = 'SUBMITTED' WHERE merchant_id='{merchant_id}'", "Step 9：更新Application状态")

                    # --- 🥚🥚🥚 插入 Entity, Person, Docs ---
                    #插入Entity
                    sql_entity = f"""insert into `dpu_entity` (`additional_info`, `business_registration_number`, `chi_name`, `city`, `company_registration_date`, `company_type`, `country_list_of_top_3_buyers`, `country_list_of_top_3_suppliers`,`country_of_source_of_funds`,`created_at`, `created_by`, `draft_status`, `en_name_consistent`, `encryption_status`,`eng_name`, `extend_json`, `funder_type`, `id`, `industry`, `initial_source_of_wealth`, `is_total_equity_over75`,`last_submitted_reg_no`, `last_update_on`, `main_product`, `merchant_id`, `ongoing_source_of_wealth`, `postcode`,`registered_country_code`, `registered_office_address1`, `registered_office_address2`, `sanction_status`, `source_of_funds`, `submission_count`, `updated_at`, `updated_by`)
                                    values (NULL, '{business_registration_number}', NULL, '', '2015-08-12', 'Private company limited by shares', 'United States Of America,Canada,Mexico', 'China', 'Hong Kong', '2026-01-21 18:49:21', '1039000002', 'SUBMITTED', 0, 'ENCRYPTED', '{company_eng_name}', '{{}}', 'FUNDPARK', '{ids['entity_id']}', 'Toys & Leisure Products', 'savings', 1, '{business_registration_number}', '3a987643', 'Toys', '{merchant_id}', 'operationProfit', '', 'CN', 'Unit 808, 8/F, Innovation Plaza, 12 Science Park Road, Hong Kong Science Park, Sha Tin', NULL, 'NOT_HIT', 'bizOperations', 1, '2026-01-22 02:00:38', '1039000002')"""
                    check_and_execute(executor, sql_entity, "Step 10: 插入Entity")

                    #插入dpu_nature_person--Shareholder
                    sql_dpu_nature_person = f"""insert into `dpu_nature_person` (`add_status`, `birthday`, `business_key`, `chi_name`, `city`,`country_code`, `created_at`, `created_by`, `draft_status`, `email`, `encryption_status`, `eng_name`,`entity_id`, `extend_json`, `first_chi_name`, `funder_type`, `id`, `id_number`, `id_type`, `last_chi_name`,`last_update_on`, `marital_status`, `merchant_id`, `nationality`, `nature_person_associate_id`, `nature_person_type`, `number_of_shares`, `percentage_of_shares`, `phone_country_code`, `phone_number`,`postcode`, `residential_address1`, `residential_address2`, `sanction_status`, `updated_at`, `updated_by`) 
                                                values ('API', '{Shareholder_1_birth_date}', NULL, '{Shareholder_1_cn_Name}', '', '', '2026-01-22 02:23:06', '1039000002', 'SUBMITTED', 'asdas22dasd@163.com', 'PLAINTEXT', '{Shareholder_1_en_Name}', '{ids['entity_id']}', NULL, NULL, 'FUNDPARK', '{ids['random_id']}', NULL, 'PRC_RESIDENT_ID_CARD', NULL, X'3a987643', 'UNKNOWN', '{merchant_id}', 'China', NULL, 'DIRECTOR_SHAREHOLDER_UBO', 10, '30.00', '+86', '19073511031', '', '', '', 'INITIAL','2026-01-22 02:23:06', '1039000002')"""
                    check_and_execute(executor, sql_dpu_nature_person, "Step 11: 向dpu_nature_person插入Shareholder第一条记录")

                    sql_dpu_nature_person = f"""insert into `dpu_nature_person` (`add_status`, `birthday`, `business_key`, `chi_name`, `city`,`country_code`, `created_at`, `created_by`, `draft_status`, `email`, `encryption_status`, `eng_name`,`entity_id`, `extend_json`, `first_chi_name`, `funder_type`, `id`, `id_number`, `id_type`, `last_chi_name`,`last_update_on`, `marital_status`, `merchant_id`, `nationality`, `nature_person_associate_id`, `nature_person_type`, `number_of_shares`, `percentage_of_shares`, `phone_country_code`, `phone_number`,`postcode`, `residential_address1`, `residential_address2`, `sanction_status`, `updated_at`, `updated_by`) 
                                                                        values ('API', '{Shareholder_2_birth_date}', NULL, '{Shareholder_2_cn_Name}', '', '', '2026-01-22 02:23:06', '1039000002', 'SUBMITTED', 'asdas22dasd@163.com', 'PLAINTEXT', '{Shareholder_2_en_Name}', '{ids['entity_id']}', NULL, NULL, 'FUNDPARK', '{ids['random_id1']}', NULL, 'PRC_RESIDENT_ID_CARD', NULL, X'3a987643', 'UNKNOWN', '{merchant_id}', 'China', NULL, 'DIRECTOR_SHAREHOLDER_UBO', 10, '30.00', '+86', '19073511031', '', '', '', 'INITIAL','2026-01-22 02:23:06', '1039000002')"""
                    check_and_execute(executor, sql_dpu_nature_person, "Step 12: 向dpu_nature_person插入Shareholder第二条记录")

                    sql_dpu_nature_person = f"""insert into `dpu_nature_person` (`add_status`, `birthday`, `business_key`, `chi_name`, `city`,`country_code`, `created_at`, `created_by`, `draft_status`, `email`, `encryption_status`, `eng_name`,`entity_id`, `extend_json`, `first_chi_name`, `funder_type`, `id`, `id_number`, `id_type`, `last_chi_name`,`last_update_on`, `marital_status`, `merchant_id`, `nationality`, `nature_person_associate_id`, `nature_person_type`, `number_of_shares`, `percentage_of_shares`, `phone_country_code`, `phone_number`,`postcode`, `residential_address1`, `residential_address2`, `sanction_status`, `updated_at`, `updated_by`) 
                                                                                                values ('API', '{Shareholder_3_birth_date}', NULL, '{Shareholder_3_cn_Name}', '', '', '2026-01-22 02:23:06', '1039000002', 'SUBMITTED', 'asdas22dasd@163.com', 'PLAINTEXT', '{Shareholder_3_en_Name}', '{ids['entity_id']}', NULL, NULL, 'FUNDPARK', '{ids['random_id2']}', NULL, 'PRC_RESIDENT_ID_CARD', NULL, X'3a987643', 'UNKNOWN', '{merchant_id}', 'China', NULL, 'DIRECTOR_SHAREHOLDER_UBO', 10, '40.00', '+86', '19073511031', '', '', '', 'INITIAL','2026-01-22 02:23:06', '1039000002')"""
                    check_and_execute(executor, sql_dpu_nature_person, "Step 13: 向dpu_nature_person插入Shareholder第三条记录")

                    #插入dpu_person_doc(正面)
                    sql_dpu_nature_person_documents_front = f"""insert into `dpu_nature_person_documents` (`application_id`, 
                                                                `application_unique_id`, `content_file_type`, `create_by`, `created_at`, `doc_name`,
                                                                 `doc_type`, `entity_id`, `file_content`, `file_url`, `id`, `last_update_on`, `merchant_id`, 
                                                                 `nature_person_id`, `status`, `update_by`, `updated_at`) values ('f5208fb77d8d4712a436b716331cb6b9', 
                                                                 '{application_unique_id}', 'IMG', NULL, '2026-01-22 02:23:06', 'PRC ID-Front@3x-2Sh4SffG.png', 
                                                                 'DIRECTOR_ID_FRONT', '{ids['entity_id']}', NULL, 'uploads/default/default/default/file_20260122102246_121ab309d18b.png', 
                                                                 '{ids['doc_front']}', NULL, '{merchant_id}', '1f4479db-b9ef-4cce-aa45-9871753a2a1c', 
                                                                 'NEW', NULL, '2026-01-22 02:23:06')"""
                    check_and_execute(executor, sql_dpu_nature_person_documents_front, "Step 14: 插入dpu_nature_person_documents (正面)")
                    #插入dpu_person_doc(背面)
                    sql_dpu_nature_person_documents_back = f"""insert into `dpu_nature_person_documents` (`application_id`, `application_unique_id`, `content_file_type`,`create_by`, `created_at`, `doc_name`, `doc_type`, `entity_id`, `file_content`, `file_url`, `id`, `last_update_on`,`merchant_id`, `nature_person_id`, `status`, `update_by`, `updated_at`) 
                                                values ('f5208fb77d8d4712a436b716331cb6b9','{application_unique_id}', 'IMG', NULL, '2026-01-22 02:23:06', 'PRC ID-Back@3x-DPHeKKi2.png', 'DIRECTOR_ID_BACK','{ids['entity_id']}', NULL, 'uploads/default/default/default/file_20260122102247_a65a2d41c9c3.png', '{ids['doc_back']}',NULL, '{merchant_id}', '1f4479db-b9ef-4cce-aa45-9871753a2a1c', 'NEW', NULL, '2026-01-22 02:23:06')"""
                    check_and_execute(executor, sql_dpu_nature_person_documents_back, "Step 15: 插入dpu_nature_person_documents (背面)")

                    # --- 🥚🥚🥚插入 dpu_merchants_limit ---
                    sql_dpu_merchants_limit = f"""UPDATE `dpu_merchants_limit` 
                                                                SET 
                                                                `activated_limit` = '{approvedLimit}',
                                                                `activated_limit_update_at` = '2026-01-16 15:48:39',
                                                                `application_flow` = 'main',
                                                                `approved_limit` = '{approvedLimit}',
                                                                `approved_limit_update_at` = '2026-01-16 14:19:09',
                                                                `available_limit` = '{approvedLimit}',
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
                    check_and_execute(executor, sql_dpu_merchants_limit, "Step 16：更新dpu_merchants_limit")
                    # --- 🥚🥚🥚 插入 dpu_bank_account ---
                    sql_dpu_bank_account = f"""INSERT INTO `dpu_bank_account` (
                                                                            `bank_account_name`, 
                                                                            `bank_account_number`, 
                                                                            `bank_code`, 
                                                                            `bank_name`, 
                                                                            `bank_status`, 
                                                                            `branch_code`, 
                                                                            `created_at`, 
                                                                            `created_by`, 
                                                                            `effective_from`, 
                                                                            `effective_to`, 
                                                                            `id`, 
                                                                            `last_drawdown_at`, 
                                                                            `last_update_on`, 
                                                                            `merchant_id`, 
                                                                            `phone_number`, 
                                                                            `status`, 
                                                                            `swift_code`, 
                                                                            `updated_at`, 
                                                                            `updated_by`,
                                                                            `bank_address`
                                                                        ) VALUES (
                                                                            '{Bank_account_Name}', 
                                                                            '{Bank_account_Number}', 
                                                                            '{Branch_Code}', 
                                                                            '{Bank_account}',
                                                                            NULL, 
                                                                            NULL, 
                                                                            '2026-01-22 10:40:05', 
                                                                            '1039000002', 
                                                                            '2026-01-22 10:40:05', 
                                                                            '2026-01-22 10:40:05',  
                                                                            '{ids['random_id']}', 
                                                                            NULL, 
                                                                            X'35382e3135322e3131382e3637', 
                                                                            '{merchant_id}', 
                                                                            '19073511039', 
                                                                            'PRIMARY', 
                                                                            '{Swift_Code}', 
                                                                            '2026-01-22 10:40:05', 
                                                                            NULL,
                                                                            '{Bank_account_Number_address}'
                                                                        )"""
                    check_and_execute(executor, sql_dpu_bank_account, "Step 17：插入dpu_bank_account")
                    # --- 🥚🥚🥚 插入/更新 dpu_notify_event_dependency  ---
                    # 先查询是否已存在该 biz_id 的记录
                    res_event_dep = check_and_execute(executor,
                        f"SELECT * FROM dpu_notify_event_dependency WHERE biz_id = '{application_unique_id}'",
                        "Step 18: 查询dpu_notify_event_dependency是否存在")

                    existing_event_dep = res_event_dep['data'] if res_event_dep['data'] else []

                    # 定义要插入的4条记录数据
                    event_dep_records = [
                        {
                            'name': '第一条',
                            'dependency_type': 'AMAZON_3PL_SP_DATA_ALIGNMENT',
                            'event_type': 'FP_FIRST_KYC_START',
                            'event_id': ids['sql9_10_id'],
                            'record_id': ids['random_id']
                        },
                        {
                            'name': '第二条',
                            'dependency_type': 'OWS_SANCTIONS_SCREENING',
                            'event_type': 'FP_FIRST_KYC_START',
                            'event_id': ids['sql9_10_id'],
                            'record_id': ids['random_id1']
                        },
                        {
                            'name': '第三条',
                            'dependency_type': 'AMAZON_3PL_SP_DATA_ALIGNMENT',
                            'event_type': 'FP_FIRST_CREDIT_MODEL_START',
                            'event_id': ids['sql11_12_id'],
                            'record_id': ids['random_id2']
                        },
                        {
                            'name': '第四条',
                            'dependency_type': 'OWS_SANCTIONS_SCREENING',
                            'event_type': 'FP_FIRST_CREDIT_MODEL_START',
                            'event_id': ids['sql11_12_id'],
                            'record_id': ids['random_id3']
                        }
                    ]

                    step_num = 19
                    for record in event_dep_records:
                        # 检查是否已存在相同 event_type + dependency_type 的记录
                        exists = False
                        existing_id = None
                        for row in existing_event_dep:
                            # row结构: id, event_id, event_type, biz_id, dependency_type, ...
                            if row[3] == application_unique_id and row[7] == record['event_type'] and row[4] == record['dependency_type']:
                                exists = True
                                existing_id = row[0]
                                break

                        if exists:
                            # 存在则更新
                            sql_update = f"""UPDATE `dpu_notify_event_dependency`
                                SET `dependency_value` = 'READY',
                                    `dependency_status` = 'READY',
                                    `event_id` = '{record['event_id']}',
                                    `update_time` = '2026-01-22 02:40:05'
                                WHERE `id` = '{existing_id}'"""
                            check_and_execute(executor, sql_update, f"Step {step_num}：更新dpu_notify_event_dependency ({record['name']})")
                        else:
                            # 不存在则插入
                            sql_insert = f"""INSERT INTO `dpu_notify_event_dependency`
                                (`biz_id`, `create_time`, `dependency_finish_time`, `dependency_status`,
                                 `dependency_type`, `dependency_value`, `event_id`, `event_type`, `ext_json`, `id`, `update_time`)
                                VALUES ('{application_unique_id}', '2026-01-22 02:40:05', NULL, 'READY',
                                        '{record['dependency_type']}', 'READY', '{record['event_id']}', '{record['event_type']}',
                                        NULL, '{record['record_id']}', '2026-01-22 02:40:05')"""
                            check_and_execute(executor, sql_insert, f"Step {step_num}：插入dpu_notify_event_dependency ({record['name']})")
                        step_num += 1

                    # --- 🥚🥚🥚 插入/更新 dpu_notify_event  ---
                    # 先查询是否已存在该 biz_id 的记录
                    res_event = check_and_execute(executor,
                        f"SELECT * FROM dpu_notify_event WHERE biz_id = '{application_unique_id}'",
                        f"Step {step_num}: 查询dpu_notify_event是否存在")

                    existing_events = res_event['data'] if res_event['data'] else []
                    step_num += 1

                    # 定义要插入的3条记录数据
                    event_records = [
                        {
                            'name': '第一条',
                            'event_type': 'FP_FIRST_CREDIT_MODEL_START',
                            'record_id': ids['notify_id_1']
                        },
                        {
                            'name': '第二条',
                            'event_type': 'FP_FIRST_KYC_START',
                            'record_id': ids['notify_id_2']
                        },
                        {
                            'name': '第三条',
                            'event_type': 'FP_2K_ESIGN_DRAWDOWN_START',
                            'record_id': ids['notify_id_3']
                        }
                    ]

                    for record in event_records:
                        # 检查是否已存在相同 event_type 的记录
                        exists = False
                        existing_id = None
                        for row in existing_events:
                            # row结构: id, event_type, biz_id, ...
                            if row[2] == application_unique_id and row[1] == record['event_type']:
                                exists = True
                                existing_id = row[0]
                                break

                        if exists:
                            # 存在则更新
                            sql_update = f"""UPDATE `dpu_notify_event`
                                SET `notify_status` = 'SUCCESS',
                                    `retry_count` = 0,
                                    `update_time` = '2026-01-22 02:40:05'
                                WHERE `id` = '{existing_id}'"""
                            check_and_execute(executor, sql_update, f"Step {step_num}：更新dpu_notify_event ({record['name']})")
                        else:
                            # 不存在则插入
                            sql_insert = f"""INSERT INTO `dpu_notify_event`
                                (`biz_id`, `create_time`, `event_type`, `ext_json`, `id`, `next_retry_time`,
                                 `notify_status`, `retry_count`, `update_time`)
                                VALUES ('{application_unique_id}', '2026-01-22 02:40:05', '{record['event_type']}',
                                        NULL, '{record['record_id']}', NULL, 'SUCCESS', 0, '2026-01-22 02:40:05')"""
                            check_and_execute(executor, sql_insert, f"Step {step_num}：插入dpu_notify_event ({record['name']})")
                        step_num += 1
                    # --- 🥚🥚🥚 插入 dpu_credit_offer  ---
                    sql_dpu_credit_offer = f"""insert into `dpu_credit_offer` (`application_id`, `application_unique_id`, `approved_limit_amount`, 
                                    `approved_limit_currency`, `approveofferfailure_reason`, `base_rate`, `base_rate_type`, `created_at`, `created_by`,
                                    `e_sign_status`, `esign_failure_reason`, `fee_or_charge_amount`, `fee_or_charge_currency`, `fee_or_charge_date`,
                                    `fee_or_charge_type`, `finance_product`, `fixed_rate`, `id`, `lender_approved_offer_id`, `lender_code`,
                                    `lender_company_id`, `lender_credit_id`, `limit_application_id`, `margin_rate`, `max_tenor`, `merchant_id`,
                                    `min_tenor`, `offer_end_date`, `offer_start_date`, `offer_term`, `offer_term_unit`, `rate_type`, `signed_limit_amount`,
                                    `signed_limit_currency`, `status`, `updated_at`, `updated_by`, `warter_mark_amount`, `warter_mark_currency`) values 
                                    ('{application_id}', '{application_unique_id}', '{approvedLimit}', 'USD', NULL, '{baseRate}', 'SOFR',
                                    '2026-01-16 11:33:29', 'SYSTEM', 'SUCCESS', NULL, '0.00', 'USD', '2023-10-16', 'PROCESSING_FEE', 'LINE_OF_CREDIT',
                                    NULL, '{ids['credit_offer_id']}', '{lender_approved_offer_id}', 'FUNDPARK', '{lender_company_id}', '{lender_credit_id}',
                                    '{ids['limit_application_id']}', '{marginRate}', 24, '{merchant_id}', 3, '2024-10-15', '2023-10-16',
                                    12, 'Months', 'Float', '{signedLimit}', 'USD', 'ACCEPTED', '2026-01-16 15:48:39', 'SYSTEM', '0.00', 'USD')"""
                    check_and_execute(executor, sql_dpu_credit_offer, "Step 24：插入dpu_credit_offer")

                    # --- 🥚🥚🥚插入 dpu_limit_application  ---
                    sql_dpu_limit_application = f"""insert into `dpu_limit_application` (`activated_limit`, `available_limit`, `create_by`, `created_at`, `currency`,
                                    `id`, `last_update_on`, `lender_code`, `limit_application_unique_id`, `merchant_id`, `previous_activated_limit`,
                                    `previous_approved_limit`, `previous_available_limit`, `previous_signed_limit`, `previous_underwritten_limit`,
                                    `product`, `status`, `underwritten_limit`, `update_by`, `updated_at`) values (NULL, NULL, 'SYSTEM',
                                    '2026-01-16 11:32:31', 'USD', '{ids['random_limit_application_unique_id']}', X'0a0a83ee', 'FUNDPARK', '{ids['limit_application_unique_id']}',
                                    '{merchant_id}', NULL, NULL, NULL, NULL, NULL, 'LINE_OF_CREDIT', 'ACCEPTED', '{underwrittenAmount}',
                                    '5058000001', '2026-01-16 14:19:17')"""
                    check_and_execute(executor, sql_dpu_limit_application, "Step 25：插入dpu_limit_application")

                    # --- 🥚🥚🥚插入 dpu_limit_application_account  ---  ---
                    sql_dpu_limit_application_account = f"""insert into `dpu_limit_application_account` (
                                                                                                        `activated_limit`, 
                                                                                                        `approved_limit`, 
                                                                                                        `authorization_id`, 
                                                                                                        `create_by`, 
                                                                                                        `created_at`, 
                                                                                                        `currency`, 
                                                                                                        `frozen_limit`, 
                                                                                                        `id`, 
                                                                                                        `indicative_limit`, 
                                                                                                        `last_update_on`, 
                                                                                                        `limit_application_id`, 
                                                                                                        `limit_application_unique_id`, 
                                                                                                        `merchant_account_id`, 
                                                                                                        `merchant_id`, 
                                                                                                        `psp_status`, 
                                                                                                        `signed_limit`, 
                                                                                                        `underwritten_limit`, 
                                                                                                        `update_by`, 
                                                                                                        `updated_at`, 
                                                                                                        `utilization_limit`) 
                                                                                                        values
                                                                                                         (
                                                                                                        '{approvedLimit}', 
                                                                                                        '{approvedLimit}', 
                                                                                                        '{amazon_seller_id}',
                                                                                                        'SYSTEM', 
                                                                                                        '2026-01-16 19:32:31', 
                                                                                                        NULL, 
                                                                                                        NULL, 
                                                                                                        '{ids['random_id_LAA']}', 
                                                                                                        '0.00', 
                                                                                                        X'0a0a83ee', 
                                                                                                        '{ids['limit_application_id']}',
                                                                                                        '{ids['limit_application_unique_id']}', 
                                                                                                        '{merchant_account_id}', 
                                                                                                        '{merchant_id}', 
                                                                                                        'INITIAL', 
                                                                                                        '{signedLimit}', 
                                                                                                        '{underwrittenAmount}', 
                                                                                                        'SYSTEM', 
                                                                                                        '2026-01-16 22:18:51', 
                                                                                                        NULL)"""
                    check_and_execute(executor, sql_dpu_limit_application_account, "Step 26：插入sql_dpu_limit_application_account")

                    # --- 🥚🥚🥚插入 dpu_drawdown  ---
                    #第一笔提现记录
                    sql_dpu_drawdown_1 = f"""insert into `dpu_drawdown` (
                                                        `account_name`,
                                                        `account_number`,
                                                        `account_platform`,
                                                        `actual_drawdown_date`,
                                                        `bank_address`,
                                                        `base_interest_rate`,
                                                        `base_rate_type`,
                                                        `branch_code`,
                                                        `charge_bases`,
                                                        `created_at`,
                                                        `currency`,
                                                        `drawdown_amount`,
                                                        `drawdown_complete_datetime`,
                                                        `drawdown_failed_reason`,
                                                        `drawdown_start_datetime`,
                                                        `drawdown_submit_datetime`,
                                                        `fee_or_charge_amount`,
                                                        `fee_or_charge_currency`,
                                                        `fee_or_charge_date`,
                                                        `fee_or_charge_type`,
                                                        `finance_product`,
                                                        `fixed_rate`,
                                                        `id`,
                                                        `lender_approved_offer_id`,
                                                        `lender_code`,
                                                        `lender_drawdown_id`,
                                                        `lender_id`,
                                                        `lender_loan_id`,
                                                        `loan_id`,
                                                        `margin_interest_rate`,
                                                        `marketplace_country`,
                                                        `merchant_id`,
                                                        `new_repayment_date`,
                                                        `outstanding_amount`,
                                                        `overdue_days`,
                                                        `phone_number`,
                                                        `repayment_method`,
                                                        `repayment_status`,
                                                        `repayment_term`,
                                                        `status`,
                                                        `swift_code`,
                                                        `tenor`,
                                                        `term`,
                                                        `term_unit`,
                                                        `total_interest_rate`,
                                                        `updated_at`)
                                                        values 
                                                        ('{Bank_account_Name}',
                                                        '{Bank_account_Number}',
                                                        '{Bank_account}',
                                                        '2026-01-26 00:00:00',
                                                        '{Bank_account_Number_address}',
                                                        '6.000000',
                                                        'SOFR',
                                                        '{Branch_Code}',
                                                        'Float',
                                                        '2026-02-03 19:54:48',
                                                        'USD',
                                                        '{drawdown_amount_1}',
                                                        '2026-01-26 00:00:00',
                                                        NULL,
                                                        '2026-02-03 19:54:48',
                                                        '2026-02-03 19:54:48',
                                                        '{marginRate}',
                                                        'USD',
                                                        '2023-10-16 00:00:00',
                                                        'PROCESSING_FEE',
                                                        'LINE_OF_CREDIT',
                                                        NULL,
                                                        '{ids['random_id']}',
                                                        '{lender_approved_offer_id}',
                                                        'FUNDPARK',
                                                        'DRA1',
                                                        NULL,
                                                        'lender-{ids['loan_id']}',
                                                        '{ids['loan_id']}',
                                                        '0.000000',
                                                        NULL,
                                                        '{merchant_id}',
                                                        '2026-04-26',
                                                        '{drawdown_amount_1}',
                                                        NULL,
                                                        NULL,
                                                        'ANYTIME',
                                                        'OUTSTANDING',
                                                        '90',
                                                        'APPROVED',
                                                        '{Swift_Code}',
                                                        NULL,
                                                        120,
                                                        'Days',
                                                        '6.000000',
                                                        '2026-02-03 19:54:54')"""
                    check_and_execute(executor, sql_dpu_drawdown_1, "Step 27: 向dpu_drawdown插入第一笔提现记录")
                    #第二笔提现记录
                    sql_dpu_drawdown_2 = f"""insert into `dpu_drawdown` (
                                                                            `account_name`,
                                                                            `account_number`,
                                                                            `account_platform`,
                                                                            `actual_drawdown_date`,
                                                                            `bank_address`,
                                                                            `base_interest_rate`,
                                                                            `base_rate_type`,
                                                                            `branch_code`,
                                                                            `charge_bases`,
                                                                            `created_at`,
                                                                            `currency`,
                                                                            `drawdown_amount`,
                                                                            `drawdown_complete_datetime`,
                                                                            `drawdown_failed_reason`,
                                                                            `drawdown_start_datetime`,
                                                                            `drawdown_submit_datetime`,
                                                                            `fee_or_charge_amount`,
                                                                            `fee_or_charge_currency`,
                                                                            `fee_or_charge_date`,
                                                                            `fee_or_charge_type`,
                                                                            `finance_product`,
                                                                            `fixed_rate`,
                                                                            `id`,
                                                                            `lender_approved_offer_id`,
                                                                            `lender_code`,
                                                                            `lender_drawdown_id`,
                                                                            `lender_id`,
                                                                            `lender_loan_id`,
                                                                            `loan_id`,
                                                                            `margin_interest_rate`,
                                                                            `marketplace_country`,
                                                                            `merchant_id`,
                                                                            `new_repayment_date`,
                                                                            `outstanding_amount`,
                                                                            `overdue_days`,
                                                                            `phone_number`,
                                                                            `repayment_method`,
                                                                            `repayment_status`,
                                                                            `repayment_term`,
                                                                            `status`,
                                                                            `swift_code`,
                                                                            `tenor`,
                                                                            `term`,
                                                                            `term_unit`,
                                                                            `total_interest_rate`,
                                                                            `updated_at`)
                                                                            values 
                                                                            ('{Bank_account_Name}',
                                                                            '{Bank_account_Number}',
                                                                            '{Bank_account}',
                                                                            '2026-01-26 00:00:00',
                                                                            '{Bank_account_Number_address}',
                                                                            '6.000000',
                                                                            'SOFR',
                                                                            '{Branch_Code}',
                                                                            'Float',
                                                                            '2026-02-03 19:54:48',
                                                                            'USD',
                                                                            '{drawdown_amount_2}',
                                                                            '2026-01-26 00:00:00',
                                                                            NULL,
                                                                            '2026-02-03 19:54:48',
                                                                            '2026-02-03 19:54:48',
                                                                            '{marginRate}',
                                                                            'USD',
                                                                            '2023-10-16 00:00:00',
                                                                            'PROCESSING_FEE',
                                                                            'LINE_OF_CREDIT',
                                                                            NULL,
                                                                            '{ids['random_id1']}',
                                                                            '{lender_approved_offer_id}',
                                                                            'FUNDPARK',
                                                                            'DRA1',
                                                                            NULL,
                                                                            'lender-{ids['loan_id1']}',
                                                                            '{ids['loan_id1']}',
                                                                            '0.000000',
                                                                            NULL,
                                                                            '{merchant_id}',
                                                                            '2026-04-26',
                                                                            '{drawdown_amount_2}',
                                                                            NULL,
                                                                            NULL,
                                                                            'ANYTIME',
                                                                            'OUTSTANDING',
                                                                            '90',
                                                                            'APPROVED',
                                                                            '{Swift_Code}',
                                                                            NULL,
                                                                            120,
                                                                            'Days',
                                                                            '6.000000',
                                                                            '2026-02-03 19:54:54')"""
                    check_and_execute(executor, sql_dpu_drawdown_2, "Step 28: 向dpu_drawdown插入第二笔提现记录")

                    # 更新第一笔借款的--utilization_limit--available_limit-
                    if (drawdown_amount_1 is not None and str(drawdown_amount_1).strip() != '' and
                            repayment_1_principal is not None and str(repayment_1_principal).strip() != ''):
                        available_limit_1 = float(available_limit) - float(drawdown_amount_1) + float(
                            repayment_1_principal)  # 第一笔借款完成之后--可用提现金额
                        print('available_limit_1为', available_limit_1)
                        try:
                            # 第一笔提现记录dpu_credit_transaction
                            sql_dpu_credit_transaction_1 = f"""insert into `dpu_credit_transaction` (
                                                                                    `activated_limit`, 
                                                                                    `activated_limit_update_at`, 
                                                                                    `approved_limit`, 
                                                                                    `approved_limit_update_at`, 
                                                                                    `available_limit`, 
                                                                                    `available_limit_update_at`, 
                                                                                    `charge_bases`, 
                                                                                    `created_at`, 
                                                                                    `currency`, 
                                                                                    `effective_to`, 
                                                                                    `finance_product`, 
                                                                                    `frozen_limit`, 
                                                                                    `frozen_limit_update_at`, 
                                                                                    `id`, 
                                                                                    `indicative_limit`, 
                                                                                    `indicative_limit_update_at`, 
                                                                                    `lender_code`, 
                                                                                    `lender_id`, 
                                                                                    `margin_rate`, 
                                                                                    `merchant_id`, 
                                                                                    `rate_type`, 
                                                                                    `reason_code`, 
                                                                                    `reason_id`, 
                                                                                    `signed_limit`, 
                                                                                    `signed_limit_update_at`, 
                                                                                    `underwritten_limit`, 
                                                                                    `underwritten_limit_update_at`, 
                                                                                    `updated_at`, 
                                                                                    `utilization_limit`, 
                                                                                    `utilization_limit_update_at`
                                                                                ) 
                                                                                values (
                                                                                    '{approvedLimit}', 
                                                                                    '2026-01-16 23:48:39', 
                                                                                    '{approvedLimit}', 
                                                                                    '2026-01-16 22:19:09', 
                                                                                    '{available_limit_1}', 
                                                                                    '2026-01-16 23:48:39', 
                                                                                    'Float', 
                                                                                    '2026-02-05 19:31:50', 
                                                                                    'USD', 
                                                                                    NULL, 
                                                                                    'LINE_OF_CREDIT', 
                                                                                    '{drawdown_amount_1}', 
                                                                                    '2026-02-05 19:31:50', 
                                                                                    '{ids['random_id']}', 
                                                                                    '240000.00', 
                                                                                    '2026-02-03 18:12:32', 
                                                                                    'FUNDPARK', 
                                                                                    NULL, 
                                                                                    '{marginRate}', 
                                                                                    '{merchant_id}', 
                                                                                    'SOFR', 
                                                                                    301, 
                                                                                    '{ids['random_id1']}', 
                                                                                    '{signedLimit}', 
                                                                                    '2026-01-16 23:48:39', 
                                                                                    '{underwrittenAmount}', 
                                                                                    '2026-01-16 22:19:09', 
                                                                                    '2026-02-05 19:31:50', 
                                                                                    NULL, 
                                                                                    NULL
                                                                                )"""
                            check_and_execute(executor, sql_dpu_credit_transaction_1,
                                              "Step 29: 向sql_dpu_credit_transaction插入第一笔提现记录--frozen_limit更新")
                            sql_dpu_credit_transaction_2 = f"""insert into `dpu_credit_transaction` (
                                                                                                        `activated_limit`, 
                                                                                                        `activated_limit_update_at`, 
                                                                                                        `approved_limit`, 
                                                                                                        `approved_limit_update_at`, 
                                                                                                        `available_limit`, 
                                                                                                        `available_limit_update_at`, 
                                                                                                        `charge_bases`, 
                                                                                                        `created_at`, 
                                                                                                        `currency`, 
                                                                                                        `effective_to`, 
                                                                                                        `finance_product`, 
                                                                                                        `frozen_limit`, 
                                                                                                        `frozen_limit_update_at`, 
                                                                                                        `id`, 
                                                                                                        `indicative_limit`, 
                                                                                                        `indicative_limit_update_at`, 
                                                                                                        `lender_code`, 
                                                                                                        `lender_id`, 
                                                                                                        `margin_rate`, 
                                                                                                        `merchant_id`, 
                                                                                                        `rate_type`, 
                                                                                                        `reason_code`, 
                                                                                                        `reason_id`, 
                                                                                                        `signed_limit`, 
                                                                                                        `signed_limit_update_at`, 
                                                                                                        `underwritten_limit`, 
                                                                                                        `underwritten_limit_update_at`, 
                                                                                                        `updated_at`, 
                                                                                                        `utilization_limit`, 
                                                                                                        `utilization_limit_update_at`
                                                                                                    ) 
                                                                                                    values (
                                                                                                        '{approvedLimit}', 
                                                                                                        '2026-01-16 23:48:39', 
                                                                                                        '{approvedLimit}', 
                                                                                                        '2026-01-16 22:19:09', 
                                                                                                        '{available_limit_1}', 
                                                                                                        '2026-01-16 23:48:39', 
                                                                                                        'Float', 
                                                                                                        '2026-02-05 19:31:50', 
                                                                                                        'USD', 
                                                                                                        NULL, 
                                                                                                        'LINE_OF_CREDIT', 
                                                                                                        '', 
                                                                                                        '2026-02-05 19:31:50', 
                                                                                                        '{ids['random_id1']}', 
                                                                                                        '240000.00', 
                                                                                                        '2026-02-03 18:12:32', 
                                                                                                        'FUNDPARK', 
                                                                                                        NULL, 
                                                                                                        '{marginRate}', 
                                                                                                        '{merchant_id}', 
                                                                                                        'SOFR', 
                                                                                                        301, 
                                                                                                        '{ids['random_id1']}', 
                                                                                                        '{signedLimit}', 
                                                                                                        '2026-01-16 23:48:39', 
                                                                                                        '{underwrittenAmount}', 
                                                                                                        '2026-01-16 22:19:09', 
                                                                                                        '2026-02-05 19:31:50', 
                                                                                                        '{drawdown_amount_1}', 
                                                                                                        NULL
                                                                                                    )"""
                            check_and_execute(executor, sql_dpu_credit_transaction_2,
                                              "Step 30: 向sql_dpu_credit_transaction插入第二笔提现记录--utilization_limit更新")
                            # 更新dpu_merchants_limit表 utilization_limit和available_limit
                            sql_dpu_merchants_limit = f"""update `dpu_merchants_limit` 
                                                            set 
                                                                `utilization_limit` = '{drawdown_amount_1}',
                                                                `available_limit` = '{available_limit_1}',
                                                                `updated_at` = now()
                                                            where 
                                                                `merchant_id` = '{merchant_id}'
                                                            """
                            check_and_execute(executor, sql_dpu_merchants_limit,
                                              "Step 35: 更新dpu_merchants_limit表 utilization_limit和available_limit")
                        except ValueError as e:
                            print(f"转换错误: {e}")
                        return available_limit_1
                    else:
                        print("Step 35: drawdown_amount_1为空，跳过更新dpu_merchants_limit记录")

                    # 处理第二笔借款的还款金额（确保非空字符串才能转换）
                    repayment_2_principal_num = float(repayment_2_principal) if (repayment_2_principal is not None and str(repayment_2_principal).strip()) else 0

                    # 更新第二笔借款的--utilization_limit--available_limit-
                    if (drawdown_amount_1 is not None and str(drawdown_amount_1).strip() != '' and
                        drawdown_amount_2 is not None and str(drawdown_amount_2).strip() != ''):
                        # 第二笔借款完成之后--可用提现金额
                        available_limit_2 = float(available_limit_1) - float(drawdown_amount_2) + repayment_2_principal_num
                        print('available_limit_2为', available_limit_2)
                        utilization_limit_2 = float(drawdown_amount_2) + float(drawdown_amount_1)
                        try:
                            # 第二笔提现记录dpu_credit_transaction
                            sql_dpu_credit_transaction_10 = f"""insert into `dpu_credit_transaction` (
                                                                                    `activated_limit`, 
                                                                                    `activated_limit_update_at`, 
                                                                                    `approved_limit`, 
                                                                                    `approved_limit_update_at`, 
                                                                                    `available_limit`, 
                                                                                    `available_limit_update_at`, 
                                                                                    `charge_bases`, 
                                                                                    `created_at`, 
                                                                                    `currency`, 
                                                                                    `effective_to`, 
                                                                                    `finance_product`, 
                                                                                    `frozen_limit`, 
                                                                                    `frozen_limit_update_at`, 
                                                                                    `id`, 
                                                                                    `indicative_limit`, 
                                                                                    `indicative_limit_update_at`, 
                                                                                    `lender_code`, 
                                                                                    `lender_id`, 
                                                                                    `margin_rate`, 
                                                                                    `merchant_id`, 
                                                                                    `rate_type`, 
                                                                                    `reason_code`, 
                                                                                    `reason_id`, 
                                                                                    `signed_limit`, 
                                                                                    `signed_limit_update_at`, 
                                                                                    `underwritten_limit`, 
                                                                                    `underwritten_limit_update_at`, 
                                                                                    `updated_at`, 
                                                                                    `utilization_limit`, 
                                                                                    `utilization_limit_update_at`
                                                                                ) 
                                                                                values (
                                                                                    '{approvedLimit}', 
                                                                                    '2026-01-16 23:48:39', 
                                                                                    '{approvedLimit}', 
                                                                                    '2026-01-16 22:19:09', 
                                                                                    '{available_limit_2}', 
                                                                                    '2026-01-16 23:48:39', 
                                                                                    'Float', 
                                                                                    '2026-02-05 19:31:50', 
                                                                                    'USD', 
                                                                                    NULL, 
                                                                                    'LINE_OF_CREDIT', 
                                                                                    '{drawdown_amount_2}', 
                                                                                    '2026-02-05 19:31:50', 
                                                                                    '{ids['random_id2']}', 
                                                                                    '240000.00', 
                                                                                    '2026-02-03 18:12:32', 
                                                                                    'FUNDPARK', 
                                                                                    NULL, 
                                                                                    '{marginRate}', 
                                                                                    '{merchant_id}', 
                                                                                    'SOFR', 
                                                                                    301, 
                                                                                    '{ids['random_id2']}', 
                                                                                    '{signedLimit}', 
                                                                                    '2026-01-16 23:48:39', 
                                                                                    '{underwrittenAmount}', 
                                                                                    '2026-01-16 22:19:09', 
                                                                                    '2026-02-05 19:31:50', 
                                                                                    NULL, 
                                                                                    NULL
                                                                                )"""
                            check_and_execute(executor, sql_dpu_credit_transaction_10,
                                              "Step 31: 向sql_dpu_credit_transaction插入第二笔提现记录--frozen_limit更新")
                            sql_dpu_credit_transaction_11 = f"""insert into `dpu_credit_transaction` (
                                                                                                        `activated_limit`, 
                                                                                                        `activated_limit_update_at`, 
                                                                                                        `approved_limit`, 
                                                                                                        `approved_limit_update_at`, 
                                                                                                        `available_limit`, 
                                                                                                        `available_limit_update_at`, 
                                                                                                        `charge_bases`, 
                                                                                                        `created_at`, 
                                                                                                        `currency`, 
                                                                                                        `effective_to`, 
                                                                                                        `finance_product`, 
                                                                                                        `frozen_limit`, 
                                                                                                        `frozen_limit_update_at`, 
                                                                                                        `id`, 
                                                                                                        `indicative_limit`, 
                                                                                                        `indicative_limit_update_at`, 
                                                                                                        `lender_code`, 
                                                                                                        `lender_id`, 
                                                                                                        `margin_rate`, 
                                                                                                        `merchant_id`, 
                                                                                                        `rate_type`, 
                                                                                                        `reason_code`, 
                                                                                                        `reason_id`, 
                                                                                                        `signed_limit`, 
                                                                                                        `signed_limit_update_at`, 
                                                                                                        `underwritten_limit`, 
                                                                                                        `underwritten_limit_update_at`, 
                                                                                                        `updated_at`, 
                                                                                                        `utilization_limit`, 
                                                                                                        `utilization_limit_update_at`
                                                                                                    ) 
                                                                                                    values (
                                                                                                        '{approvedLimit}', 
                                                                                                        '2026-01-16 23:48:39', 
                                                                                                        '{approvedLimit}', 
                                                                                                        '2026-01-16 22:19:09', 
                                                                                                        '{available_limit_2}', 
                                                                                                        '2026-01-16 23:48:39', 
                                                                                                        'Float', 
                                                                                                        '2026-02-05 19:31:50', 
                                                                                                        'USD', 
                                                                                                        NULL, 
                                                                                                        'LINE_OF_CREDIT', 
                                                                                                        '', 
                                                                                                        '2026-02-05 19:31:50', 
                                                                                                        '{ids['random_id3']}', 
                                                                                                        '240000.00', 
                                                                                                        '2026-02-03 18:12:32', 
                                                                                                        'FUNDPARK', 
                                                                                                        NULL, 
                                                                                                        '{marginRate}', 
                                                                                                        '{merchant_id}', 
                                                                                                        'SOFR', 
                                                                                                        301, 
                                                                                                        '{ids['random_id3']}', 
                                                                                                        '{signedLimit}', 
                                                                                                        '2026-01-16 23:48:39', 
                                                                                                        '{underwrittenAmount}', 
                                                                                                        '2026-01-16 22:19:09', 
                                                                                                        '2026-02-05 19:31:50', 
                                                                                                        '{drawdown_amount_2}', 
                                                                                                        NULL
                                                                                                    )"""
                            check_and_execute(executor, sql_dpu_credit_transaction_11,
                                              "Step 32: 向sql_dpu_credit_transaction插入第二笔提现记录--utilization_limit更新")
                            # 更新dpu_merchants_limit表 utilization_limit和available_limit
                            sql_dpu_merchants_limit = f"""update `dpu_merchants_limit` 
                                                        set 
                                                            `utilization_limit` = '{utilization_limit_2}',
                                                            `available_limit` = '{available_limit_2}',
                                                            `updated_at` = now()
                                                        where 
                                                            `merchant_id` = '{merchant_id}'
                                                        """
                            check_and_execute(executor, sql_dpu_merchants_limit,
                                              "Step 36: 更新dpu_merchants_limit表 utilization_limit和available_limit")
                        except ValueError as e:
                            print(f"转换错误: {e}")
                    else:
                        print("Step 36: drawdown_amount_2为空，跳过插入dpu_drawdown记录")

                    #第二笔还款记录dpu_credit_transaction
                    sql_dpu_credit_transaction_20 = f"""insert into `dpu_credit_transaction` (
                                                                            `activated_limit`,
                                                                            `activated_limit_update_at`,
                                                                            `approved_limit`,
                                                                            `approved_limit_update_at`,
                                                                            `available_limit`,
                                                                            `available_limit_update_at`,
                                                                            `charge_bases`,
                                                                            `created_at`,
                                                                            `currency`,
                                                                            `effective_to`,
                                                                            `finance_product`,
                                                                            `frozen_limit`,
                                                                            `frozen_limit_update_at`,
                                                                            `id`,
                                                                            `indicative_limit`,
                                                                            `indicative_limit_update_at`,
                                                                            `lender_code`,
                                                                            `lender_id`,
                                                                            `margin_rate`,
                                                                            `merchant_id`,
                                                                            `rate_type`,
                                                                            `reason_code`,
                                                                            `reason_id`,
                                                                            `signed_limit`,
                                                                            `signed_limit_update_at`,
                                                                            `underwritten_limit`,
                                                                            `underwritten_limit_update_at`,
                                                                            `updated_at`,
                                                                            `utilization_limit`,
                                                                            `utilization_limit_update_at`
                                                                        )
                                                                        values (
                                                                            '{approvedLimit}',
                                                                            '2026-01-16 23:48:39',
                                                                            '{approvedLimit}',
                                                                            '2026-01-16 22:19:09',
                                                                            '{available_limit_1}',
                                                                            '2026-01-16 23:48:39',
                                                                            'Float',
                                                                            '2026-02-05 19:31:50',
                                                                            'USD',
                                                                            NULL,
                                                                            'LINE_OF_CREDIT',
                                                                            '{drawdown_amount_1}',
                                                                            '2026-02-05 19:31:50',
                                                                            '{ids['random_id4']}',
                                                                            '240000.00',
                                                                            '2026-02-03 18:12:32',
                                                                            'FUNDPARK',
                                                                            NULL,
                                                                            '{marginRate}',
                                                                            '{merchant_id}',
                                                                            'SOFR',
                                                                            301,
                                                                            '{ids['random_id4']}',
                                                                            '{signedLimit}',
                                                                            '2026-01-16 23:48:39',
                                                                            '{underwrittenAmount}',
                                                                            '2026-01-16 22:19:09',
                                                                            '2026-02-05 19:31:50',
                                                                            NULL,
                                                                            NULL
                                                                        )"""
                    check_and_execute(executor, sql_dpu_credit_transaction_20, "Step 33: 向sql_dpu_credit_transaction插入第二笔提现记录--frozen_limit更新")
                    sql_dpu_credit_transaction_21 = f"""insert into `dpu_credit_transaction` (
                                                                                                `activated_limit`,
                                                                                                `activated_limit_update_at`,
                                                                                                `approved_limit`,
                                                                                                `approved_limit_update_at`,
                                                                                                `available_limit`,
                                                                                                `available_limit_update_at`,
                                                                                                `charge_bases`,
                                                                                                `created_at`,
                                                                                                `currency`,
                                                                                                `effective_to`,
                                                                                                `finance_product`,
                                                                                                `frozen_limit`,
                                                                                                `frozen_limit_update_at`,
                                                                                                `id`,
                                                                                                `indicative_limit`,
                                                                                                `indicative_limit_update_at`,
                                                                                                `lender_code`,
                                                                                                `lender_id`,
                                                                                                `margin_rate`,
                                                                                                `merchant_id`,
                                                                                                `rate_type`,
                                                                                                `reason_code`,
                                                                                                `reason_id`,
                                                                                                `signed_limit`,
                                                                                                `signed_limit_update_at`,
                                                                                                `underwritten_limit`,
                                                                                                `underwritten_limit_update_at`,
                                                                                                `updated_at`,
                                                                                                `utilization_limit`,
                                                                                                `utilization_limit_update_at`
                                                                                            )
                                                                                            values (
                                                                                                '{approvedLimit}',
                                                                                                '2026-01-16 23:48:39',
                                                                                                '{approvedLimit}',
                                                                                                '2026-01-16 22:19:09',
                                                                                                '{available_limit_1}',
                                                                                                '2026-01-16 23:48:39',
                                                                                                'Float',
                                                                                                '2026-02-05 19:31:50',
                                                                                                'USD',
                                                                                                NULL,
                                                                                                'LINE_OF_CREDIT',
                                                                                                '',
                                                                                                '2026-02-05 19:31:50',
                                                                                                '{ids['random_id5']}',
                                                                                                '240000.00',
                                                                                                '2026-02-03 18:12:32',
                                                                                                'FUNDPARK',
                                                                                                NULL,
                                                                                                '{marginRate}',
                                                                                                '{merchant_id}',
                                                                                                'SOFR',
                                                                                                301,
                                                                                                '{ids['random_id5']}',
                                                                                                '{signedLimit}',
                                                                                                '2026-01-16 23:48:39',
                                                                                                '{underwrittenAmount}',
                                                                                                '2026-01-16 22:19:09',
                                                                                                '2026-02-05 19:31:50',
                                                                                                '{drawdown_amount_1}',
                                                                                                NULL
                                                                                            )"""
                    check_and_execute(executor, sql_dpu_credit_transaction_21, "Step 34: 向sql_dpu_credit_transaction插入第二笔提现记录--utilization_limit更新")
    except Exception as e:
        log.error(f"处理数据时出错: {e}")

if __name__ == '__main__':
    file_path = r"D:\data\project\test\input_data.csv"
    run_application(file_path)
