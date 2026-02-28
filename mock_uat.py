# -*- coding: utf-8 -*-
"""
DPU状态模拟工具
功能：支持账号注册、SP授权、核保/审批/PSP/电子签/放款/还款等状态模拟，支持多环境切换和多店铺场景
环境支持：sit/local/dev/uat/preprod
核心特性：自动重连数据库、输入验证、日志颜色区分、统一请求处理
"""
import logging
import os
import socket
import time
import uuid
import random
from urllib.parse import urlencode
from enum import Enum
from typing import Optional, Dict, Any, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

import pymysql
import requests
from faker import Faker
from pymysql.constants import CLIENT
from pymysql.err import OperationalError

# ============================ 基础配置（集中管理，便于维护）============================
# 环境配置（支持：sit/local/dev/uat/preprod）
ENV = "uat"

# 流程配置映射（清晰展示不同额度对应的流程步骤）
STEPS = {
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


# ============================ 日志配置（修复StreamHandler参数错误）============================
class ColorFormatter(logging.Formatter):
    """日志颜色格式化器：ERROR标红，其他默认"""
    RED = "\033[91m"
    RESET = "\033[0m"
    FORMAT = "[%(asctime)s] [%(levelname)s] %(lineno)d %(funcName)s: %(message)s"

    def __init__(self):
        super().__init__(self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.ERROR:
            return f"{self.RED}{super().format(record)}{self.RESET}"
        return super().format(record)


# 修复：先创建Handler实例，再设置formatter（StreamHandler不支持初始化传formatter）
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())

# 配置日志（强制覆盖默认配置，确保格式统一）
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler],  # 直接传入已设置格式器的handler
    force=True
)
log = logging.getLogger(__name__)

# 初始化工具实例（单例复用）
faker = Faker("zh_CN")


# ============================ 工具函数（精简冗余，提升复用性）============================
def generate_uuid37() -> str:
    """生成37位UUID字符串（替代nanoid）"""
    return str(uuid.uuid4())


def validate_phone_number(phone_number: str) -> bool:
    """验证手机号格式（支持8位或11位数字）"""
    return phone_number.isdigit() and len(phone_number) in (11, 8)


def get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间字符串"""
    return time.strftime(fmt, time.localtime())


def get_utc_time() -> str:
    """获取UTC时间字符串（符合ISO格式）"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def validate_numeric_input(input_str: str) -> bool:
    """验证输入是否为有效数字（支持整数和小数）"""
    return input_str.replace('.', '', 1).isdigit() if input_str else False


def input_with_validation(
        prompt: str,
        validator: Callable[[str], bool],
        error_msg: str = "输入无效，请重新输入！"
) -> str:
    """带验证的输入函数（通用封装，减少重复代码）"""
    while True:
        user_input = input(prompt).strip()
        if validator(user_input):
            return user_input
        log.error(error_msg)


def calculate_future_date(days: int = 90) -> str:
    """计算未来日期（默认90天后）"""
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


# ============================ 枚举类定义（规范状态值，减少魔法字符串）============================
class SanctionStatus(Enum):
    """application表制裁状态枚举"""
    HIT = 'HIT'
    NOT_HIT = 'NOT_HIT'
    INITIAL = 'INITIAL'


class ReturnedFailureReason(Enum):
    """审批退回失败原因枚举"""
    INCORRECT_BRN = "不正确 BRN"
    FAILED_TO_OBTAIN_CUSTOMER_ID = "未能获取客户 ID 号码"
    ID_MISMATCH_WITH_CR_RECORD = "ID 号码与 CR 记录不相符"
    FAILED_COMPANY_STRUCTURE_VERIFICATION = "未能通过公司结构校验"
    REQUIRES_MANUAL_AML_VERIFICATION = "需要人工处理反洗钱验证"


class DPUStatus(Enum):
    """DPU状态枚举：psp/esign用SUCCESS/FAIL，其余用APPROVED/REJECTED"""
    INITIAL = 'INITIAL'
    SUBMITTED = 'SUBMITTED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    RETURNED = 'RETURNED'
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    PROCESSING = "PROCESSING"


class RepaymentStatus(Enum):
    """还款状态枚举"""
    SUCCESS = "Success"
    FAILURE = "Failure"
    START = "Start"  # 修正原笔误STATR


class DrawdownFailureReason(Enum):
    """放款失败原因枚举"""
    NO_VALID_BANK_ACCOUNT = ("ER001", "无有效银行账户")
    INSUFFICIENT_WATER_LEVEL = ("ER002", "可用水位线 < 提款金额")
    UNKNOWN_ERROR = ("ER003", "未知错误")
    BANK_REJECT = ("ER004", "银行/支付服务提供商拒绝")
    OVERDUE = ("ER005", "逾期")


# ============================ 配置数据类（集中管理配置，支持多环境）============================
@dataclass(frozen=True)
class ApiConfig:
    """API配置数据类（不可变，集中管理接口地址）"""
    base_url: str
    create_offerid_url: str
    redirect_url: str
    register_url: str
    login_url: str
    spapi_auth_url: str
    multi_shop_sp_auth_url: str
    link_sap_3pl_url: str
    create_psp_auth_url: str
    webhook_url: str
    update_offer_url: str
    txt_path: str


