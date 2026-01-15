# -*- coding: utf-8 -*-
import logging
import time
import uuid
from typing import Optional, Dict, Any, Callable

import pymysql
import requests
from pymysql.constants import CLIENT
from pymysql.err import OperationalError

# ============================ 基础配置 ============================
ENV = "uat"

# 保留原始完整配置结构（无任何修改）
AUTO_CONFIG = {
    "underwritten_amount": "500000",  # 核保额度（字符串类型）
    "underwritten_status": "APPROVED",
    "approved_amount": 500000.00,  # 审批额度（浮点型）
    "approved_status": "APPROVED",
    "psp_start_status": "PROCESSING",
    "psp_completed_status": "SUCCESS",
    "esign_amount": 500000.00,  # 电子签额度（浮点型）
    "esign_status": "SUCCESS",
    "step_interval": 10,
}

# 日志配置（仅调整格式，不修改日志级别）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


# ============================ 工具函数（完全保留原始逻辑） ============================
def generate_uuid37() -> str:
    """生成37位UUID（原始逻辑）"""
    return str(uuid.uuid4())


def validate_phone(phone: str) -> bool:
    """验证手机号"""
    return phone.isdigit() and len(phone) in [8, 11]


def get_utc_time() -> str:
    """获取标准UTC时间（原始格式）"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_local_time_str() -> str:
    """获取lastUpdatedOn字段要求的格式（原始逻辑）"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def input_with_validate(prompt: str, validator: Callable[[str], bool], err_msg: str) -> str:
    """带验证输入（原始逻辑）"""
    while True:
        user_input = input(prompt).strip()
        if validator(user_input):
            return user_input
        log.error(err_msg)


# ============================ 数据库配置（完全保留原始逻辑） ============================
class DBConfig:
    _CONFIG_MAP = {
        "sit": {"host": "18.162.145.173", "user": "dpu_sit", "password": "20250818dpu_sit",
                "database": "dpu_seller_center"},
        "dev": {"host": "aurora-dpu-dev.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com", "user": "dpu_dev",
                "password": "J9IUmPpD@Hon8Y#v", "database": "dpu_seller_center"},
        "uat": {"host": "aurora-dpu-uat.cluster-cv2aqqmyo5k9.ap-east-1.rds.amazonaws.com", "user": "dpu_uat",
                "password": "6S[a=u.*Z;Zt~b&-A4|Ma&q^w8r_3vz[", "database": "dpu_seller_center"},
        "preprod": {"host": "43.199.241.190", "user": "dpu_preprod", "password": "OWBSNfx8cC5c#Or0",
                    "database": "dpu_seller_center"},
        "local": {"host": "localhost", "user": "root", "password": "root", "database": "dpu_seller_center"}
    }

    @classmethod
    def get_config(cls, env: str = ENV) -> Dict[str, Any]:
        config = cls._CONFIG_MAP.get(env)
        if not config:
            raise ValueError(f"不支持的环境：{env}")
        return {**config, "port": 3306, "charset": "utf8mb4", "connect_timeout": 15}


class DBExecutor:
    """数据库执行器（完全保留原始逻辑）"""

    def __init__(self, env: str = ENV):
        self.config = DBConfig.get_config(env)
        self.conn: Optional[pymysql.Connection] = None
        self.cursor: Optional[pymysql.Cursor] = None
        self._connect()

    def _connect(self) -> None:
        try:
            self.conn = pymysql.connect(**self.config, autocommit=True, client_flag=CLIENT.INTERACTIVE)
            self.cursor = self.conn.cursor()
            log.info("✅ 数据库连接成功")
        except Exception as e:
            log.error(f"❌ 数据库连接失败: {e}")
            raise

    def query_one(self, sql: str) -> Optional[Any]:
        try:
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            return result[0] if result else None
        except OperationalError as e:
            log.error(f"❌ SQL执行失败: {e}, SQL: {sql[:100]}")
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        log.info("✅ 数据库连接已关闭")


