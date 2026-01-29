# -*- coding: utf-8 -*-
import logging
import time
import uuid
import contextlib
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass

import pymysql
import requests
from pymysql.constants import CLIENT
from pymysql.err import OperationalError, ProgrammingError

# ============================ 基础配置 ============================
ENV = "sit"

AUTO_CONFIG = {
    "approved_amount": 2000.00,
    "approved_status": "APPROVED",
    "esign_amount": 2000.00,
    "esign_status": "SUCCESS",
    "step_interval": 10,
    "drawdown_amount": 2000.00,
    "drawdown_status": "APPROVED",
    "sql_timeout": 5  # SQL执行超时时间（秒）
}

# 日志配置（结构化输出）
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


# ============================ 数据类（类型提示优化） ============================
@dataclass
class QueryResult:
    success: bool
    data: Optional[Any] = None
    error_msg: str = ""


# ============================ 工具函数 ============================
def generate_uuid37() -> str:
    return str(uuid.uuid4())


def validate_phone(phone: str) -> bool:
    """增强手机号校验：支持8/11位纯数字，且11位需符合手机号段规则"""
    if not phone.isdigit() or len(phone) not in (8, 11):
        return False
    # 11位手机号段基础校验（可选）
    if len(phone) == 11 and not phone.startswith(('13', '14', '15', '16', '17', '18', '19')):
        log.warning(f"手机号{phone}格式不符合常见号段规则")
    return True


def get_utc_time() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_local_time_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    return time.strftime(format_str, time.localtime())


def input_with_validate(prompt: str, validator: Callable[[str], bool], err_msg: str) -> str:
    """增强输入校验：添加重试次数限制"""
    max_retry = 3
    retry_count = 0
    while retry_count < max_retry:
        user_input = input(prompt).strip()
        if validator(user_input):
            return user_input
        retry_count += 1
        remaining = max_retry - retry_count
        log.error(f"{err_msg} 剩余重试次数: {remaining}")
    raise ValueError(f"输入验证失败，已达到最大重试次数({max_retry})")


# ============================ 数据库配置（深度优化） ============================
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
        return {
            **config,
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 15,
            "read_timeout": AUTO_CONFIG["sql_timeout"],  # 读超时
            "write_timeout": AUTO_CONFIG["sql_timeout"],  # 写超时
            "use_unicode": True,
            "autocommit": True,
            "sql_mode": "NO_ENGINE_SUBSTITUTION,STRICT_TRANS_TABLES"
        }