class DatabaseConfig:
    """数据库配置类（支持多环境切换，懒加载配置）"""
    _DATABASE_CONFIG: Dict[str, Dict[str, Union[str, int]]] = {
        "sit": {
            "host": "18.162.145.173",
            "user": "dpu_sit",
            "password": "20250818dpu_sit",
            "database": "dpu_seller_center",
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,
            "read_timeout": 15,
        },
        "dev": {
            "host": "aurora-dpu-dev.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
            "user": "dpu_dev",
            "password": "J9IUmPpD@Hon8Y#v",
            "database": "dpu_seller_center",
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,
            "read_timeout": 15,
        },
        "uat": {
            "host": "aurora-dpu-uat.cluster-cv2aqqmyo5k9.ap-east-1.rds.amazonaws.com",
            "user": "dpu_uat",
            "password": "6S[a=u.*Z;Zt~b&-A4|Ma&q^w8r_3vz[",
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
        "local": {
            "host": "localhost",
            "user": "root",
            "password": "root",
            "database": "dpu_seller_center",
            "port": 3306,
            "charset": "utf8mb4",
            "connect_timeout": 1500,
            "read_timeout": 15,
        }
    }

    @classmethod
    def get_config(cls, env: str = ENV) -> Dict[str, Union[str, int]]:
        """获取指定环境的数据库配置（环境校验）"""
        if env not in cls._DATABASE_CONFIG:
            raise ValueError(
                f"不支持的环境：{env}（支持：{','.join(cls._DATABASE_CONFIG.keys())}）"
            )
        return cls._DATABASE_CONFIG[env].copy()


def get_local_physical_ip() -> Optional[str]:
    """获取本地物理网卡IP地址（用于绕过VPN直连数据库）"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            if not local_ip.startswith(("10.", "172.16.", "192.168.", "127.")):
                return local_ip
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if not local_ip.startswith(("10.", "172.16.", "192.168.", "127.")):
                return local_ip
    except Exception:
        pass
    return None


# ============================ 数据库执行器（精简连接逻辑，提升稳定性）============================
class DatabaseExecutor:
    """数据库操作执行器（封装连接、查询、执行逻辑，支持自动重连和上下文管理）"""

    def __init__(self, env: str = ENV):
        self.config = DatabaseConfig.get_config(env)
        self.conn: Optional[pymysql.connections.Connection] = None
        self.cursor: Optional[pymysql.cursors.Cursor] = None
        self.env = env

    def connect(self) -> None:
        """建立数据库连接（绑定本地物理网卡IP绕过VPN）"""
        # 获取本地物理网卡IP
        local_ip = get_local_physical_ip()
        connect_params = self.config.copy()

        if local_ip:
            connect_params['bind_address'] = local_ip

        try:
            # 清除代理环境变量
            old_proxies = {}
            for proxy_key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
                if os.environ.get(proxy_key):
                    old_proxies[proxy_key] = os.environ[proxy_key]
                    del os.environ[proxy_key]

            self.conn = pymysql.connect(
                **connect_params,
                autocommit=True,
                client_flag=CLIENT.INTERACTIVE
            )
            self.cursor = self.conn.cursor()
            if local_ip:
                log.info(f"[{self.env}] 数据库直连成功（已绑定 {local_ip} 绕过VPN）")
            else:
                log.info(f"[{self.env}] 数据库连接成功（系统自动路由）")
        except Exception as e:
            log.error(f"[{self.env}] 数据库连接失败: {e}")
            raise
        finally:
            # 恢复代理环境变量
            for k, v in old_proxies.items():
                os.environ[k] = v

    def reconnect(self) -> None:
        """数据库重连（连接失效时自动调用）"""
        try:
            if self.conn:
                self.conn.close()
            self.connect()
            log.info(f"[{self.env}] 数据库重连成功")
        except Exception as e:
            log.error(f"[{self.env}] 数据库重连失败: {e}")
            raise

    def _execute_with_retry(
            self,
            func: Callable[[str], Any],
            sql: str,
            retry: int = 3
    ) -> Any:
        """带重试机制的执行包装器（统一处理连接失效）"""
        try:
            # f-string中不能使用反斜杠，需要提前处理
            sql_display = sql.strip().replace('\n', ' ')
            log.debug(f"执行SQL: {sql_display}")
            return func(sql)
        except OperationalError as e:
            # 处理常见连接失效错误码
            if e.args[0] in (2006, 2013, 10054) and retry > 0:
                log.warning(f"数据库连接失效，剩余{retry}次重连尝试...")
                self.reconnect()
                return self._execute_with_retry(func, sql, retry - 1)
            sql_display = sql.strip().replace('\n', ' ')
            log.error(f"SQL执行出错: {e}, SQL: {sql_display}")
            raise
        except Exception as e:
            sql_display = sql.strip().replace('\n', ' ')
            log.error(f"SQL执行出错: {e}, SQL: {sql_display}")
            raise

    def execute_sql(self, sql: str, retry: int = 3) -> Optional[Any]:
        """执行SQL语句（查询返回第一条结果的第一个字段，其他返回None）"""

        def _execute(sql: str):
            self.cursor.execute(sql)
            if sql.strip().lower().startswith("select"):
                results = self.cursor.fetchall()
                return results[0][0] if results else None
            return None

        return self._execute_with_retry(_execute, sql, retry)

    def execute_query(self, sql: str, retry: int = 3) -> Optional[Dict[str, Any]]:
        """执行查询并返回字典格式结果（字段名-值映射）"""

        def _query(sql: str):
            self.cursor.execute(sql)
            columns = [desc[0] for desc in self.cursor.description]
            results = self.cursor.fetchall()
            return dict(zip(columns, results[0])) if results else None

        return self._execute_with_retry(_query, sql, retry)

    def __enter__(self):
        """上下文管理器进入（支持with语句）"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出（自动关闭连接）"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        log.info(f"[{self.env}] 数据库连接已关闭")


# ============================ DPU模拟服务（核心业务逻辑，职责单一）============================
class DPUMockService:
    """DPU状态模拟服务（封装所有业务操作，支持单例共享多店铺状态）"""
    generated_selling_partner_id: Optional[str] = None  # 多店铺共享SP绑定ID
    cached_lender_repayment_id: Optional[str] = None  # 缓存的还款ID，确保连续还款操作ID一致

    def __init__(self, phone_number: str, db_executor: DatabaseExecutor):
        self.phone_number = phone_number
        self.db_executor = db_executor
        self.merchant_id = self.get_merchant_id()
        self.seller_id: Optional[str] = None
        self.api_config = self._init_api_config()  # 初始化API配置

    def _init_api_config(self) -> ApiConfig:
        """初始化API配置（根据环境自动切换）"""
        # 基础URL映射
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "local": "http://192.168.11.3:8080"
        }
        base_url = base_url_dict[self.db_executor.env]

        # 重定向URL特殊处理
        redirect_url = (
            f"{base_url}/dpu-merchant/amazon/redirect"
            if self.db_executor.env in ("uat", "preprod")
            else f"https://dpu-gateway-{self.db_executor.env}.dowsure.com/dpu-merchant/amazon/redirect"
        )

        # 构建API配置（复用基础URL，减少冗余）
        return ApiConfig(
            base_url=base_url,
            create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            redirect_url=redirect_url,
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=f"{base_url}/dpu-merchant/amz/sp/shop/auth",
            multi_shop_sp_auth_url=f"{base_url}/dpu-auth/amazon-sp/auth",
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            update_offer_url=f"{base_url}/dpu-auth/amazon-sp/updateOffer",
            txt_path=f"./register_{self.db_executor.env}.txt"
        )

    # ============================ 数据查询方法（精简SQL，提升可读性）============================
    def get_merchant_id(self) -> Optional[str]:
        """根据手机号查询最新的merchant_id"""
        sql = f"""
            SELECT merchant_id FROM dpu_users 
            WHERE phone_number = '{self.phone_number}' 
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    def get_platform_offer_id(self, seller_id: str) -> Optional[str]:
        """根据seller_id查询platform_offer_id"""
        sql = f"""
            SELECT platform_offer_id FROM dpu_manual_offer 
            WHERE platform_seller_id = '{seller_id}'
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    def get_drawdown_info(self) -> Optional[Dict[str, Any]]:
        """从dpu_drawdown表获取最新放款信息（还款操作必需）"""
        if not self.merchant_id:
            log.error("未获取到merchant_id，无法查询放款信息")
            return None

        sql = f"""
            SELECT merchant_id, loan_id, lender_loan_id 
            FROM dpu_drawdown 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1
        """
        drawdown_info = self.db_executor.execute_query(sql)
        if drawdown_info:
            log.info(f"获取放款信息成功: {drawdown_info}")
        else:
            log.error(f"merchant_id: {self.merchant_id} 无对应放款记录")
        return drawdown_info

    # ============================ 快捷属性（复用查询逻辑，减少重复代码）============================
    @property
    def merchant_account_id(self) -> Optional[str]:
        """获取merchant_account_id"""
        sql = f"""
            SELECT merchant_account_id FROM dpu_merchant_account_limit 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    @property
    def application_unique_id(self) -> Optional[str]:
        """获取application_unique_id"""
        sql = f"""
            SELECT application_unique_id FROM dpu_application 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    @property
    def lender_approved_offer_id(self) -> str:
        """生成lender_approved_offer_id"""
        return f"lender-{self.application_unique_id}" if self.application_unique_id else "lender-default"

    @property
    def dpu_loan_id(self) -> Optional[str]:
        """获取dpu_loan_id"""
        sql = f"""
            SELECT loan_id FROM dpu_drawdown 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    @property
    def lender_loan_id(self) -> str:
        """生成lender_loan_id"""
        return f"lender-{self.dpu_loan_id}" if self.dpu_loan_id else "lender-loan-default"

    @property
    def dpu_limit_application_id(self) -> Optional[str]:
        """获取limit_application_unique_id"""
        sql = f"""
            SELECT limit_application_unique_id FROM dpu_limit_application 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    @property
    def dpu_auth_token_seller_id(self) -> Optional[str]:
        """获取SP授权的seller_id"""
        sql = f"""
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = '{self.merchant_id}' 
            AND authorization_party = 'SP' 
            AND authorization_id IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        """
        return self.db_executor.execute_sql(sql)

    def _get_or_create_lender_repayment_id(self) -> str:
        """获取或创建还款ID（确保连续操作ID一致）"""
        if self.cached_lender_repayment_id is None:
            self.cached_lender_repayment_id = f"LRP{generate_uuid37()[:10].upper()}"
            log.info(f"生成新的还款ID: {self.cached_lender_repayment_id}")
        else:
            log.info(f"使用缓存的还款ID: {self.cached_lender_repayment_id}")
        return self.cached_lender_repayment_id

    def clear_lender_repayment_id(self) -> None:
        """清空缓存的还款ID（用于新的还款流程）"""
        if self.cached_lender_repayment_id:
            log.info(f"清空缓存的还款ID: {self.cached_lender_repayment_id}")
            self.cached_lender_repayment_id = None
        else:
            log.info("当前无缓存的还款ID，无需清空")

    # ============================ 公共请求方法（统一异常处理，提升稳定性）============================
    def _send_webhook_request(self, request_body: Dict[str, Any]) -> bool:
        """发送webhook请求（统一日志和异常处理）"""
        try:
            response = requests.post(
                self.api_config.webhook_url,
                json=request_body,
                timeout=30
            )
            response.raise_for_status()
            log.info(f"Webhook请求成功，响应: {response.text[:100]}...")
            return True
        except requests.exceptions.RequestException as e:
            # ========== 优化点1：增强Webhook请求失败日志 ==========
            error_detail = f"Webhook请求失败: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                error_detail += f"\n  - 响应头: {dict(e.response.headers)}"
                try:
                    # 尝试解析JSON响应
                    resp_json = e.response.json()
                    error_detail += f"\n  - TraceId: {resp_json.get('traceId', 'N/A')}"
                    error_detail += f"\n  - Status: {resp_json.get('status', 'N/A')}"
                    error_detail += f"\n  - Detail: {resp_json.get('detail', 'N/A')}"
                    error_detail += f"\n  - 完整响应: {resp_json}"
                except:
                    # 非JSON响应直接输出文本
                    error_detail += f"\n  - 响应内容: {e.response.text[:500]}"
            log.error(error_detail)
            return False

    def _send_request(
            self,
            url: str,
            method: str = "POST",
            **kwargs
    ) -> Optional[Dict]:
        """通用请求方法（支持GET/POST，统一异常处理）"""
        try:
            response = requests.request(method.upper(), url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # ========== 优化点2：增强通用请求失败日志 ==========
            error_detail = f"请求{url}失败: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_detail += f"\n  - 请求方法: {method.upper()}"
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                error_detail += f"\n  - 响应头: {dict(e.response.headers)}"
                try:
                    # 尝试解析JSON响应
                    resp_json = e.response.json()
                    error_detail += f"\n  - TraceId: {resp_json.get('traceId', 'N/A')}"
                    error_detail += f"\n  - Status: {resp_json.get('status', 'N/A')}"
                    error_detail += f"\n  - Code: {resp_json.get('code', 'N/A')}"
                    error_detail += f"\n  - Message: {resp_json.get('message', 'N/A')}"
                    error_detail += f"\n  - Detail: {resp_json.get('detail', 'N/A')}"
                    error_detail += f"\n  - 完整响应JSON: {resp_json}"
                except:
                    # 非JSON响应直接输出文本
                    error_detail += f"\n  - 响应内容: {e.response.text[:500]}"
            log.error(error_detail)
            return None

    # ============================ 业务操作方法（精简冗余，提升复用性）============================
    @classmethod
    def get_journey_by_input(cls) -> str:
        """获取用户选择的注册流程（200K/500K/2000K）"""
        journey_map = {"1": "200K", "2": "500K", "3": "2000K"}
        prompt = "请输入注册流程：1-200K 2-500K 3-2000K \n"
        return journey_map[input_with_validation(prompt, lambda x: x in journey_map)]

    @classmethod
    def _create_offer_id(cls, journey: str, api_config: ApiConfig) -> Optional[str]:
        """创建offer_id（按流程生成对应额度，创建后自动访问redirect_url使offer_id生效）"""
        journey_amount = {"200K": 100000, "500K": 800000, "2000K": 6000000}
        yearly_amount = journey_amount.get(journey.upper())
        if not yearly_amount:
            log.error(f"不支持的流程: {journey}")
            return None

        # 创建offer_id
        resp = requests.post(
            api_config.create_offerid_url,
            json={"yearlyRepaymentAmount": yearly_amount},
            timeout=30
        )
        offer_id = resp.json().get("data", {}).get("amazon3plOfferId") if resp.ok else None

        # 创建成功后自动访问redirect_url使offer_id生效
        if offer_id:
            redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
            try:
                # GET请求激活
                requests.get(redirect_url, timeout=30)
                # POST请求二次确认
                post_payload = {"offerId": offer_id, "relayPage": 1}
                requests.post(
                    redirect_url,
                    json=post_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                log.info(f"offer_id {offer_id} 已激活")
            except requests.exceptions.RequestException as e:
                # ========== 优化点3：增强offer_id激活失败日志 ==========
                error_detail = f"offer_id激活失败: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    error_detail += f"\n  - 状态码: {e.response.status_code}"
                    error_detail += f"\n  - 响应内容: {e.response.text[:500]}"
                log.warning(error_detail)
        else:
            log.error("offer_id创建失败")

        return offer_id

    @classmethod
    def register_new_account(cls) -> str:
        """注册新账号（自动生成手机号、邮箱，返回注册成功的手机号）"""
        journey = cls.get_journey_by_input()
        log.info(f"开始注册新账号，流程: {journey}")

        # 生成账号信息
        phone_number = ''.join(filter(str.isdigit, faker.phone_number()))
        email = f"{phone_number}y@163doushabao.com"
        log.info(f"生成账号信息 | 手机号：{phone_number} | 邮箱：{email}")

        # 初始化API配置
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "local": "http://192.168.11.3:8080"
        }
        base_url = base_url_dict[ENV]
        api_config = ApiConfig(
            base_url=base_url,
            create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            redirect_url=(
                f"{base_url}/dpu-merchant/amazon/redirect"
                if ENV in ("uat", "preprod")
                else f"https://dpu-gateway-{ENV}.dowsure.com/dpu-merchant/amazon/redirect"
            ),
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=f"{base_url}/dpu-merchant/amz/sp/shop/auth",
            multi_shop_sp_auth_url=f"{base_url}/dpu-auth/amazon-sp/auth",
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            txt_path=f"./register_{ENV}.txt"
        )

        # 创建offer_id（失败重试）
        offer_id = cls._create_offer_id(journey, api_config)
        if not offer_id:
            log.error("创建offer_id失败，重新注册...")
            return cls.register_new_account()

        # 验证码验证
        validate_url = f"{base_url}/dpu-user/auth/validateSmsCode-sign"
        headers = {
            "accept": "application/json, */*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/143.0.0.0 Safari/537.36"
        }
        payload = {"areaCode": "+86", "code": "666666", "phone": phone_number}
        try:
            requests.post(validate_url, json=payload, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            # ========== 优化点4：增强验证码验证失败日志 ==========
            error_detail = f"验证码验证失败: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                try:
                    resp_json = e.response.json()
                    error_detail += f"\n  - TraceId: {resp_json.get('traceId', 'N/A')}"
                    error_detail += f"\n  - 错误信息: {resp_json.get('message', 'N/A')}"
                except:
                    error_detail += f"\n  - 响应内容: {e.response.text[:500]}"
            log.error(error_detail)

        # 注册请求
        register_payload = {
            "phone": phone_number,
            "areaCode": "+86",
            "code": "666666",
            "email": email,
            "offerId": offer_id,
            "password": "Aa11111111..",
            "confirmPassword": "Aa11111111..",
            "isAcceptMarketing": True,
            "securityQuestionCode": "SEC_Q_004",
            "securityAnswer": "test"
        }

        try:
            redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
            requests.get(redirect_url, timeout=30)
            resp_register = requests.post(
                api_config.register_url,
                json=register_payload,
                timeout=30
            )
            resp_register.raise_for_status()
            token = resp_register.json().get("data", {}).get("token", "未获取到token")
            print(f"✅ 注册成功！手机号: {phone_number} | Token: {token}")
            with open(api_config.txt_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{journey}\n{phone_number}\n{redirect_url}\n")
            return phone_number
        except requests.exceptions.RequestException as e:
            # ========== 优化点5：增强注册失败日志 ==========
            error_detail = f"注册失败: {str(e)} | 手机号：{phone_number}"
            if hasattr(e, 'response') and e.response is not None:
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                try:
                    resp_json = e.response.json()
                    error_detail += f"\n  - TraceId: {resp_json.get('traceId', 'N/A')}"
                    error_detail += f"\n  - Code: {resp_json.get('code', 'N/A')}"
                    error_detail += f"\n  - Message: {resp_json.get('message', 'N/A')}"
                except:
                    error_detail += f"\n  - 响应内容: {e.response.text[:500]}"
            log.error(error_detail)
            return cls.register_new_account()

    # 功能1已注释：模拟SPAPI授权回调
    # def mock_spapi_auth(self) -> None:
    #     """模拟SPAPI授权回调"""
    #     shop_num = input_with_validation(
    #         prompt="请输入店铺编号(1,2,3...): \n",
    #         validator=lambda x: x.isdigit() and int(x) >= 1,
    #         error_msg="请输入正整数！"
    #     )
    #     self.seller_id = f"{shop_num}BTC6RWJD{self.phone_number}"
    #     payload = {
    #         "phone": self.phone_number,
    #         "status": "ACTIVE",
    #         "dpu_token": "dpu_token",
    #         "sellerId": self.seller_id,
    #         "authorization_code": "authorization_code",
    #         "refresh_token_expires_time": "2025-09-19T10:09:07.921Z",
    #         "access_token": "access_token sunt",
    #         "refresh_token": "refresh_token minim et anim sunt"
    #     }
    #     response = self._send_request(self.api_config.spapi_auth_url, json=payload)
    #     if response and response.get("code") == 200:
    #         log.info(f"SPAPI授权成功，seller_id: {self.seller_id}")
    #     else:
    #         log.error(f"SPAPI授权失败: {response}")

    def mock_link_sp_3pl_shop(self) -> None:
        """模拟关联SP和3PL店铺"""
        log.info("开始关联SP和3PL店铺...")
        result = self._send_request(self.api_config.link_sap_3pl_url, params={"phone": self.phone_number})
        log.info("关联成功" if (result and result.get("code") == 200) else "关联失败")

    def _build_common_webhook_data(
            self,
            event_type: str,
            status: str,
            additional_data: Optional[Dict] = None
    ) -> Dict:
        """构建通用webhook数据结构（复用基础字段，减少冗余）"""
        data = {
            "data": {
                "eventType": event_type,
                "eventId": generate_uuid37(),
                "eventMessage": f"{event_type.replace('.', ' ')} event",
                "enquiryUrl": "https://api.example.com/enquiry/123",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system"
                }
            }
        }
        if additional_data:
            data["data"]["details"].update(additional_data)
        return data

    def mock_underwritten_status(self) -> None:
        """模拟核保状态更新"""
        underwritten_amount = input_with_validation(
            prompt="请输入评估额度：\n",
            validator=lambda x: x.isdigit(),
            error_msg="请输入整数！"
        )
        status_input = input_with_validation(
            prompt="请输入核保状态：1-APPROVED 2-REJECTED\n",
            validator=lambda x: x in ("1", "2"),
            error_msg="请输入1或2！"
        )
        underwritten_status = DPUStatus.APPROVED.value if status_input == "1" else DPUStatus.REJECTED.value

        data = self._build_common_webhook_data(
            "underwrittenLimit.completed",
            underwritten_status,
            {
                "dpuMerchantAccountId": [
                    {"MerchantAccountId": self.dpu_auth_token_seller_id}] if self.dpu_auth_token_seller_id else [],
                "dpuLimitApplicationId": self.dpu_limit_application_id,
                "originalRequestId": "req_EFAL17621784619057169",
                "status": underwritten_status,
                "credit": {
                    "marginRate": "2.5",
                    "chargeBases": "Fixed",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "creditLimit": {
                        "currency": "CNY",
                        "underwrittenAmount": {"currency": "CNY", "amount": underwritten_amount}
                    }
                }
            }
        )
        self._send_webhook_request(data)

    def _select_failure_reason(self, reason_enum: Enum) -> str:
        """通用失败原因选择器（复用选择逻辑）"""
        reason_map = {str(i + 1): item.value for i, item in enumerate(reason_enum)}
        prompt = "请选择退回原因：\n" + "\n".join([f"{k}-{v}" for k, v in reason_map.items()]) + "\n"
        return reason_map[input_with_validation(prompt, lambda x: x in reason_map)]

    def mock_approved_offer_status(self) -> None:
        """模拟审批状态更新"""
        approved_amount = round(float(input_with_validation(
            prompt="请输入授信额度：\n",
            validator=lambda x: x.isdigit(),
            error_msg="请输入整数！"
        )), 2)
        status_input = input_with_validation(
            prompt="请输入审批状态：1-APPROVED 2-RETURNED 3-REJECTED\n",
            validator=lambda x: x in ("1", "2", "3"),
            error_msg="请输入1/2/3！"
        )

        status_map = {
            "1": DPUStatus.APPROVED.value,
            "2": DPUStatus.RETURNED.value,
            "3": DPUStatus.REJECTED.value
        }
        approved_status = status_map[status_input]
        failure_reason = self._select_failure_reason(
            ReturnedFailureReason) if approved_status == DPUStatus.RETURNED.value else None

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
                    "originalRequestId": "req_1111113579",
                    "status": approved_status,
                    "failureReason": failure_reason,
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
                        "approvedLimit": {"currency": "USD", "amount": approved_amount},
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
        self._send_webhook_request(request_body)

    def mock_esign_status(self) -> None:
        """模拟电子签状态更新"""
        signed_amount = round(float(input_with_validation(
            prompt="请输入已签约额度：\n",
            validator=lambda x: x.isdigit(),
            error_msg="请输入整数！"
        )), 2)
        status_input = input_with_validation(
            prompt="请输入电子签状态：1-SUCCESS 2-FAIL\n",
            validator=lambda x: x in ("1", "2"),
            error_msg="请输入1或2！"
        )
        esign_status = DPUStatus.SUCCESS.value if status_input == "1" else DPUStatus.FAIL.value

        data = self._build_common_webhook_data(
            "esign.completed",
            esign_status,
            {
                "lenderApprovedOfferId": self.lender_approved_offer_id,
                "result": esign_status,
                "signedLimit": {"amount": signed_amount, "currency": "USD"}
            }
        )
        self._send_webhook_request(data)

    def mock_drawdown_status(self) -> None:
        """模拟放款状态更新"""
        drawdown_amount = input_with_validation(
            prompt="请输入放款额度：\n",
            validator=validate_numeric_input,
            error_msg="请输入有效数字！"
        )
        status_input = input_with_validation(
            prompt="请输入放款状态：1-APPROVED 2-REJECTED\n",
            validator=lambda x: x in ("1", "2"),
            error_msg="请输入1或2！"
        )

        is_rejected = status_input == "2"
        drawdown_status = "REJECTED" if is_rejected else "APPROVED"
        failure_reason = None
        if is_rejected:
            reason_map = {str(i + 1): item.value[0] for i, item in enumerate(DrawdownFailureReason)}
            prompt = "请选择放款失败原因：\n" + "\n".join(
                [f"{k}-{item.value[0]}({item.value[1]})" for k, item in enumerate(DrawdownFailureReason, 1)]) + "\n"
            failure_reason = reason_map[input_with_validation(prompt, lambda x: x in reason_map)]

        current_date = get_current_time("%Y-%m-%d")
        request_body = {
            "data": {
                "eventType": "disbursement.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "Disbursement completed",
                "enquiryUrl": f"/loans?merchantId={self.merchant_id}&loanId=LEND1",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id or "de04dcca3dee4461a581e8ffed19612e",
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "dpuLoanId": self.dpu_loan_id or "EFL17613857845725084",
                    "lenderLoanId": self.lender_loan_id or "lender-EFL17613857845725084",
                    "originalRequestId": "e37b91d056114e48a466b433934e2068",
                    "lenderCreditId": "CR1",
                    "lenderCompanyId": "LEND1",
                    "lenderDrawdownId": "DRA1",
                    "drawdownStatus": drawdown_status,
                    "failureReason": failure_reason,
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system",
                    "disbursement": {
                        "loanAmount": {"currency": "USD", "amount": f"{float(drawdown_amount):.2f}"},
                        "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "10.00",
                                 "marginRate": "0.00"},
                        "term": "90",
                        "termUnit": "Days",
                        "drawdownSuccessDate": current_date,
                        "actualDrawdownDate": current_date
                    },
                    "repayment": {
                        "expectedRepaymentDate": calculate_future_date(90),
                        "expectedRepaymentAmount": {"currency": "USD", "amount": f"{float(drawdown_amount):.2f}"},
                        "repaymentTerm": "90"
                    }
                }
            }
        }
        self._send_webhook_request(request_body)

    # 功能5已注释：创建PSP授权记录
    # def mock_create_psp_record(self) -> None:
    #     """创建PSP授权记录"""
    #     if not self.seller_id:
    #         log.error("请先执行SPAPI授权获取seller_id")
    #         return
    #
    #     params = {"authorizationId": self.seller_id, "pspId": f"PSP{self.seller_id}"}
    #     result = self._send_request(self.api_config.create_psp_auth_url, params=params)
    #     log.info("创建PSP授权记录成功" if result else "创建PSP授权记录失败")
    #     time.sleep(1)

    def _mock_psp_status(self, is_start: bool = True) -> None:
        """模拟PSP状态更新（复用逻辑，支持开始/完成状态）"""
        if is_start:
            event_type = "psp.verification.started"
            status_prompt = "请输入PSP开始状态：1-PROCESSING 2-FAIL 3-INITIAL\n"
            status_map = {"1": DPUStatus.PROCESSING.value, "2": DPUStatus.FAIL.value, "3": DPUStatus.INITIAL.value}
        else:
            event_type = "psp.verification.completed"
            status_prompt = "请输入PSP完成状态：1-SUCCESS 2-FAIL 3-INITIAL\n"
            status_map = {"1": DPUStatus.SUCCESS.value, "2": DPUStatus.FAIL.value, "3": DPUStatus.INITIAL.value}

        status_input = input_with_validation(prompt=status_prompt, validator=lambda x: x in status_map)
        data = self._build_common_webhook_data(
            event_type,
            status_map[status_input],
            {
                "applicationId": "EFA17590311621044381",
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": self.dpu_auth_token_seller_id,
                "lenderApprovedOfferId": self.lender_approved_offer_id,
                "result": status_map[status_input]
            }
        )
        self._send_webhook_request(data)

    def mock_psp_start_status(self) -> None:
        """模拟PSP开始状态"""
        self._mock_psp_status(is_start=True)

    def mock_psp_completed_status(self) -> None:
        """模拟PSP完成状态"""
        self._mock_psp_status(is_start=False)

    def mock_multi_shop_binding(self) -> None:
        """SP店铺绑定（多店铺第一步）"""
        state = input_with_validation(prompt="请输入state值：\n", validator=lambda x: bool(x),
                                      error_msg="state不能为空！")
        self.generated_selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"

        params = {
            "state": state,
            "selling_partner_id": self.generated_selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }
        full_auth_url = f"{self.api_config.multi_shop_sp_auth_url}?{urlencode(params)}"

        log.info(f"【多店铺】SP绑定ID：{self.generated_selling_partner_id}")
        log.info(f"【多店铺】SP授权URL：{full_auth_url}")

    def mock_multi_shop_3pl_redirect(self) -> None:
        """3PL重定向（多店铺第二步）"""
        if not self.generated_selling_partner_id:
            log.error("无SP绑定ID，请先执行11-SP店铺绑定")
            return

        platform_offer_id = self.get_platform_offer_id(self.generated_selling_partner_id)
        if not platform_offer_id:
            log.error(f"seller_id: {self.generated_selling_partner_id} 无对应platform_offer_id")
            return

        full_redirect_url = f"{self.api_config.redirect_url}?offerId={platform_offer_id}"
        log.info(f"【多店铺】SP绑定ID：{self.generated_selling_partner_id}")
        log.info(f"【多店铺】platform_offer_id：{platform_offer_id}")
        log.info(f"【多店铺】3PL重定向URL：{full_redirect_url}")

    def mock_sp_status_update(self) -> None:
        """SP状态更新（调用 updateOffer 接口）"""
        log.info("开始处理SP状态更新...")

        # 获取 platform_seller_id
        platform_seller_id = input_with_validation(
            prompt="请输入 platform_seller_id：\n",
            validator=lambda x: bool(x.strip()),
            error_msg="platform_seller_id 不能为空！"
        )

        # 从数据库查询 idempotency_key 和 platform_offer_id
        idempotency_key_sql = f"""
            SELECT idempotency_key FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = '{platform_seller_id}'
        """
        platform_offer_id_sql = f"""
            SELECT platform_offer_id FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = '{platform_seller_id}'
        """

        idempotency_key = self.db_executor.execute_sql(idempotency_key_sql)
        platform_offer_id = self.db_executor.execute_sql(platform_offer_id_sql)

        if not idempotency_key:
            log.error(f"未查询到 idempotency_key，platform_seller_id: {platform_seller_id}")
            return
        if not platform_offer_id:
            log.error(f"未查询到 platform_offer_id，platform_seller_id: {platform_seller_id}")
            return

        log.info(f"查询成功 | idempotency_key: {idempotency_key} | platform_offer_id: {platform_offer_id}")

        # 选择状态
        status_map = {
            "1": "SUCCESS",
            "2": "FAIL"
        }
        status_input = input_with_validation(
            prompt="请输入状态：\n1-SUCCESS  2-FAIL\n",
            validator=lambda x: x in status_map,
            error_msg="请输入1或2！"
        )
        send_status = status_map[status_input]

        # 获取失败原因（如果选择 FAIL）
        failure_reason = ""
        if send_status == "FAIL":
            reason_map = {
                "1": "Lender and seller country not align(User do have US shop）",
                "2": "Active credit approval exists",
                "3": "An offer already exists for the seller for the same partner product combination"
            }
            prompt = "请选择失败原因：\n" + "\n".join([f"{k}-{v}" for k, v in reason_map.items()]) + "\n"
            failure_reason = reason_map[input_with_validation(prompt, lambda x: x in reason_map)]

        # 构建请求体
        payload = {
            "idempotencyKey": idempotency_key,
            "sendStatus": send_status,
            "offerId": platform_offer_id,
            "reason": failure_reason
        }

        # 发送请求
        try:
            response = requests.post(
                self.api_config.update_offer_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            log.info(f"SP状态更新成功 | 响应: {response.text[:200]}...")
        except requests.exceptions.RequestException as e:
            error_detail = f"SP状态更新失败: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                try:
                    resp_json = e.response.json()
                    error_detail += f"\n  - TraceId: {resp_json.get('traceId', 'N/A')}"
                    error_detail += f"\n  - Status: {resp_json.get('status', 'N/A')}"
                    error_detail += f"\n  - Message: {resp_json.get('message', 'N/A')}"
                except:
                    error_detail += f"\n  - 响应内容: {e.response.text[:500]}"
            log.error(error_detail)

    def mock_repayment_start_status(self) -> None:
        """模拟还款开始状态通知（固定状态为Start，无需选择状态）"""
        log.info("开始处理还款开始操作...")

        # 获取放款信息
        drawdown_info = self.get_drawdown_info()
        if not drawdown_info:
            log.error("还款操作终止")
            return

        # 获取输入
        principal_amount = float(input_with_validation(
            prompt="请输入还款本金金额：\n",
            validator=validate_numeric_input,
            error_msg="请输入整数或小数！"
        ))
        outstanding_amount = float(input_with_validation(
            prompt="请输入未结清金额：\n",
            validator=validate_numeric_input,
            error_msg="请输入整数或小数！"
        ))

        # 固定状态为Start
        repayment_status = RepaymentStatus.START.value
        failure_reason = None
        interest_amount = 88.00
        total_amount = round(principal_amount + interest_amount, 2)

        # 获取统一的还款ID
        lender_repayment_id = self._get_or_create_lender_repayment_id()

        # 构建请求
        data = self._build_common_webhook_data(
            "repayment.status",
            repayment_status,
            {
                "merchantId": drawdown_info["merchant_id"],
                "dpuLoanId": drawdown_info["loan_id"],
                "lenderLoanId": drawdown_info["lender_loan_id"],
                "lenderRepaymentId": lender_repayment_id,
                "repayment": {
                    "status": repayment_status,
                    "failureReason": failure_reason,
                    "fundSource": "BankTransfer",
                    "paidOn": get_current_time(),
                    "totalPaidAmount": {"currency": "USD", "amount": total_amount},
                    "principalPaidAmount": {"currency": "USD", "amount": principal_amount},
                    "interestPaidAmount": {"currency": "USD", "amount": interest_amount},
                    "feePaidAmount": {"currency": "USD", "amount": 0.00},
                    "outstandingAmount": {"currency": "USD", "amount": outstanding_amount}
                }
            }
        )

        log.info(
            f"还款开始请求发送 | 状态={repayment_status} | 还款ID={lender_repayment_id} | 总金额={total_amount} USD")
        self._send_webhook_request(data)

    def mock_repayment_status(self) -> None:
        """模拟还款状态通知（执行完自动清空还款ID缓存）"""
        log.info("开始处理还款操作...")

        # 获取放款信息
        drawdown_info = self.get_drawdown_info()
        if not drawdown_info:
            log.error("还款操作终止")
            return

        # 获取输入
        principal_amount = float(input_with_validation(
            prompt="请输入还款本金金额：\n",
            validator=validate_numeric_input,
            error_msg="请输入整数或小数！"
        ))
        outstanding_amount = float(input_with_validation(
            prompt="请输入未结清金额：\n",
            validator=validate_numeric_input,
            error_msg="请输入整数或小数！"
        ))

        # 选择还款状态
        status_map = {
            "1": RepaymentStatus.SUCCESS.value,
            "2": RepaymentStatus.FAILURE.value,
            #"3": RepaymentStatus.START.value
        }
        status_input = input_with_validation(
            prompt="请输入还款状态：\n1-Success(成功)  2-Failure(失败) \n",
            validator=lambda x: x in status_map,
            error_msg="请输入1-2！"
        )
        repayment_status = status_map[status_input]

        # 处理失败原因
        failure_reason = None
        if repayment_status == RepaymentStatus.FAILURE.value:
            reason_map = {
                "1": "ER001（银行汇票与实际还款金额不符）",
                "2": "ER002（操作拒绝）"
            }
            prompt = "请选择失败原因编码：\n" + "\n".join([f"{k}-{v}" for k, v in reason_map.items()]) + "\n"
            failure_reason = reason_map[input_with_validation(prompt, lambda x: x in reason_map)].split("（")[0]

        # 计算金额
        interest_amount = 88.00
        total_amount = round(principal_amount + interest_amount, 2)

        # 获取统一的还款ID
        lender_repayment_id = self._get_or_create_lender_repayment_id()

        # 构建请求
        data = self._build_common_webhook_data(
            "repayment.status",
            repayment_status,
            {
                "merchantId": drawdown_info["merchant_id"],
                "dpuLoanId": drawdown_info["loan_id"],
                "lenderLoanId": drawdown_info["lender_loan_id"],
                "lenderRepaymentId": lender_repayment_id,
                "repayment": {
                    "status": repayment_status,
                    "failureReason": failure_reason,
                    "fundSource": "BankTransfer",
                    "paidOn": get_current_time(),
                    "totalPaidAmount": {"currency": "USD", "amount": total_amount},
                    "principalPaidAmount": {"currency": "USD", "amount": principal_amount},
                    "interestPaidAmount": {"currency": "USD", "amount": interest_amount},
                    "feePaidAmount": {"currency": "USD", "amount": 0.00},
                    "outstandingAmount": {"currency": "USD", "amount": outstanding_amount}
                }
            }
        )

        log.info(f"还款请求发送 | 状态={repayment_status} | 还款ID={lender_repayment_id} | 总金额={total_amount} USD")
        self._send_webhook_request(data)

        # 核心修改：执行完还款操作后自动清空缓存
        self.clear_lender_repayment_id()


# ============================ 辅助函数（精简逻辑，提升可读性）============================
def check_is_registered(phone_number: str, db_executor: DatabaseExecutor) -> bool:
    """检查手机号是否已注册（包含merchant_id和3PL授权校验）"""
    try:
        # 校验merchant_id
        merchant_id = db_executor.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone_number}' LIMIT 1"
        )
        if not merchant_id:
            log.error(f"手机号 {phone_number} 未注册")
            return False

        # 校验3PL授权
        offer_id = db_executor.execute_sql(f"""
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = '{merchant_id}' 
            AND authorization_party = '3PL' 
            ORDER BY created_at DESC LIMIT 1
        """)
        if offer_id:
            log.info(f"手机号 {phone_number} 已注册，offer_id: {offer_id}")
        else:
            log.warning(f"手机号 {phone_number} 已注册，但无3PL授权记录")
        return True
    except Exception as e:
        log.error(f"查询注册状态失败: {e}")
        return False


