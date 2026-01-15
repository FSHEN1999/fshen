# author:yeZh date:2025/9/27
# -*- coding: utf-8 -*-
import logging
import aiohttp
import pymysql
import requests
from enum import Enum
from faker import Faker
from pymysql.constants import CLIENT

ENV = "uat"  # "sit" or "local" or "dev" or "uat"

is_register_new_account = False
#is_register_new_account = True



steps = {
    "200k": """
            1.approved offer 
            2.更新esign状态
            3.更新放款状态
            4.underwritten 
            5.approved offer
            6.psp_start
            7.psp completed
            8.更新esign状态
            9.更新放款状态""",
    "500k-2M": """
            1.underwritten 
            2.approved offer
            3.psp_start
            4.psp completed
            5.更新esign状态
            6.更新放款状态""",
}

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]  %(lineno)s  %(funcName)s  %(message)s")
log = logging.getLogger(__name__)
faker = Faker("zh_CN")


class SanctionStatus(Enum):
    """application表，制裁状态：'HIT','NOT_HIT','PENDING'"""
    HIT = 'HIT'
    NOT_HIT = 'NOT_HIT'
    PENDING = 'PENDING'


class DPUStatus(Enum):
    """psp esign为SUCCESS/FAIL 其余的为APPROVED/REJECTED"""
    INITIAL = 'INITIAL'
    SUBMITTED = 'SUBMITTED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    PROCESSING = "PROCESSING"


class ExecuteSql:
    database_config_dict = {
        "sit": {
            "host": "18.162.145.173",  # 数据库地址
            "user": "dpu_sit",  # 用户名
            "password": "20250818dpu_sit",  # 密码
            "database": "dpu_seller_center",  # 数据库名
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,  # 连接超时
            "read_timeout": 15,  # 读取数据超时
        },
        "dev": {
            "host": "aurora-dpu-dev.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",  # 数据库地址
            "user": "dpu_dev",  # 用户名
            "password": "J9IUmPpD@Hon8Y#v",  # 密码
            "database": "dpu_seller_center",  # 数据库名
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,  # 连接超时
            "read_timeout": 15,  # 读取数据超时
        },
        "uat": {
            "host": "aurora-dpu-uat.cluster-cv2aqqmyo5k9.ap-east-1.rds.amazonaws.com",  # 数据库地址
            "user": "dpu_uat",  # 用户名
            "password": "6S[a=u.*Z;Zt~b&-A4|Ma&q^w8r_3vz[",  # 密码
            "database": "dpu_seller_center",  # 数据库名
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,  # 连接超时
            "read_timeout": 15,  # 读取数据超时
        },
        "preprod": {
            "host": "43.199.241.190",  # 数据库地址
            "user": "dpu_preprod",  # 用户名
            "password": "OWBSNfx8cC5c#Or0",  # 密码
            "database": "dpu_seller_center",  # 数据库名
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,  # 连接超时
            "read_timeout": 15,  # 读取数据超时
        }

    }
    database_config = database_config_dict.get(ENV)

    def __init__(self):
        self.config = ExecuteSql.database_config
        self.conn = pymysql.connect(**self.config, autocommit=True, client_flag=CLIENT.INTERACTIVE)
        self.cursor = self.conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def reconnect(self):
        try:
            if self.conn:
                self.conn.close()
            self.conn = pymysql.connect(**self.config, autocommit=True)
            self.cursor = self.conn.cursor()
            log.info("数据库重连成功")
        except Exception as e:
            log.error(f"数据库重连失败: {e}")

    def execute_sql(self, sql, retry=3):
        try:
            self.cursor.execute(sql)
            self.conn.commit()
            if sql.strip().lower().startswith("select"):
                return self.cursor.fetchall()[0][0] if self.cursor.rowcount > 0 else None
        except pymysql.err.OperationalError as e:
            if e.args[0] in (2006, 2013, 10054) and retry > 0:  # server has gone away / lost connection
                log.warning("连接失效，尝试重连中...")
                self.reconnect()
                return self.execute_sql(sql, retry - 1)
            else:
                log.error(f"SQL执行出错：{e}")
        return None