class DBExecutor:
    """数据库执行器（修复 execute() first 错误）"""

    def __init__(self, env: str = ENV):
        self.config = DBConfig.get_config(env)
        self.conn: Optional[pymysql.Connection] = None
        self._main_cursor: Optional[pymysql.Cursor] = None  # 主游标（避免命名冲突）
        self._connect()

    def _connect(self) -> None:
        """增强连接逻辑：添加重连机制"""
        max_retry = 2
        for retry in range(max_retry):
            try:
                self.conn = pymysql.connect(
                    host=self.config["host"],
                    user=self.config["user"],
                    password=self.config["password"],
                    database=self.config["database"],
                    port=self.config["port"],
                    charset=self.config["charset"],
                    connect_timeout=self.config["connect_timeout"],
                    read_timeout=self.config["read_timeout"],
                    write_timeout=self.config["write_timeout"],
                    use_unicode=self.config["use_unicode"],
                    autocommit=self.config["autocommit"],
                    client_flag=CLIENT.MULTI_STATEMENTS
                )
                self._main_cursor = self.conn.cursor()  # 初始化主游标
                log.info("✅ 数据库连接成功")
                return
            except OperationalError as e:
                log.error(f"❌ 数据库连接失败(重试{retry + 1}/{max_retry}): {str(e)}")
                if retry == max_retry - 1:
                    raise
                time.sleep(1)  # 重试间隔

    def _execute_query(self, sql: str, params: tuple = (), is_dict: bool = False) -> QueryResult:
        """
        修复核心：移除无效的scroll，确保先execute再获取结果
        - 彻底删除 cursor.scroll(0, mode='absolute')（根源问题）
        - 每个查询使用独立游标，避免状态混乱
        """
        cursor = None
        try:
            # 1. 创建独立游标（避免主游标状态污染）
            if is_dict:
                cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            else:
                cursor = self.conn.cursor()  # 新建普通游标，而非复用主游标

            # 2. 先执行execute（核心修复：确保execute优先执行）
            log.debug(f"执行参数化SQL: {sql} | 参数: {params}")
            affected_rows = cursor.execute(sql, params)  # 先执行！
            log.debug(f"SQL匹配行数: {affected_rows}")

            # 3. 再获取结果
            result = cursor.fetchone()

            # 4. 标准化返回
            if result:
                data = result if is_dict else (result[0] if result else None)
                return QueryResult(success=True, data=data)
            return QueryResult(success=True, data=None)

        except ProgrammingError as e:
            err_msg = f"SQL语法错误: {str(e)} | SQL: {sql[:200]}"
            log.error(err_msg)
            return QueryResult(success=False, error_msg=err_msg)
        except OperationalError as e:
            err_msg = f"SQL执行超时/连接异常: {str(e)} | SQL: {sql[:200]}"
            log.error(err_msg)
            # 尝试重连
            self._connect()
            return QueryResult(success=False, error_msg=err_msg)
        except Exception as e:
            err_msg = f"SQL执行失败: {str(e)} | SQL: {sql[:200]}"
            log.error(err_msg)
            return QueryResult(success=False, error_msg=err_msg)
        finally:
            # 确保游标关闭，避免资源泄漏
            if cursor:
                cursor.close()

    def query_one_param(self, sql: str, params: tuple = ()) -> QueryResult:
        """修复版：参数化查询单个值"""
        return self._execute_query(sql, params, is_dict=False)

    def query_dict_param(self, sql: str, params: tuple = ()) -> QueryResult:
        """修复版：参数化查询字典结果"""
        return self._execute_query(sql, params, is_dict=True)

    def batch_execute(self, sql: str, params_list: list[tuple]) -> QueryResult:
        """批量执行SQL（如需要）"""
        try:
            # 使用主游标执行批量操作
            affected_rows = self._main_cursor.executemany(sql, params_list)
            log.debug(f"批量执行影响行数: {affected_rows}")
            return QueryResult(success=True, data=affected_rows)
        except Exception as e:
            err_msg = f"批量执行失败: {str(e)} | SQL: {sql[:200]}"
            log.error(err_msg)
            return QueryResult(success=False, error_msg=err_msg)

    @contextlib.contextmanager
    def transaction(self):
        """事务上下文管理器"""
        try:
            self.conn.autocommit(False)
            yield
            self.conn.commit()
            log.info("✅ 事务提交成功")
        except Exception as e:
            self.conn.rollback()
            log.error(f"❌ 事务回滚: {str(e)}")
            raise
        finally:
            self.conn.autocommit(True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._main_cursor:
            self._main_cursor.close()
        if self.conn:
            self.conn.close()
        log.info("✅ 数据库连接已关闭")

    # ========== 新增：推荐索引（可执行一次创建） ==========
    def create_recommended_indexes(self):
        """创建高频查询字段索引（首次运行执行）"""
        indexes = [
            # dpu_users: 手机号查询优化
            "CREATE INDEX idx_dpu_users_phone ON dpu_users(phone_number);",
            # dpu_auth_token: 商户ID+授权方查询优化
            "CREATE INDEX idx_dpu_auth_token_merchant_party ON dpu_auth_token(merchant_id, authorization_party);",
            # dpu_limit_application: 商户ID查询优化
            "CREATE INDEX idx_dpu_limit_app_merchant ON dpu_limit_application(merchant_id);",
            # dpu_application: 商户ID查询优化
            "CREATE INDEX idx_dpu_application_merchant ON dpu_application(merchant_id);",
            # dpu_drawdown: 商户ID查询优化
            "CREATE INDEX idx_dpu_drawdown_merchant ON dpu_drawdown(merchant_id);"
        ]
        for idx_sql in indexes:
            try:
                # 使用主游标执行索引创建
                self._main_cursor.execute(idx_sql)
                log.info(f"✅ 索引创建成功: {idx_sql[:50]}...")
            except Exception as e:
                if "Duplicate key name" in str(e):
                    log.info(f"ℹ️ 索引已存在: {idx_sql[:50]}...")
                else:
                    log.error(f"❌ 索引创建失败: {str(e)} | SQL: {idx_sql[:50]}...")


# ============================ API配置 ============================
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


# ============================ 核心服务（适配正确字段名） ============================
class DPUAutoService:
    def __init__(self, phone: str, db_executor: DBExecutor):
        self.phone = phone
        self.db = db_executor
        self.api = ApiConfig()

        # 1. 获取merchant_id（优化查询逻辑）
        self.merchant_id = self._get_merchant_id()
        if not self.merchant_id:
            raise ValueError(f"❌ 手机号{phone}未查询到merchant_id")

        # 2. 批量获取所有需要的ID（减少数据库交互次数）
        (self.dpu_auth_token_seller_id,
         self.dpu_limit_application_id,
         self.application_unique_id) = self._batch_get_application_ids()

        # 3. 放款ID初始化（仅占位，用户确认放款后才查询）
        self.lender_approved_offer_id = f"lender-{self.application_unique_id}" if self.application_unique_id else "lender-default"
        self.dpu_loan_id = None  # 延迟赋值（直接使用数据库的loan_id）
        self.lender_loan_id = None  # 延迟赋值（数据库loan_id拼接lender-前缀）

        log.info(f"✅ 初始化完成 | 手机号: {phone} | MerchantID: {self.merchant_id}")
        log.info(f"📊 基础ID | application_unique_id: {self.application_unique_id}")

    def _get_merchant_id(self) -> Optional[str]:
        """优化：手机号查询merchant_id（添加非空校验）"""
        sql = """
            SELECT merchant_id FROM dpu_users 
            WHERE phone_number = %s 
              AND merchant_id IS NOT NULL  -- 非空校验
            ORDER BY created_at DESC LIMIT 1;
        """
        result = self.db.query_one_param(sql, (self.phone,))
        if not result.success:
            log.error(f"❌ 查询merchant_id失败: {result.error_msg}")
            return None
        return result.data

    def _batch_get_application_ids(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """优化：批量获取应用相关ID（减少3次查询为1次逻辑封装）"""
        # 1. 获取auth token
        auth_sql = """
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = %s 
              AND authorization_party = 'SP' 
              AND authorization_id IS NOT NULL
            ORDER BY created_at DESC LIMIT 1;
        """
        auth_result = self.db.query_one_param(auth_sql, (self.merchant_id,))

        # 2. 获取limit application ID
        limit_sql = """
            SELECT limit_application_unique_id FROM dpu_limit_application 
            WHERE merchant_id = %s 
              AND limit_application_unique_id IS NOT NULL
            ORDER BY created_at DESC LIMIT 1;
        """
        limit_result = self.db.query_one_param(limit_sql, (self.merchant_id,))

        # 3. 获取application ID
        app_sql = """
            SELECT application_unique_id FROM dpu_application 
            WHERE merchant_id = %s 
              AND application_unique_id IS NOT NULL
            ORDER BY created_at DESC LIMIT 1;
        """
        app_result = self.db.query_one_param(app_sql, (self.merchant_id,))

        # 统一返回
        auth_id = auth_result.data if auth_result.success else None
        limit_id = limit_result.data if limit_result.success else None
        app_id = app_result.data if app_result.success else None

        if not all([auth_result.success, limit_result.success, app_result.success]):
            log.warning("⚠️ 部分ID查询失败，可能影响流程")

        return auth_id, limit_id, app_id

    def _get_drawdown_loan_id(self) -> str:
        """【精简版】仅查询loan_id（无需查询lender_approved_offer_id）"""
        sql = """
            SELECT loan_id FROM dpu_drawdown 
            WHERE merchant_id = %s 
              AND loan_id IS NOT NULL 
            ORDER BY created_at DESC LIMIT 1;
        """
        result = self.db.query_one_param(sql, (self.merchant_id,))

        if not result.success:
            raise ValueError(f"❌ 查询loan_id失败: {result.error_msg}")
        if not result.data:
            raise ValueError(f"❌ 在dpu_drawdown表中未查询到merchant_id={self.merchant_id}的有效loan_id记录")

        return result.data

    # ========== 以下为原有逻辑（仅修改放款ID查询/拼接部分） ==========
    def _send_webhook_request(self, request_body: Dict[str, Any], step_name: str = "未知步骤") -> bool:
        log.info(f"\n🚀 发送{step_name}请求")
        try:
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
            log.error(f"❌ {step_name} 异常: {str(e)}")
            return False

    def _wait_for_interval(self, step_name: str):
        log.info(f"\n⏳ 等待{AUTO_CONFIG['step_interval']}秒后执行{step_name}...")
        time.sleep(AUTO_CONFIG['step_interval'])

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

    def run_disbursement_completed(self) -> bool:
        # 前置校验：确保放款ID已查询
        if not self.dpu_loan_id or not self.lender_loan_id:
            log.error("❌ 放款ID未初始化，请先查询放款ID")
            return False

        drawdown_amount = AUTO_CONFIG["drawdown_amount"]
        drawdown_status = AUTO_CONFIG["drawdown_status"]

        request_body = {
            "data": {
                "eventType": "disbursement.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "Disbursement completed",
                "enquiryUrl": f"/loans?merchantId={self.merchant_id}&loanId=LEND1",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "dpuLoanId": self.dpu_loan_id,  # 直接使用数据库的loan_id
                    "lenderLoanId": self.lender_loan_id,  # 使用拼接后的lender-loan_id
                    "originalRequestId": "e37b91d056114e48a466b433934e2068",
                    "lenderCreditId": "CR1",
                    "lenderCompanyId": "LEND1",
                    "lenderDrawdownId": "DRA1",
                    "drawdownStatus": drawdown_status,
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system",
                    "disbursement": {
                        "loanAmount": {"currency": "USD", "amount": drawdown_amount},
                        "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "6.00",
                                 "marginRate": "0.00"},
                        "term": "120",
                        "termUnit": "Days",
                        "drawdownSuccessDate": get_current_time("%Y-%m-%d"),
                        "actualDrawdownDate": get_current_time("%Y-%m-%d")
                    },
                    "repayment": {
                        "expectedRepaymentDate": "2026-01-21",
                        "expectedRepaymentAmount": {"currency": "USD", "amount": drawdown_amount},
                        "repaymentTerm": "90"
                    }
                }
            }
        }
        return self._send_webhook_request(request_body, "放款(disbursement.completed)")

    def run_full_flow(self):
        log.info("\n" + "=" * 60)
        log.info("🎯 开始DPU自动化流程（500K额度）")
        log.info("=" * 60)

        # 步骤1：审批（原逻辑无修改）
        if not self.run_approved():
            log.error("❌ 审批失败，流程终止")
            return

        log.info("\n📌 审批请求已成功（200响应），准备自动执行电子签流程")
        self._wait_for_interval("电子签")

        # 步骤2：电子签（原逻辑无修改）
        if not self.run_esign():
            log.error("❌ 电子签失败，流程终止")
            return

        log.info("\n📌 电子签请求已成功（200响应），准备开始放款流程")
        # 步骤3：人工确认放款 + 延迟查询放款ID（仅查询loan_id，拼接lender-前缀）
        while True:
            user_input = input("🔍 是否确认开始放款(disbursement.completed)请求？输入1继续：").strip()
            if user_input == "1":
                log.info("✅ 确认开始放款流程，正在查询最新loan_id...")
                try:
                    # 调用精简后的查询方法，仅获取loan_id
                    db_loan_id = self._get_drawdown_loan_id()

                    # 赋值：dpu_loan_id用原始值，lender_loan_id拼接前缀
                    self.dpu_loan_id = db_loan_id
                    self.lender_loan_id = f"lender-{db_loan_id}"

                    log.info(f"✅ loan_id查询成功 | 数据库loan_id: {db_loan_id}")
                    log.info(
                        f"✅ 放款ID处理完成 | dpu_loan_id: {self.dpu_loan_id} | lender_loan_id: {self.lender_loan_id}")
                except ValueError as e:
                    log.error(f"❌ loan_id查询失败: {str(e)}")
                    return
                break
            log.warning("⚠️ 请输入1确认继续，其他输入无效！")

        # 步骤4：执行放款（原逻辑无修改）
        if not self.run_disbursement_completed():
            log.error("❌ 放款失败，流程终止")
            return

        log.info("\n" + "=" * 60)
        log.info("🎉 所有流程执行完成！")
        log.info(f"📱 手机号: {self.phone} | 💰 额度: 2K | 📤 放款金额: 2K USD")
        log.info(f"🔑 贷款ID | dpu_loan_id: {self.dpu_loan_id} | lender_loan_id: {self.lender_loan_id}")
        log.info("=" * 60)