# ============================ 主函数（精简流程，提升用户体验）============================
def main():
    """程序入口（控制整体流程）"""
    log.info(f"当前环境：{ENV}")
    log.info("=" * 50)

    # 初始化数据库连接（上下文管理自动关闭）
    with DatabaseExecutor() as db_executor:
        # 选择操作类型
        register_choice = input_with_validation(
            prompt="请选择操作：1-注册新账号 2-使用现有账号 \n",
            validator=lambda x: x in ("1", "2")
        )

        # 处理注册/登录
        if register_choice == "1":
            phone_number = DPUMockService.register_new_account()
        else:
            phone_number = input_with_validation(
                prompt="请输入手机号：\n",
                validator=lambda x: validate_phone_number(x) and check_is_registered(x, db_executor),
                error_msg="请输入有效的已注册手机号（8位或11位数字）！"
            )

        # 初始化服务
        mock_service = DPUMockService(phone_number, db_executor)

        # 主菜单配置（结构化管理，便于维护）- 移除了1(spapi授权)、5(创建psp记录)、14(清空缓存)选项
        menu = """
请输入要执行的操作：
1 - link-sp-3pl关联      2 - 核保(underwritten)    3 - 审批(approved)
4 - psp开始(psp_start)   5 - psp完成(psp_completed)  6 - 电子签(esign)
7 - 放款(drawdown)       8 - 还款开始(repayment_start)  9 - 还款(repayment)
10 - SP店铺绑定（多店铺第一步）  11 - SP状态更新  12 - 3PL重定向（多店铺第二步）
q - 退出
"""
        operation_map = {
            "1": mock_service.mock_link_sp_3pl_shop,
            "2": mock_service.mock_underwritten_status,
            "3": mock_service.mock_approved_offer_status,
            "4": mock_service.mock_psp_start_status,
            "5": mock_service.mock_psp_completed_status,
            "6": mock_service.mock_esign_status,
            "7": mock_service.mock_drawdown_status,
            "8": mock_service.mock_repayment_start_status,
            "9": mock_service.mock_repayment_status,
            "10": mock_service.mock_multi_shop_binding,
            "11": mock_service.mock_sp_status_update,
            "12": mock_service.mock_multi_shop_3pl_redirect
        }

        # 菜单循环
        while True:
            log.info(menu)
            operator = input("请输入操作编号：\n").strip().lower()
            if operator == "q":
                log.info("程序已退出")
                break
            if operator in operation_map:
                try:
                    operation_map[operator]()
                except Exception as e:
                    log.error(f"操作执行失败: {e}")
            else:
                log.error("输入无效，请输入正确的操作编号！")
            log.info("=" * 50)


# ============================ 程序启动（捕获异常，优雅退出）============================
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n程序被用户中断")
    except Exception as e:
        log.error(f"程序异常退出: {e}")
        exit(1)