def get_login_token(phone_number, offer_id):
    # todo 待更新
    url = "https://sit.api.expressfinance.business.hsbc.com/dpu-user/auth/login"
    data = {
        "phone": phone_number,
        "areaCode": "+86",
        "code": "666666",
        "offerId": offer_id
    }
    resp_login = requests.post(url, json=data)
    if resp_login.status_code == 200:
        return resp_login.json().get("data").get("token")
    else:
        log.error("登录失败,{}".format(resp_login.json()))
        exit(1)


class MockDpuStatus:
    seller_id = ''

    def __init__(self, phone_number, executor, ):
        self.phone_number = phone_number
        self.executor = executor
        self.merchant_id = self.get_merchant_id()

    @staticmethod
    def create_offer_id(journey: str, ):
        journey_amount = {
            "200K": 100000,
            "500K": 800000,
            "2000K": 6000000
        }
        yearly_repayment_amount = journey_amount.get(journey.upper())
        if not yearly_repayment_amount:
            log.error("error journey input...")
            return None

        payload = {"yearlyRepaymentAmount": yearly_repayment_amount}

        resp_create_offer_id = requests.post(url=CREATE_OFFERID_URL, json=payload)
        if resp_create_offer_id.status_code == 200:
            resp_json = resp_create_offer_id.json()
            offer_id = resp_json.get("data").get("amazon3plOfferId")
            return offer_id
        else:
            log.error(f"create offer_id error : response code {resp_create_offer_id.status_code}...")
            return None

    @staticmethod
    def register_new_account():
        journey_number = {
            "1": "200K",
            "2": "500K",
            "3": "2000K"
        }
        while True:
            input_ = input("请输入要注册的流程：1-200K 2-500K 3-2000K \n").strip()
            if input_ in ["1", "2", "3"]:
                journey = journey_number.get(input_)
                break
            else:
                log.error("输入错误，请重新输入！")
        log.info("开始注册新账号...")
        phone_number = faker.phone_number()
        email = f"{phone_number}y@163.com"
        offer_id = MockDpuStatus.create_offer_id(journey, )

        register_payload = {
            "phone": phone_number,
            "areaCode": "+86",
            "code": "666666",
            "email": email,
            "offerId": offer_id
        }
        redirect_url = REDIRECT_URL + "?offerId=" + offer_id
        # login_url = LOGIN_URL + "?offerId=" + offer_id
        try:
            # sit需要重定向，目前dev不要 todo
            resp_redirect = requests.get(url=redirect_url, )
            if resp_redirect.status_code == 200:
                log.info(f"[{phone_number}] journey: {journey} 重定向成功")
            else:
                log.error(f"[{phone_number}] journey: {journey} 重定向失败 ...{resp_redirect.json()}")

            resp_register = requests.post(REGISTER_URL, json=register_payload, )
            if resp_register.status_code == 200:
                # 写入txt
                with open(txt_path, 'a', newline='', encoding='utf-8') as f:
                    # 写入txt
                    f.write("\n" + journey + "\n" + phone_number + "\n" + redirect_url + "\n\n")
                    log.info(f"journey: {journey} [{phone_number}] 注册成功，已写入{txt_path}...")
                return phone_number
            else:
                log.error(
                    f"[{phone_number}] journey: {journey} 注册失败, status_code: {resp_register.status_code}  正在重新注册...")
                return MockDpuStatus.register_new_account()

        except Exception as e:
            log.error(f"[{phone_number}] -- journey: {journey} 注册失败... : {e}")

    def mock_spapi_auth(self, ):
        # seller_id名称逻辑 第一家店1/第二家店2... + BTC6RWJD + phone_number
        while True:
            number = input(
                "请输入要为第几家店进行spapi认证: 1-first shop 2-add second shop 3-add third shop ...：\n").strip()
            if number.isdigit() and int(number) >= 1:
                break
            else:
                log.error("输入错误，请重新输入！")
        log.info("正在进行spapi认证...")
        seller_id = number + "BTC6RWJD" + self.phone_number
        payload = {
            "phone": self.phone_number,
            "status": "ACTIVE",
            "dpu_token": "dpu_token",
            "sellerId": seller_id,
            "authorization_code": "authorization_code",
            "refresh_token_expires_time": "2025-09-19T10:09:07.921Z",
            "access_token": "access_token sunt",
            "refresh_token": "refresh_token minim et anim sunt"
        }
        response = requests.post(url=SPAPI_AUTH_URL, json=payload, auth=None)
        if response.json().get("code") == 200:
            log.info("spapi授权回调成功...")
            MockDpuStatus.seller_id = seller_id
        else:
            log.error("spapi授权回调失败...")

    def mock_link_sp_3pl_shop(self):
        log.info("开始关联spapi和3pl店铺...")
        response = requests.post(url=LINK_SAP_3PL_URL, params={"phone": self.phone_number})
        if response.json().get("code") == 200:
            log.info("关联spapi和3pl店铺成功...")
        else:
            log.error("关联spapi和3pl店铺失败...")

    def get_merchant_id(self):
        """根据手机号查询dpu_user表获取merchant_id"""
        sql = f"select merchant_id from dpu_users where phone_number = '{self.phone_number}'"
        merchant_id = self.executor.execute_sql(sql)
        return merchant_id

    def get_platform_offer_id(self, seller_id):
        """根据seller_id查询dpu_manual_offer表获取重定向的platform_offer_id"""
        sql = f"SELECT platform_offer_id FROM dpu_manual_offer WHERE platform_seller_id = '{seller_id}';"
        platform_offer_id = self.executor.execute_sql(sql)
        return platform_offer_id

    @property
    def get_merchant_account_id(self):
        sql = f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id= '{self.merchant_id}' ORDER BY created_at DESC;"
        merchant_account_id = self.executor.execute_sql(sql)
        return merchant_account_id

    @property
    def get_application_unique_id(self, ):
        """获取业务id,根据merchant_id查询dpu_application表获取application_unique_id"""
        sql = f"select application_unique_id from dpu_application where merchant_id = '{self.merchant_id}' order by created_at desc;"
        application_unique_id = self.executor.execute_sql(sql)
        return application_unique_id

    @property
    def get_lender_approved_offer_id(self, ):
        return f"lender-{self.get_application_unique_id}"

    @property
    def get_lender_loan_id(self, ):
        return f"lender-{self.get_dpu_loan_id}"

    @property
    def get_dpu_loan_id(self, ):
        """mock drawdown请求时使用，获取dpuLoanId，查dpu_drawdown表，对应loan_id"""
        sql = f"select loan_id from dpu_drawdown where merchant_id = '{self.merchant_id}' order by created_at desc"
        dpu_loan_id = self.executor.execute_sql(sql)
        return dpu_loan_id

    @property
    def get_dpu_limit_application_id(self, ):
        """根据merchant_id查询dpu_limit_application表获取limit_application_id"""
        sql = f"select limit_application_unique_id from dpu_limit_application where merchant_id = '{self.merchant_id}' order by created_at desc"
        dpu_limit_application_id = self.executor.execute_sql(sql)
        return dpu_limit_application_id

    @property
    def get_dpu_auth_token_seller_id(self):
        """根据merchant_id查询dpu_auth_token表获取seller_id"""
        sql = f"select authorization_id from dpu_auth_token where merchant_id = '{self.merchant_id}' order by created_at desc"
        dpu_auth_token_seller_id = self.executor.execute_sql(sql)
        return dpu_auth_token_seller_id

    def mock_sanction_status(self, ):
        """修改制裁状态 dpu_application表,当前默认NOT_HIT"""
        sanction_status = ''
        while True:
            input_ = input("请输入制裁状态对应的数字：1-NOT_HIT 2-HIT 3-PENDING \n").strip()
            match input_:
                case '1':
                    sanction_status = SanctionStatus.NOT_HIT.value
                    break
                case '2':
                    sanction_status = SanctionStatus.HIT.value
                    break
                case '3':
                    sanction_status = SanctionStatus.PENDING.value
                    break
                case _:
                    log.error("输入错误，请重新输入: ")
                    continue
        sql = f"UPDATE dpu_application set sanction_status='{sanction_status}' WHERE merchant_id={self.merchant_id}"
        self.executor.execute_sql(sql)

    def mock_approved_offer_status(self, journey: str = None, status: str = None):
        while True:
            approved_limit_amount = input("请输入授信额度：\n").strip()
            if approved_limit_amount.isdigit():
                approved_limit_amount = round(float(approved_limit_amount), 2)
                break
            log.error("请输入整数 \n")
        # 暂时不输这个参数
        signed_limit_amount = 0

        # while True:
        #     signed_limit_amount = input("请输入已签约额度：\n").strip()
        #     if signed_limit_amount.isdigit():
        #         signed_limit_amount = round(float(signed_limit_amount), 2)
        #         break
        #     log.error("请输入整数 \n")
        #     continue
        def approvedoffer_completed_request(param_approved_offer_status, param_approved_limit_amount,
                                            param_signed_limit_amount):
            request_body = {
                "data": {
                    "eventType": "approvedoffer.completed",
                    "eventId": "evt_12341567890",
                    "eventMessage": "Application approval process completed successfully",
                    "enquiryUrl": "https://api.lender.com/enquiry/12345",
                    "datetime": "2023-10-15T14:30:00",
                    "details": {
                        "merchantId": self.merchant_id,
                        "dpuApplicationId": self.get_application_unique_id,
                        "originalRequestId": "req_1111113579",
                        "status": param_approved_offer_status,
                        "failureReason": None,
                        "lenderApprovedOfferId": self.get_lender_approved_offer_id,
                        "offer": {
                            "rate": {
                                "baseRate": "0.05",
                                "marginRate": "0.02",
                                "fixedRate": "0.07"
                            },
                            "term": 12,
                            "termUnit": "Months",  # 1025 dev是小写 其他是大写
                            "mintenor": 3,
                            "maxtenor": 24,
                            "offerEndDate": "2024-10-15",
                            "offerStartDate": "2023-10-16",
                            "approvedLimit": {
                                "currency": "USD",
                                "amount": param_approved_limit_amount
                            },
                            "warterMark": {
                                "currency": "USD",
                                "amount": 0.00
                            },
                            "signedLimit": {
                                "currency": "USD",
                                "amount": param_signed_limit_amount
                            },
                            "feeOrCharge": {
                                "type": "PROCESSING_FEE",
                                "feeOrChargeDate": "2023-10-16",
                                "netAmount": {
                                    "currency": "USD",
                                    "amount": 0.00
                                }
                            }
                        }
                    }
                }
            }

            response = requests.post(url=WEBHOOK_URL, json=request_body, auth=None)
            if response.status_code == 200 and response.json().get("data") == {}:
                log.info("审批状态修改成功")
            else:
                log.error("审批状态修改失败")

        approved_offer_status = ''
        while True:
            input_ = input("请输入审批状态对应数字：1-APPROVED 2-REJECTED \n").strip()
            match input_:
                case '1':
                    approved_offer_status = DPUStatus.APPROVED.value
                    break
                case '2':
                    approved_offer_status = DPUStatus.REJECTED.value
                    break
                case _:
                    log.error("输入错误，请重新输入: ")
                    continue
        approvedoffer_completed_request(approved_offer_status, approved_limit_amount, signed_limit_amount)

    def mock_esign_status(self, ):
        """修改电子签状态 """
        while True:
            signed_limit_amount = input("请输入已签约额度：\n").strip()
            if signed_limit_amount.isdigit():
                signed_limit_amount = round(float(signed_limit_amount), 2)
                break
            log.error("请输入整数 \n")

        def esign_completed_request(param_esign_status, param_signed_limit):
            request_body = {
                "data": {
                    "eventType": "esign.completed",
                    "eventId": "evt_esign_789012",
                    "eventMessage": "电子签章已完成",
                    "enquiryUrl": "https://api.example.com/enquiry/esign/456",
                    "datetime": "2023-10-16T10:15:00Z",
                    "details": {
                        "merchantId": self.merchant_id,
                        "lenderApprovedOfferId": self.get_lender_approved_offer_id,
                        "result": param_esign_status,
                        "failureReason": None,
                        "signedLimit": {
                            "amount": param_signed_limit,
                            "currency": "USD"
                        },
                        "lastUpdatedOn": "2023-10-16T10:10:00Z",
                        "lastUpdatedBy": "esign_system"
                    }
                }
            }
            response = requests.post(url=WEBHOOK_URL, json=request_body, )
            if response.status_code == 200 and response.json().get("data") == {}:
                log.info("esign状态修改成功")
            else:
                log.error("esign状态修改失败")

        esign_status = ''
        while True:
            input_ = input("请输入电子签状态对应数字：1-SUCCESS 2-FAIL \n").strip()
            match input_:
                case '1':
                    esign_status = DPUStatus.SUCCESS.value
                    break
                case '2':
                    esign_status = DPUStatus.FAIL.value
                    break
                case _:
                    log.error("输入错误，请重新输入！")
                    continue
        esign_completed_request(esign_status, signed_limit_amount)

    def mock_drawdown_status(self, status: str = None, step: int = 0):
        """修改放款状态 dpu_drawdown表"""
        while True:
            drawdown_amount = input("请输入放款额度：\n").strip()
            if drawdown_amount.isdigit():
                break
            log.error("请输入整数！")

        def disbursement_completed_request(param_drawdown_status, param_drawdown_amount):
            # dpu_loan_id = self.get_dpu_loan_id
            request_body = {
                "data": {
                    "eventType": "disbursement.completed",
                    "eventId": "2f47d61e-5262-443a-9748-44cc679da07f",
                    "eventMessage": "Disbursement completed",
                    "enquiryUrl": "/loans?merchantId=01bab20c834747ed923b7162cfca79aa&loanId=LEND1",
                    "datetime": "2025-10-23T09:13:52Z",
                    "details": {
                        "merchantId": self.merchant_id,
                        "lenderApprovedOfferId": self.get_lender_approved_offer_id,
                        "dpuLoanId": self.get_dpu_loan_id,
                        "lenderLoanId": self.get_lender_loan_id,
                        "originalRequestId": "e37b91d056114e48a466b433934e2068",
                        "lenderCreditId": "CR1",
                        "lenderCompanyId": "LEND1",
                        "lenderDrawdownId": "DRA1",
                        "drawdownStatus": param_drawdown_status,
                        "lastUpdatedOn": "2025-10-23 09:13:52",
                        "lastUpdatedBy": "system",
                        "disbursement": {
                            "loanAmount": {
                                "currency": "USD",
                                "amount": param_drawdown_amount
                            },
                            "rate": {
                                "chargeBases": "Float",
                                "baseRateType": "SOFR",
                                "baseRate": "6.00",
                                "marginRate": "0.00"
                            },
                            "term": "120",
                            "termUnit": "Days",
                            "drawdownSuccessDate": "2025-10-23",
                            "actualDrawdownDate": "2025-10-23"
                        },
                        "repayment": {
                            "expectedRepaymentDate": "2026-01-21",
                            "expectedRepaymentAmount": {
                                "currency": "USD",
                                "amount": param_drawdown_amount
                            },
                            "repaymentTerm": "90"
                        }
                    }
                }
            }
            response = requests.post(url=WEBHOOK_URL, json=request_body, )
            if response.status_code == 200 and response.json().get("data") == {}:
                log.info("提款状态修改成功")
            else:
                log.error("提款状态修改失败")

        drawdown_status = ''
        while True:
            input_ = input("请输入放款状态对应数字：1-APPROVED 2-REJECTED \n").strip()
            match input_:
                case '1':
                    drawdown_status = DPUStatus.APPROVED.value
                    break
                case '2':
                    drawdown_status = DPUStatus.REJECTED.value
                    break
                case _:
                    log.error("输入错误，请重新输入: ")
                    continue
        disbursement_completed_request(drawdown_status, drawdown_amount)

    def mock_underwritten_status(self, status: str = None, step: int = 0):

        while True:
            underwritten_amount = input("请输入评估额度：\n").strip()
            if underwritten_amount.isdigit():
                break
            log.error("请输入整数 \n")

        def underwritten_request(param_underwritten_status, param_underwritten_amount, ):
            request_body = {
                "data": {
                    "eventType": "underwrittenLimit.completed",
                    "eventId": "evt_123456789",
                    "eventMessage": "核保完成通知",
                    "enquiryUrl": "https://api.example.com/enquiry/123",
                    "datetime": "2023-10-15T14:30:00Z",
                    "details": {
                        "merchantId": self.merchant_id,
                        "dpuMerchantAccountId": [],
                        "dpuLimitApplicationId": self.get_dpu_limit_application_id,
                        "originalRequestId": "req_50111101",
                        "status": param_underwritten_status,
                        "failureReason": None,
                        "lastUpdatedOn": "2023-10-15T14:25:00Z",
                        "lastUpdatedBy": "system",
                        "lenderLoanId": "lloan_6001",
                        "lenderRepaymentScheduled": "lrs_7001",
                        "lenderCreditId": "lcredit_8001",
                        "lenderRepaymentId": "lrepay_9001",
                        "credit": {
                            "marginRate": "2.5",
                            "baseRate": "3.5",
                            "baseRateType": "FIXED",
                            "eSign": "PENDING",
                            "creditLimit": {
                                "currency": "CNY",
                                "underwrittenAmount": {
                                    "currency": "CNY",
                                    "amount": param_underwritten_amount
                                },
                                "availableLimit": {
                                    "currency": "CNY",
                                    "amount": "0.00"
                                },
                                "signedLimit": {
                                    "currency": "CNY",
                                    "amount": "0.00"
                                },
                                "watermark": {
                                    "currency": "CNY",
                                    "amount": "0.00"
                                }
                            }
                        }
                    }
                }
            }
            response = requests.post(url=WEBHOOK_URL, json=request_body, auth=None)
            if response.status_code == 200 and response.json().get("data") == {}:
                log.info("额度评估成功")
            else:
                log.error("额度评估失败")

        underwritten_status = ''

        while True:
            input_ = input("请输入额度评估状态数字：1-APPROVED 2-REJECTED\n").strip()
            match input_:
                case '1':
                    underwritten_status = DPUStatus.APPROVED.value
                    break
                case '2':
                    underwritten_status = DPUStatus.REJECTED.value
                    break
                case _:
                    log.info("输入错误，请重新输入！")
                    continue
        underwritten_request(underwritten_status, underwritten_amount)

    def mock_create_psp_record(self, ):
        seller_id = MockDpuStatus.seller_id
        params = {
            "authorizationId": seller_id,
            "pspId": "PSP" + seller_id
        }
        response = requests.post(url=CREATE_PSP_AUTH_URL, params=params, auth=None)
        if response.status_code == 200:
            log.info("创建psp授权记录成功...")
        else:
            log.error("创建psp授权记录失败...")

    def mock_psp_start_status(self, ):
        """修改psp开始状态 """

        def psp_verification_started_request(param_psp_start_status):
            request_body = {
                "data": {
                    "eventType": "psp.verification.started",
                    "eventId": "evt_psp_start_123456",
                    "eventMessage": "PSP验证已开始",
                    "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                    "datetime": "2023-10-15T15:30:00Z",
                    "applicationId": "EFA17590311621044381",
                    "details": {
                        "pspId": "pspId123457",
                        "pspName": "AirWallex",
                        "merchantAccountId": self.get_dpu_auth_token_seller_id,
                        "merchantId": self.merchant_id,
                        "lenderApprovedOfferId": self.get_lender_approved_offer_id,
                        "result": param_psp_start_status,
                        "failureReason": None,
                        "lastUpdatedOn": "2023-10-15T15:25:00Z",
                        "lastUpdatedBy": "system_psp"
                    }
                }
            }
            response = requests.post(url=WEBHOOK_URL, json=request_body, )
            if response.status_code == 200 and response.json().get("data") == {}:
                log.info(f"psp验证开始状态修改成功  {param_psp_start_status}...")
            else:
                log.error("psp验证开始状态修改失败 ...")

        psp_start_status = ''
        while True:
            input_ = input("请输入修改psp开始状态对应数字：1-PROCESSING 2-FAIL 3-INITIAL \n").strip()
            match input_:
                case '1':
                    psp_start_status = DPUStatus.PROCESSING.value
                    break
                case '2':
                    psp_start_status = DPUStatus.FAIL.value
                    break
                case '3':
                    psp_start_status = DPUStatus.INITIAL.value
                    break
                case _:
                    log.error("输入错误，请重新输入！")
                    continue
        psp_verification_started_request(psp_start_status)

    def mock_psp_completed_status(self, ):
        """修改psp完成状态 """

        def psp_verification_completed_request(param_psp_completed_status):
            request_body = {
                "data": {
                    "eventType": "psp.verification.completed",
                    "eventId": "evt_psp_start_123456",
                    "eventMessage": "PSP验证已开始",
                    "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                    "datetime": "2023-10-15T15:30:00Z",
                    "applicationId": "EFA17590311621044381",
                    "details": {
                        "pspId": "pspId123457",
                        "pspName": "AirWallex",
                        "merchantAccountId": self.get_dpu_auth_token_seller_id,
                        "merchantId": self.merchant_id,
                        "lenderApprovedOfferId": self.get_lender_approved_offer_id,
                        "result": param_psp_completed_status,
                        "failureReason": None,
                        "lastUpdatedOn": "2023-10-15T15:25:00Z",
                        "lastUpdatedBy": "system_psp"
                    }
                }
            }

            response = requests.post(url=WEBHOOK_URL, json=request_body, )
            if response.status_code == 200:
                log.info(f"psp验证完成状态修改成功  {param_psp_completed_status}")
            else:
                log.error(f"psp验证完成状态修改失败... status_code: {response.status_code}")

        psp_completed_status = ''
        while True:
            input_ = input("请输入修改psp完成状态对应数字：1-SUCCESS 2-FAIL 3-INITIAL \n").strip()
            match input_:
                case '1':
                    psp_completed_status = DPUStatus.SUCCESS.value
                    break
                case '2':
                    psp_completed_status = DPUStatus.FAIL.value
                    break
                case '3':
                    psp_completed_status = DPUStatus.INITIAL.value
                    break
                case _:
                    log.error("输入错误，请重新输入！")
                    continue
        psp_verification_completed_request(psp_completed_status)

    def redirect_3pl(self):
        while True:
            input_ = input("请输入是为第几家店进行3pl:\n").strip()
            if input_.isdigit() and int(input_) in range(1, 7):
                break
            else:
                log.error("输入无效，请重新输入！")
        seller_id = input_ + "BTC6RWJD" + self.phone_number
        log.info("正在进行3pl认证...")
        try:
            response = requests.get(url=REDIRECT_URL, params={"offerId": self.get_platform_offer_id(seller_id)})
            if response.status_code == 200:
                log.info(f"第{input_}家店3pl重定向成功")
            else:
                log.error(f"第{input_}家店3pl重定向失败，response.status_code: {response.status_code}")
        except Exception as e:
            log.error(f"第{input_}家店3pl重定向失败，错误信息：{e}")