# ============================ 辅助函数（SQL查询优化） ============================
def check_phone_registered(phone: str, db: DBExecutor) -> bool:
    """优化：移除字符串拼接，全参数化查询（原逻辑无修改）"""
    # 1. 查询merchant_id（参数化）
    merchant_sql = "SELECT merchant_id FROM dpu_users WHERE phone_number = %s LIMIT 1;"
    merchant_result = db.query_one_param(merchant_sql, (phone,))

    if not merchant_result.success:
        log.error(f"❌ 查询手机号注册状态失败: {merchant_result.error_msg}")
        return False
    if not merchant_result.data:
        log.error(f"❌ 手机号 {phone} 未注册")
        return False

    merchant_id = merchant_result.data

    # 2. 查询3PL授权记录（参数化）
    auth_sql = """
        SELECT authorization_id FROM dpu_auth_token 
        WHERE merchant_id = %s 
          AND authorization_party = '3PL' 
        ORDER BY created_at DESC LIMIT 1;
    """
    auth_result = db.query_one_param(auth_sql, (merchant_id,))

    if auth_result.success and auth_result.data:
        log.info(f"✅ 手机号 {phone} 已注册 | OfferID: {auth_result.data}")
    else:
        log.warning(f"⚠️ 手机号 {phone} 已注册，但无3PL授权记录 | 原因: {auth_result.error_msg or '无数据'}")

    return True