# ============================ API配置（完全保留原始逻辑） ============================
class ApiConfig:
    def __init__(self, env: str = ENV):
        base_url_map = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "local": "http://192.168.11.3:8080"
        }
        self.base_url = base_url_map[env]
        self.webhook_url = f"{self.base_url}/dpu-openapi/webhook-notifications"


# ============================ 核心服务（仅修改流程控制，请求体完全保留） ============================
class DPUAutoService:
    def __init__(self, phone: str, db_executor: DBExecutor):
        self.phone = phone
        self.db = db_executor
        self.api = ApiConfig()

        # 完全保留原始数据库查询逻辑
        self.merchant_id = self._get_merchant_id()
        self.dpu_auth_token_seller_id = self._get_dpu_auth_token_seller_id()
        self.dpu_limit_application_id = self._get_dpu_limit_application_id()
        self.application_unique_id = self._get_application_unique_id()
        self.lender_approved_offer_id = f"lender-{self.application_unique_id}" if self.application_unique_id else "lender-default"

        if not self.merchant_id:
            raise ValueError(f"❌ 手机号{phone}未查询到merchant_id")
        log.info(f"✅ 初始化完成 | 手机号: {phone} | MerchantID: {self.merchant_id}")

    # 完全保留原始数据库查询方法
    def _get_merchant_id(self) -> Optional[str]:
        sql = f"""
            SELECT merchant_id FROM dpu_users 
            WHERE phone_number = '{self.phone}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db.query_one(sql)

    def _get_dpu_auth_token_seller_id(self) -> Optional[str]:
        if not self.merchant_id:
            return None
        sql = f"""
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = '{self.merchant_id}' 
            AND authorization_party = 'SP' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db.query_one(sql)

    def _get_dpu_limit_application_id(self) -> Optional[str]:
        if not self.merchant_id:
            return None
        sql = f"""
            SELECT limit_application_unique_id FROM dpu_limit_application 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db.query_one(sql)

    def _get_application_unique_id(self) -> Optional[str]:
        if not self.merchant_id:
            return None
        sql = f"""
            SELECT application_unique_id FROM dpu_application 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db.query_one(sql)

    # 完全保留原始请求发送逻辑（确保接口请求不报错）
    def _send_webhook_request(self, request_body: Dict[str, Any], step_name: str) -> bool:
        """完全保留原始请求逻辑，仅新增日志"""
        log.info(f"\n🚀 发送{step_name}请求")
        try:
            # 保留原始请求头（关键！确保接口不报错）
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            response = requests.post(
                self.api.webhook_url,
                json=request_body,
                headers=headers,
                timeout=30
            )
            if response.status_code == 200:
                log.info(f"✅ {step_name} 请求成功 - 响应: {response.text[:100]}...")
                return True
            log.error(f"❌ {step_name} 失败 | 状态码: {response.status_code} | 响应: {response.text[:200]}...")
            return False
        except Exception as e:
            log.error(f"❌ {step_name} 异常: {e}")
            return False

    def _wait_for_interval(self, step_name: str):
        """保留原始等待逻辑"""
        log.info(f"\n⏳ 等待{AUTO_CONFIG['step_interval']}秒后执行{step_name}...")
        time.sleep(AUTO_CONFIG['step_interval'])

    # ------------------------------ 完全保留原始核保请求体 ------------------------------
    def run_underwritten(self) -> bool:
        request_body = {
            "data": {
                "eventType": "underwrittenLimit.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "核保完成通知",
                "enquiryUrl": "https://api.example.com/enquiry/123",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "dpuMerchantAccountId": [
                        {"MerchantAccountId": self.dpu_auth_token_seller_id}] if self.dpu_auth_token_seller_id else [],
                    "dpuLimitApplicationId": self.dpu_limit_application_id,
                    "originalRequestId": "req_EFAL17621784619057169",
                    "status": AUTO_CONFIG["underwritten_status"],
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system",
                    "lenderLoanId": "lloan_6001",
                    "lenderRepaymentScheduled": "lrs_7001",
                    "lenderCreditId": "lcredit_8001",
                    "lenderRepaymentId": "lrepay_9001",
                    "credit": {
                        "marginRate": "2.5",
                        "chargeBases": "Fixed",
                        "baseRate": "3.5",
                        "baseRateType": "FIXED",
                        "eSign": "PENDING",
                        "creditLimit": {
                            "currency": "CNY",
                            "underwrittenAmount": {"currency": "CNY", "amount": AUTO_CONFIG["underwritten_amount"]},
                            "availableLimit": {"currency": "CNY", "amount": "0.00"},
                            "signedLimit": {"currency": "CNY", "amount": "0.00"},
                            "watermark": {"currency": "CNY", "amount": "0.00"}
                        }
                    }
                }
            }
        }
        return self._send_webhook_request(request_body, "核保(underwritten)")

    # ------------------------------ 完全保留原始审批请求体 ------------------------------
    def run_approved(self) -> bool:
        request_body = {
            "data": {
                "eventType": "approvedoffer.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "Application approval process completed successfully",
                "enquiryUrl": "https://api.lender.com/enquiry/12345",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "dpuApplicationId": self.application_unique_id,
                    "originalRequestId": " ",
                    "status": AUTO_CONFIG["approved_status"],
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system",
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "offer": {
                        "rate": {
                            "chargeBases": "Float",
                            "baseRateType": "SOFR",
                            "baseRate": "0.05",
                            "marginRate": "0.02",
                            "fixedRate": "0.07"
                        },
                        "term": 12,
                        "termUnit": "Months",
                        "mintenor": 3,
                        "maxtenor": 24,
                        "offerEndDate": "2024-10-15",
                        "offerStartDate": "2023-10-16",
                        "approvedLimit": {"currency": "USD", "amount": AUTO_CONFIG["approved_amount"]},
                        "warterMark": {"currency": "USD", "amount": 0.00},
                        "signedLimit": {"currency": "USD", "amount": 0.00},
                        "feeOrCharge": {
                            "type": "PROCESSING_FEE",
                            "feeOrChargeDate": "2023-10-16",
                            "netAmount": {"currency": "USD", "amount": 0.00}
                        }
                    }
                }
            }
        }
        return self._send_webhook_request(request_body, "审批(approved)")

    # ------------------------------ 完全保留原始PSP开始请求体 ------------------------------
    def run_psp_start(self) -> bool:
        request_body = {
            "data": {
                "eventType": "psp.verification.started",
                "eventId": generate_uuid37(),
                "eventMessage": "PSP验证已开始",
                "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                "datetime": get_utc_time(),
                "applicationId": "EFA17590311621044381",
                "details": {
                    "pspId": "pspId123457",
                    "pspName": "AirWallex",
                    "merchantAccountId": self.dpu_auth_token_seller_id,
                    "merchantId": self.merchant_id,
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "result": AUTO_CONFIG["psp_start_status"],
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system_psp"
                }
            }
        }
        return self._send_webhook_request(request_body, "PSP开始(psp_start)")

    # ------------------------------ 完全保留原始PSP完成请求体 ------------------------------
    def run_psp_completed(self) -> bool:
        request_body = {
            "data": {
                "eventType": "psp.verification.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "PSP验证已完成",
                "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                "datetime": get_utc_time(),
                "applicationId": "EFA17590311621044381",
                "details": {
                    "pspId": "pspId123457",
                    "pspName": "AirWallex",
                    "merchantAccountId": self.dpu_auth_token_seller_id,
                    "merchantId": self.merchant_id,
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "result": AUTO_CONFIG["psp_completed_status"],
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system_psp"
                }
            }
        }
        return self._send_webhook_request(request_body, "PSP完成(psp_completed)")

    # ------------------------------ 完全保留原始电子签请求体 ------------------------------
    def run_esign(self) -> bool:
        request_body = {
            "data": {
                "eventType": "esign.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "电子签章已完成",
                "enquiryUrl": "https://api.example.com/enquiry/esign/456",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "result": AUTO_CONFIG["esign_status"],
                    "failureReason": None,
                    "signedLimit": {"amount": AUTO_CONFIG["esign_amount"], "currency": "USD"},
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "esign_system"
                }
            }
        }
        return self._send_webhook_request(request_body, "电子签(esign)")

    # ------------------------------ 主流程（仅新增审批后人工确认，其他完全保留） ------------------------------
    def run_full_flow(self):
        log.info("\n" + "=" * 60)
        log.info("🎯 开始DPU自动化流程（500K额度）")
        log.info("=" * 60)

        # 1. 核保（保留原始逻辑）
        if not self.run_underwritten():
            log.error("❌ 核保失败，流程终止")
            return
        self._wait_for_interval("审批")

        # 2. 审批（保留原始逻辑）
        if not self.run_approved():
            log.error("❌ 审批失败，流程终止")
            return

        # ===== 仅新增这部分：审批成功后人工确认，替代等待10秒 =====
        log.info("\n📌 审批请求已成功（200响应），准备开始PSP流程")
        while True:
            user_input = input("🔍 是否确认开始PSP开始(psp_start)请求？输入1继续：").strip()
            if user_input == "1":
                log.info("✅ 确认开始PSP流程")
                break
            log.warning("⚠️ 请输入1确认继续，其他输入无效！")
        # =========================================================

        # 3. PSP开始（保留原始逻辑）
        if not self.run_psp_start():
            log.error("❌ PSP开始失败，流程终止")
            return
        self._wait_for_interval("PSP完成")

        # 4. PSP完成（保留原始逻辑）
        if not self.run_psp_completed():
            log.error("❌ PSP完成失败，流程终止")
            return
        self._wait_for_interval("电子签")

        # 5. 电子签（保留原始逻辑）
        if not self.run_esign():
            log.error("❌ 电子签失败，流程终止")
            return

        log.info("\n" + "=" * 60)
        log.info("🎉 所有流程执行完成！")
        log.info(f"📱 手机号: {self.phone} | 💰 额度: 500K")
        log.info("=" * 60)