def is_registered(phone_number, executor):
    try:
        sql = f"select merchant_id from dpu_users where phone_number = '{phone_number}';"
        merchant_id = executor.execute_sql(sql)
        sql_ = f"select application_unique_id from dpu_application where merchant_id = '{merchant_id}' order by created_at desc limit 1;"
        application_unique_id = executor.execute_sql(sql_)
        if application_unique_id:
            log.info(f"请核对业务Id:{application_unique_id}")
            return True
        log.error("请核对业务Id")
        if merchant_id:
            return True

    except Exception as e:
        log.error(f"查询失败，请检查手机号是否正确，错误信息：{e}")
        return False


def run():
    with ExecuteSql() as executor:
        if is_register_new_account:
            phone_number = MockDpuStatus.register_new_account()

        else:
            while True:
                phone_number = input("请输入手机号：\n").strip()
                if phone_number.isdigit() and len(phone_number) == 11:
                    if is_registered(phone_number, executor):
                        break
                else:
                    log.error("输入无效，请重新输入11位数字的手机号: ")
                    continue
        mock_dpu_status = MockDpuStatus(phone_number, executor)
        while True:
            operator = input(
                "请输入回调的接口：1-spapi授权回调  2-link-sp-3pl 3-underwritten 4-approved  5-create_psp_record "
                "6-psp_start 7-psp_completed 8-esign 9-drawdown 10-add store 3pl q-quit \n").strip()
            match operator:
                case "0":
                    mock_dpu_status.register_new_account()
                    continue
                case "1":
                    mock_dpu_status.mock_spapi_auth()
                    continue
                case "2":
                    mock_dpu_status.mock_link_sp_3pl_shop()
                    continue
                case "3":
                    mock_dpu_status.mock_underwritten_status()
                    continue
                case "4":
                    mock_dpu_status.mock_approved_offer_status()
                    continue
                case "5":
                    mock_dpu_status.mock_create_psp_record()
                case "6":
                    mock_dpu_status.mock_psp_start_status()
                    continue
                case "7":
                    mock_dpu_status.mock_psp_completed_status()
                    continue
                case "8":
                    mock_dpu_status.mock_esign_status()
                    continue
                case "9":
                    mock_dpu_status.mock_drawdown_status()
                    continue
                case "10":
                    mock_dpu_status.redirect_3pl()
                case "q":
                    log.info("已退出...")
                    break
                case _:
                    log.error("输入无效，请重新输入：")
                    continue