# ============================ 主函数 ============================
def main():
    log.info(f"📢 DPU自动化工具 | 环境: {ENV}")
    log.info("🔧 流程: 审批→[自动等待10秒]→电子签→[人工确认+查询loan_id]→放款")

    with DBExecutor() as db:
        # 可选：首次运行创建索引（创建后可注释）
        # db.create_recommended_indexes()

        # 输入手机号（原逻辑无修改）
        try:
            phone = input_with_validate(
                prompt="\n请输入已注册手机号：",
                validator=lambda x: validate_phone(x) and check_phone_registered(x, db),
                err_msg="❌ 请输入有效的已注册手机号（8/11位数字）！"
            )
        except ValueError as e:
            log.error(f"❌ 手机号输入失败: {str(e)}")
            return

        # 执行流程（原逻辑无修改）
        try:
            service = DPUAutoService(phone, db)
            service.run_full_flow()
        except ValueError as e:
            log.error(f"❌ 初始化失败: {str(e)}")
        except Exception as e:
            log.error(f"❌ 流程异常: {str(e)} | 异常类型: {type(e).__name__}", exc_info=True)

    log.info("\n👋 程序执行完毕")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n⚠️ 程序被用户中断")
    except Exception as e:
        log.error(f"❌ 程序异常退出: {str(e)} | 异常类型: {type(e).__name__}", exc_info=True)
        exit(1)