# ============================ 辅助函数（完全保留原始逻辑） ============================
def check_phone_registered(phone: str, db: DBExecutor) -> bool:
    """原始校验逻辑"""
    try:
        # 校验merchant_id
        sql = f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' LIMIT 1;"
        merchant_id = db.query_one(sql)
        if not merchant_id:
            log.error(f"❌ 手机号 {phone} 未注册")
            return False

        # 校验3PL授权
        sql = f"""
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = '{merchant_id}' 
            AND authorization_party = '3PL' 
            ORDER BY created_at DESC LIMIT 1;
        """
        offer_id = db.query_one(sql)
        if offer_id:
            log.info(f"✅ 手机号 {phone} 已注册 | OfferID: {offer_id}")
        else:
            log.warning(f"⚠️ 手机号 {phone} 已注册，但无3PL授权记录")

        return True
    except Exception as e:
        log.error(f"❌ 查询注册状态失败: {e}")
        return False


# ============================ 主函数（完全保留原始逻辑） ============================
def main():
    log.info(f"📢 DPU自动化工具 | 环境: {ENV}")
    log.info("🔧 流程: 核保→审批→[人工确认]→PSP开始→PSP完成→电子签")

    with DBExecutor() as db:
        # 输入手机号
        phone = input_with_validate(
            prompt="\n请输入已注册手机号：",
            validator=lambda x: validate_phone(x) and check_phone_registered(x, db),
            err_msg="❌ 请输入有效的已注册手机号（8/11位数字）！"
        )

        # 执行流程
        try:
            service = DPUAutoService(phone, db)
            service.run_full_flow()
        except Exception as e:
            log.error(f"❌ 流程异常: {e}")

    log.info("\n👋 程序执行完毕")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n⚠️ 程序被用户中断")
    except Exception as e:
        log.error(f"❌ 程序异常退出: {e}")
        exit(1)