if __name__ == '__main__':
    BASE_URL_DICT = {
        "sit": "https://sit.api.expressfinance.business.hsbc.com",
        "dev": "https://dpu-gateway-dev.dowsure.com",
        "uat": "https://uat.api.expressfinance.business.hsbc.com",
        "local": "http://192.168.11.3:8080"
    }
    BASE_URL = BASE_URL_DICT.get(ENV)
    CREATE_OFFERID_URL = f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance"
    REDIRECT_URL = f"https://dpu-gateway-{ENV}.dowsure.com/dpu-merchant/amazon/redirect"
    if ENV == "uat":
        REDIRECT_URL = f"https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amazon/redirect"
    REGISTER_URL = f"{BASE_URL}/dpu-user/auth/signup"  # 后端api
    LOGIN_URL = f"{BASE_URL}/en/login"
    SPAPI_AUTH_URL = f"{BASE_URL}/dpu-merchant/amz/sp/shop/auth"
    LINK_SAP_3PL_URL = f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops"
    CREATE_PSP_AUTH_URL = f"{BASE_URL}/dpu-openapi/test/create-psp-auth-token"
    WEBHOOK_URL = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    txt_path_dict = {
        "sit": "./register_sit.txt",
        "dev": "./register_dev.txt",
        "uat": "./register_uat.txt",
        "local": "./register_local.txt"
    }
    txt_path = txt_path_dict.get(ENV)

    run()
