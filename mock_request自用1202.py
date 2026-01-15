# -*- coding: utf-8 -*-
import logging
import time
import uuid
import random
from urllib.parse import urlencode
from enum import Enum
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

import pymysql
import requests
from faker import Faker
from pymysql.constants import CLIENT
from pymysql.err import OperationalError

# ============================ 基础配置 ============================
# 环境配置（支持：sit/local/dev/uat/preprod）
ENV = "sit"

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

# 日志配置（仅ERROR级别标红，其他为白色，统一格式）
class ColorFormatter(logging.Formatter):
    """日志颜色格式化器"""
    RED = "\033[91m"
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.ERROR:
            # ERROR日志标红
            return f"{self.RED}[{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}] " \
                   f"[{record.levelname}] {record.lineno} {record.funcName}: {record.getMessage()}{self.RESET}"
        # 其他日志白色
        return f"[{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}] " \
               f"[{record.levelname}] {record.lineno} {record.funcName}: {record.getMessage()}"

# 配置日志处理器
handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler],
    force=True  # 强制覆盖默认配置
)
log = logging.getLogger(__name__)

# 初始化工具实例
faker = Faker("zh_CN")

# ============================ 工具函数 ============================
def generate_uuid37() -> str:
    """生成37位UUID字符串（替代nanoid）"""
    return str(uuid.uuid4())


def validate_phone_number(phone_number: str) -> bool:
    """验证手机号格式（支持8位或11位数字）"""
    return phone_number.isdigit() and len(phone_number) in [11, 8]


def get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间字符串"""
    return time.strftime(fmt, time.localtime())


def get_utc_time() -> str:
    """获取UTC时间字符串（符合ISO格式）"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def validate_numeric_input(input_str: str) -> bool:
    """验证输入是否为有效数字（支持整数和小数）"""
    return input_str.replace('.', '', 1).isdigit() if input_str else False


def input_with_validation(prompt: str, validator: Callable[[str], bool], error_msg: str) -> str:
    """带验证的输入函数（通用封装，减少重复代码）"""
    while True:
        user_input = input(prompt).strip()
        if validator(user_input):
            return user_input
        log.error(error_msg)


# ============================ 枚举类定义 ============================
class SanctionStatus(Enum):
    """application表制裁状态枚举"""
    HIT = 'HIT'  # 命中制裁
    NOT_HIT = 'NOT_HIT'  # 未命中制裁
    INITIAL = 'INITIAL'  # 初始状态


class ReturnedFailureReason(Enum):
    """审批退回失败原因枚举"""
    INCORRECT_BRN = "不正确 BRN"
    FAILED_TO_OBTAIN_CUSTOMER_ID = "未能获取客户 ID 号码"
    ID_MISMATCH_WITH_CR_RECORD = "ID 号码与 CR 记录不相符"
    FAILED_COMPANY_STRUCTURE_VERIFICATION = "未能通过公司结构校验"
    REQUIRES_MANUAL_AML_VERIFICATION = "需要人工处理反洗钱验证"


class DPUStatus(Enum):
    """DPU状态枚举：psp/esign用SUCCESS/FAIL，其余用APPROVED/REJECTED"""
    INITIAL = 'INITIAL'  # 初始状态
    SUBMITTED = 'SUBMITTED'  # 已提交
    APPROVED = 'APPROVED'  # 已批准
    REJECTED = 'REJECTED'  # 已拒绝
    RETURNED = 'RETURNED'  # 已退回
    SUCCESS = "SUCCESS"  # 成功
    FAIL = "FAIL"  # 失败
    PROCESSING = "PROCESSING"  # 处理中


class RepaymentStatus(Enum):
    """还款状态枚举"""
    SUCCESS = "Success"  # 还款成功
    FAIL = "Fail"  # 还款失败
    PENDING = "Pending"  # 处理中
    PARTIAL = "Partial"  # 部分还款


# ============================ 配置数据类 ============================
@dataclass(frozen=True)  # 不可变数据类，更安全
class ApiConfig:
    """API配置数据类（集中管理接口地址，新增多店铺SP授权路径）"""
    base_url: str
    create_offerid_url: str
    redirect_url: str
    register_url: str
    login_url: str
    spapi_auth_url: str  # 原有SP授权URL（保持不变）
    multi_shop_sp_auth_url: str  # 新增：多店铺SP授权URL
    link_sap_3pl_url: str
    create_psp_auth_url: str
    webhook_url: str
    txt_path: str


class DatabaseConfig:
    """数据库配置类（支持多环境切换）"""
    # 环境-数据库配置映射（私有常量，外部不可修改）
    _DATABASE_CONFIG_DICT: Dict[str, Dict[str, Any]] = {
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
    def get_config(cls, env: str = ENV) -> Dict[str, Any]:
        """获取指定环境的数据库配置（环境校验）"""
        config = cls._DATABASE_CONFIG_DICT.get(env)
        if not config:
            raise ValueError(f"不支持的环境：{env}（支持：{','.join(cls._DATABASE_CONFIG_DICT.keys())}）")
        return config


# ============================ 数据库执行器 ============================
class DatabaseExecutor:
    """数据库操作执行器（封装连接、查询、执行逻辑，支持自动重连）"""

    def __init__(self, env: str = ENV):
        self.config = DatabaseConfig.get_config(env)
        self.conn: Optional[pymysql.connections.Connection] = None
        self.cursor: Optional[pymysql.cursors.Cursor] = None
        self.connect()

    def connect(self) -> None:
        """建立数据库连接"""
        try:
            self.conn = pymysql.connect(
                **self.config,
                autocommit=True,
                client_flag=CLIENT.INTERACTIVE
            )
            self.cursor = self.conn.cursor()
            log.info("数据库连接成功")
        except Exception as e:
            log.error(f"数据库连接失败: {e}")
            raise

    def reconnect(self) -> None:
        """数据库重连（连接失效时自动调用）"""
        try:
            if self.conn:
                self.conn.close()
            self.connect()
            log.info("数据库重连成功")
        except Exception as e:
            log.error(f"数据库重连失败: {e}")
            raise

    def _execute_with_retry(self, func: Callable[[str], Any], sql: str, retry: int = 3) -> Any:
        """带重试机制的执行包装器（统一处理连接失效问题）"""
        try:
            log.debug(f"执行SQL: {sql.strip().replace('\n', ' ')}")  # 简化SQL日志输出
            return func(sql)
        except OperationalError as e:
            # 处理常见的连接失效错误码
            if e.args[0] in (2006, 2013, 10054) and retry > 0:
                log.warning(f"数据库连接失效，剩余{retry}次重连尝试...")
                self.reconnect()
                return self._execute_with_retry(func, sql, retry - 1)
            log.error(f"SQL执行出错: {e}, SQL: {sql.strip().replace('\n', ' ')}")
            raise
        except Exception as e:
            log.error(f"SQL执行出错: {e}, SQL: {sql.strip().replace('\n', ' ')}")
            raise

    def execute_sql(self, sql: str, retry: int = 3) -> Optional[Any]:
        """执行SQL语句（支持查询/更新/删除，查询返回第一条结果的第一个字段）"""

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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出（自动关闭连接）"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        log.info("数据库连接已关闭")


# ============================ DPU模拟服务 ============================
class DPUMockService:
    """DPU状态模拟服务（封装所有业务操作，职责单一）"""
    # 类变量（共享状态）
    generated_selling_partner_id: Optional[str] = None

    def __init__(self, phone_number: str, db_executor: DatabaseExecutor):
        self.phone_number = phone_number  # 手机号（核心标识）
        self.db_executor = db_executor  # 数据库执行器实例
        self.merchant_id = self.get_merchant_id()  # 商户ID（初始化时获取）
        self.seller_id: Optional[str] = None  # SP授权的seller_id
        self.api_config: ApiConfig = self._init_api_config()  # API配置

    def _init_api_config(self) -> ApiConfig:
        """初始化API配置（根据环境自动切换，返回不可变实例）"""
        # 基础URL映射
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "local": "http://192.168.11.3:8080"
        }

        base_url = base_url_dict[ENV]
        # 重定向URL特殊处理（uat/preprod环境不同）
        redirect_url = (
            f"{base_url}/dpu-merchant/amazon/redirect"
            if ENV in ["uat", "preprod"]
            else f"https://dpu-gateway-{ENV}.dowsure.com/dpu-merchant/amazon/redirect"
        )

        # 原有SP授权URL（保持不变）
        spapi_auth_url = f"{base_url}/dpu-merchant/amz/sp/shop/auth"
        # 新增：多店铺SP授权URL（使用参考路径 /dpu-auth/amazon-sp/auth）
        multi_shop_sp_auth_url = f"{base_url}/dpu-auth/amazon-sp/auth"

        # 构建并返回不可变API配置（包含新增的多店铺授权路径）
        return ApiConfig(
            base_url=base_url,
            create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            redirect_url=redirect_url,
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=spapi_auth_url,  # 原有路径保持不变
            multi_shop_sp_auth_url=multi_shop_sp_auth_url,  # 新增多店铺专属路径
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            txt_path=f"./register_{ENV}.txt"
        )

    # ============================ 数据查询方法（抽离SQL，提升可维护性）============================
    def get_merchant_id(self) -> Optional[str]:
        """根据手机号查询最新的merchant_id"""
        sql = f"""
            SELECT merchant_id FROM dpu_users 
            WHERE phone_number = '{self.phone_number}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db_executor.execute_sql(sql)

    def get_platform_offer_id(self, seller_id: str) -> Optional[str]:
        """根据seller_id查询platform_offer_id"""
        sql = f"""
            SELECT platform_offer_id FROM dpu_manual_offer 
            WHERE platform_seller_id = '{seller_id}'
            ORDER BY created_at DESC LIMIT 1;
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
            ORDER BY created_at DESC LIMIT 1;
        """
        drawdown_info = self.db_executor.execute_query(sql)

        if not drawdown_info:
            log.error(f"merchant_id: {self.merchant_id} 无对应放款记录")
            return None

        log.info(f"获取放款信息成功: {drawdown_info}")
        return drawdown_info

    # ============================ 快捷属性（使用@property简化访问）============================
    @property
    def merchant_account_id(self) -> Optional[str]:
        """获取merchant_account_id（快捷属性）"""
        sql = f"""
            SELECT merchant_account_id FROM dpu_merchant_account_limit 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db_executor.execute_sql(sql)

    @property
    def application_unique_id(self) -> Optional[str]:
        """获取application_unique_id（快捷属性）"""
        sql = f"""
            SELECT application_unique_id FROM dpu_application 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db_executor.execute_sql(sql)

    @property
    def lender_approved_offer_id(self) -> str:
        """生成lender_approved_offer_id（基于application_unique_id）"""
        return f"lender-{self.application_unique_id}" if self.application_unique_id else "lender-default"

    @property
    def dpu_loan_id(self) -> Optional[str]:
        """获取dpu_loan_id（快捷属性）"""
        sql = f"""
            SELECT loan_id FROM dpu_drawdown 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db_executor.execute_sql(sql)

    @property
    def lender_loan_id(self) -> str:
        """生成lender_loan_id（基于dpu_loan_id）"""
        return f"lender-{self.dpu_loan_id}" if self.dpu_loan_id else "lender-loan-default"

    @property
    def dpu_limit_application_id(self) -> Optional[str]:
        """获取limit_application_unique_id（快捷属性）"""
        sql = f"""
            SELECT limit_application_unique_id FROM dpu_limit_application 
            WHERE merchant_id = '{self.merchant_id}' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db_executor.execute_sql(sql)

    @property
    def dpu_auth_token_seller_id(self) -> Optional[str]:
        """获取SP授权的seller_id（快捷属性）"""
        sql = f"""
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = '{self.merchant_id}' 
            AND authorization_party = 'SP' 
            ORDER BY created_at DESC LIMIT 1;
        """
        return self.db_executor.execute_sql(sql)

    # ============================ 公共请求方法（统一封装，减少冗余）============================
    def _send_webhook_request(self, request_body: Dict[str, Any]) -> bool:
        """发送webhook请求（统一异常处理和日志记录）"""
        try:
            response = requests.post(
                self.api_config.webhook_url,
                json=request_body,
                timeout=30
            )
            if response.status_code == 200:
                log.info(f"Webhook请求成功，响应: {response.text[:100]}...")  # 截取响应，避免日志过长
                return True
            log.error(f"Webhook请求失败，状态码: {response.status_code}, 响应: {response.text[:200]}...")
            return False
        except Exception as e:
            log.error(f"Webhook请求异常: {e}")
            return False

    # ============================ 业务操作方法（按功能分类，逻辑清晰）============================
    @classmethod
    def get_journey_by_input(cls) -> str:
        """获取用户选择的注册流程（200K/500K/2000K）"""
        journey_map = {"1": "200K", "2": "500K", "3": "2000K"}
        prompt = "请输入注册流程：1-200K 2-500K 3-2000K \n"
        validator = lambda x: x in journey_map.keys()
        user_input = input_with_validation(prompt, validator, "输入错误，请重新输入！")
        return journey_map[user_input]

    @classmethod
    def _create_offer_id(cls, journey: str, api_config: ApiConfig) -> Optional[str]:
        """创建offer_id（内部方法，按流程生成对应额度）"""
        journey_amount = {"200K": 100000, "500K": 800000, "2000K": 6000000}
        yearly_amount = journey_amount.get(journey.upper())
        if not yearly_amount:
            log.error(f"不支持的流程: {journey}")
            return None

        try:
            resp = requests.post(
                api_config.create_offerid_url,
                json={"yearlyRepaymentAmount": yearly_amount},
                timeout=30
            )
            resp.raise_for_status()  # 触发HTTP错误
            return resp.json().get("data", {}).get("amazon3plOfferId")
        except requests.exceptions.RequestException as e:
            log.error(f"创建offer_id失败: {e}")
            return None

    @classmethod
    def register_new_account(cls) -> str:
        """注册新账号（自动生成手机号、邮箱，返回注册成功的手机号）"""
        journey = cls.get_journey_by_input()
        log.info(f"开始注册新账号，流程: {journey}")

        # 生成随机账号信息
        phone_number = faker.phone_number()
        email = f"{phone_number}y@163doushabao.com"

        # 初始化API配置（注册时单独处理，保持原有SP授权路径不变）
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
            redirect_url=f"{base_url}/dpu-merchant/amazon/redirect" if ENV in ["uat", "preprod"]
            else f"https://dpu-gateway-{ENV}.dowsure.com/dpu-merchant/amazon/redirect",
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=f"{base_url}/dpu-merchant/amz/sp/shop/auth",  # 原有路径不变
            multi_shop_sp_auth_url=f"{base_url}/dpu-auth/amazon-sp/auth",  # 新增多店铺路径
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            txt_path=f"./register_{ENV}.txt"
        )

        # 创建offer_id（失败则重试）
        offer_id = cls._create_offer_id(journey, api_config)
        if not offer_id:
            log.error("创建offer_id失败，重新注册...")
            return cls.register_new_account()

        # 构建注册参数
        register_payload = {
            "phone": phone_number,
            "areaCode": "+86",
            "code": "666666",
            "email": email,
            "offerId": offer_id
        }
        redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"

        try:
            # 执行重定向和注册
            requests.get(redirect_url, timeout=30)
            resp_register = requests.post(
                api_config.register_url,
                json=register_payload,
                timeout=30
            )
            resp_register.raise_for_status()

            # 解析响应JSON（捕获JSON解析失败异常）
            try:
                resp_data = resp_register.json()
            except ValueError as e:
                log.error(f"响应JSON解析失败: {e}，响应内容: {resp_register.text[:500]}")  # 打印前500字符避免日志过长
                raise  # 抛出异常触发重试

            # 按实际响应结构提取token（支持嵌套层级，添加多级容错）
            # 步骤：先取data -> 再取token，每一步都做容错处理
            data = resp_data.get("data", {})  # 若没有data字段，返回空字典
            token = data.get("token", "未获取到token")  # 若data中没有token，返回默认值

            # 打印token（控制台+日志，格式更清晰）
            print(f"✅ 注册成功！手机号: {phone_number} | Token: {token}")

            # 写入注册记录到文件
            with open(api_config.txt_path, 'a', newline='', encoding='utf-8') as f:
                f.write(f"\n{journey}\n{phone_number}\n{redirect_url}\n")
            log.info(f"注册成功，手机号: {phone_number}，记录已写入{api_config.txt_path}")
            return phone_number

        except requests.exceptions.RequestException as e:
            log.error(f"注册失败: {e}")
            return cls.register_new_account()

    def mock_spapi_auth(self) -> None:
        """模拟SPAPI授权回调（使用原有SP授权路径，保持不变）"""
        # 获取店铺编号（带验证）
        shop_num = input_with_validation(
            prompt="请输入店铺编号(1,2,3...): \n",
            validator=lambda x: x.isdigit() and int(x) >= 1,
            error_msg="输入错误，请输入正整数！"
        )

        # 生成seller_id
        self.seller_id = f"{shop_num}BTC6RWJD{self.phone_number}"
        payload = {
            "phone": self.phone_number,
            "status": "ACTIVE",
            "dpu_token": "dpu_token",
            "sellerId": self.seller_id,
            "authorization_code": "authorization_code",
            "refresh_token_expires_time": "2025-09-19T10:09:07.921Z",
            "access_token": "access_token sunt",
            "refresh_token": "refresh_token minim et anim sunt"
        }

        try:
            # 仍使用原有SP授权路径
            response = requests.post(self.api_config.spapi_auth_url, json=payload, timeout=30)
            response.raise_for_status()
            if response.json().get("code") == 200:
                log.info(f"SPAPI授权成功（原有路径），seller_id: {self.seller_id}")
            else:
                log.error(f"SPAPI授权失败（原有路径）: {response.text}")
        except requests.exceptions.RequestException as e:
            log.error(f"SPAPI授权异常（原有路径）: {e}")

    def mock_link_sp_3pl_shop(self) -> None:
        """模拟关联SP和3PL店铺"""
        log.info("开始关联SP和3PL店铺...")
        try:
            response = requests.post(
                self.api_config.link_sap_3pl_url,
                params={"phone": self.phone_number},
                timeout=30
            )
            response.raise_for_status()
            if response.json().get("code") == 200:
                log.info("关联成功")
            else:
                log.error(f"关联失败: {response.text}")
        except requests.exceptions.RequestException as e:
            log.error(f"关联异常: {e}")

    def mock_underwritten_status(self) -> None:
        """模拟核保状态更新（支持APPROVED/REJECTED）"""
        # 获取评估额度（带验证）
        underwritten_amount = input_with_validation(
            prompt="请输入评估额度：\n",
            validator=lambda x: x.isdigit(),
            error_msg="请输入整数！"
        )

        # 获取核保状态
        status_input = input_with_validation(
            prompt="请输入核保状态：1-APPROVED 2-REJECTED\n",
            validator=lambda x: x in ["1", "2"],
            error_msg="输入错误，请输入1或2！"
        )
        underwritten_status = DPUStatus.APPROVED.value if status_input == "1" else DPUStatus.REJECTED.value

        # 构建请求体
        request_body = {
            "data": {
                "eventType": "underwrittenLimit.completed",
                "eventId": generate_uuid37(),
                "eventMessage": "核保完成通知",
                "enquiryUrl": "https://api.example.com/enquiry/123",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": self.merchant_id,
                    "dpuMerchantAccountId": [{"MerchantAccountId": self.dpu_auth_token_seller_id}]
                    if self.dpu_auth_token_seller_id else [],
                    "dpuLimitApplicationId": self.dpu_limit_application_id,
                    "originalRequestId": "req_EFAL17621784619057169",
                    "status": underwritten_status,
                    "failureReason": None,
                    "lastUpdatedOn": get_utc_time().replace('T', ' ').replace('Z', ''),
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
                            "underwrittenAmount": {"currency": "CNY", "amount": underwritten_amount},
                            "availableLimit": {"currency": "CNY", "amount": "0.00"},
                            "signedLimit": {"currency": "CNY", "amount": "0.00"},
                            "watermark": {"currency": "CNY", "amount": "0.00"}
                        }
                    }
                }
            }
        }

        self._send_webhook_request(request_body)

    def mock_approved_offer_status(self) -> None:
        """模拟审批状态更新（支持APPROVED/RETURNED/REJECTED）"""
        # 获取授信额度（带验证）
        approved_amount = round(
            float(input_with_validation(
                prompt="请输入授信额度：\n",
                validator=lambda x: x.isdigit(),
                error_msg="请输入整数！"
            )), 2
        )

        # 获取审批状态
        status_input = input_with_validation(
            prompt="请输入审批状态：1-APPROVED 2-RETURNED 3-REJECTED\n",
            validator=lambda x: x in ["1", "2", "3"],
            error_msg="输入错误，请输入1/2/3！"
        )

        status_map = {
            "1": DPUStatus.APPROVED.value,
            "2": DPUStatus.RETURNED.value,
            "3": DPUStatus.REJECTED.value
        }
        approved_status = status_map[status_input]
        failure_reason = self._get_failure_reason() if approved_status == DPUStatus.RETURNED.value else None

        # 构建请求体
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

    def _get_failure_reason(self) -> str:
        """获取审批退回的失败原因（内部辅助方法）"""
        reason_map = {
            "1": ReturnedFailureReason.INCORRECT_BRN.value,
            "2": ReturnedFailureReason.FAILED_TO_OBTAIN_CUSTOMER_ID.value,
            "3": ReturnedFailureReason.ID_MISMATCH_WITH_CR_RECORD.value,
            "4": ReturnedFailureReason.FAILED_COMPANY_STRUCTURE_VERIFICATION.value,
            "5": ReturnedFailureReason.REQUIRES_MANUAL_AML_VERIFICATION.value
        }
        reason_input = input_with_validation(
            prompt="""请选择退回原因：
1-不正确BRN 
2-未能获取客户ID号码 
3-ID号码与CR记录不相符 
4-未能通过公司结构校验 
5-需要人工处理反洗钱验证
""",
            validator=lambda x: x in reason_map.keys(),
            error_msg="输入错误，请输入1-5！"
        )
        return reason_map[reason_input]

    def mock_esign_status(self) -> None:
        """模拟电子签状态更新（支持SUCCESS/FAIL）"""
        # 获取签约额度（带验证）
        signed_amount = round(
            float(input_with_validation(
                prompt="请输入已签约额度：\n",
                validator=lambda x: x.isdigit(),
                error_msg="请输入整数！"
            )), 2
        )

        # 获取电子签状态
        status_input = input_with_validation(
            prompt="请输入电子签状态：1-SUCCESS 2-FAIL\n",
            validator=lambda x: x in ["1", "2"],
            error_msg="输入错误，请输入1或2！"
        )
        esign_status = DPUStatus.SUCCESS.value if status_input == "1" else DPUStatus.FAIL.value

        # 构建请求体
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
                    "result": esign_status,
                    "failureReason": None,
                    "signedLimit": {"amount": signed_amount, "currency": "USD"},
                    "lastUpdatedOn": get_utc_time().replace('T', ' ').replace('Z', ''),
                    "lastUpdatedBy": "esign_system"
                }
            }
        }

        self._send_webhook_request(request_body)

    def mock_drawdown_status(self) -> None:
        """模拟放款状态更新（支持APPROVED/REJECTED）"""
        # 获取放款额度（带验证）
        drawdown_amount = input_with_validation(
            prompt="请输入放款额度：\n",
            validator=lambda x: x.isdigit(),
            error_msg="请输入整数！"
        )

        # 获取放款状态
        status_input = input_with_validation(
            prompt="请输入放款状态：1-APPROVED 2-REJECTED\n",
            validator=lambda x: x in ["1", "2"],
            error_msg="输入错误，请输入1或2！"
        )
        drawdown_status = DPUStatus.APPROVED.value if status_input == "1" else DPUStatus.REJECTED.value

        # 构建请求体
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
                    "dpuLoanId": self.dpu_loan_id,
                    "lenderLoanId": self.lender_loan_id,
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

        self._send_webhook_request(request_body)

    def mock_create_psp_record(self) -> None:
        """创建PSP授权记录（依赖seller_id）"""
        if not self.seller_id:
            log.error("请先执行SPAPI授权获取seller_id")
            return

        params = {"authorizationId": self.seller_id, "pspId": f"PSP{self.seller_id}"}
        try:
            response = requests.post(self.api_config.create_psp_auth_url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(1)
            log.info("创建PSP授权记录成功")
        except requests.exceptions.RequestException as e:
            log.error(f"创建PSP授权记录失败: {e}")

    def _mock_psp_status(self, is_start: bool = True) -> None:
        """模拟PSP状态更新（内部统一方法，减少重复代码）"""
        # 状态配置
        if is_start:
            event_type = "psp.verification.started"
            event_msg = "PSP验证已开始"
            status_prompt = "请输入PSP开始状态：1-PROCESSING 2-FAIL 3-INITIAL\n"
            status_map = {"1": DPUStatus.PROCESSING.value, "2": DPUStatus.FAIL.value, "3": DPUStatus.INITIAL.value}
        else:
            event_type = "psp.verification.completed"
            event_msg = "PSP验证已完成"
            status_prompt = "请输入PSP完成状态：1-SUCCESS 2-FAIL 3-INITIAL\n"
            status_map = {"1": DPUStatus.SUCCESS.value, "2": DPUStatus.FAIL.value, "3": DPUStatus.INITIAL.value}

        # 获取状态（带验证）
        status_input = input_with_validation(
            prompt=status_prompt,
            validator=lambda x: x in status_map.keys(),
            error_msg="输入错误，请输入1-3！"
        )
        psp_status = status_map[status_input]

        # 构建请求体
        request_body = {
            "data": {
                "eventType": event_type,
                "eventId": generate_uuid37(),
                "eventMessage": event_msg,
                "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                "datetime": get_utc_time(),
                "applicationId": "EFA17590311621044381",
                "details": {
                    "pspId": "pspId123457",
                    "pspName": "AirWallex",
                    "merchantAccountId": self.dpu_auth_token_seller_id,
                    "merchantId": self.merchant_id,
                    "lenderApprovedOfferId": self.lender_approved_offer_id,
                    "result": psp_status,
                    "failureReason": None,
                    "lastUpdatedOn": get_utc_time().replace('T', ' ').replace('Z', ''),
                    "lastUpdatedBy": "system_psp"
                }
            }
        }

        self._send_webhook_request(request_body)

    def mock_psp_start_status(self) -> None:
        """模拟PSP开始状态（对外接口）"""
        self._mock_psp_status(is_start=True)

    def mock_psp_completed_status(self) -> None:
        """模拟PSP完成状态（对外接口）"""
        self._mock_psp_status(is_start=False)

    def mock_multi_shop_binding(self) -> None:
        """第一步：SP店铺绑定（多店铺专属，使用新增的多店铺SP授权路径）"""
        # 输入state参数（带验证）
        state = input_with_validation(
            prompt="请输入state值：\n",
            validator=lambda x: bool(x),
            error_msg="state不能为空，请重新输入！"
        )

        # 生成selling_partner_id并存储
        random_suffix = random.randint(10000, 99999)
        self.generated_selling_partner_id = f"spshouquanfs{random_suffix}"

        # 拼接URL（关键修改：使用新增的多店铺SP授权路径）
        params = {
            "state": state,
            "selling_partner_id": self.generated_selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }
        # 多店铺绑定使用新增路径 multi_shop_sp_auth_url
        full_auth_url = f"{self.api_config.multi_shop_sp_auth_url}?{urlencode(params)}"

        # 输出日志（标注多店铺专属）
        log.info(f"【多店铺】SP绑定ID：{self.generated_selling_partner_id}")
        log.info(f"【多店铺】SP授权URL：{full_auth_url}")

    def mock_multi_shop_3pl_redirect(self) -> None:
        """第二步：3PL重定向（生成重定向URL）"""
        # 自动获取SP绑定ID
        selling_partner_id = self.generated_selling_partner_id
        if not selling_partner_id:
            log.error("无SP绑定ID，请先执行12-SP店铺绑定")
            return

        # 查询offer_id
        platform_offer_id = self.get_platform_offer_id(selling_partner_id)
        if not platform_offer_id:
            log.error(f"seller_id: {selling_partner_id} 无对应platform_offer_id")
            return

        # 拼接URL并输出
        full_redirect_url = f"{self.api_config.redirect_url}?offerId={platform_offer_id}"
        log.info(f"【多店铺】SP绑定ID：{selling_partner_id}")
        log.info(f"【多店铺】platform_offer_id：{platform_offer_id}")
        log.info(f"【多店铺】3PL重定向URL：{full_redirect_url}")

    def mock_repayment_status(self) -> None:
        """模拟还款状态通知（支持多状态和金额输入）"""
        log.info("开始处理还款操作...")

        # 1. 校验放款信息
        drawdown_info = self.get_drawdown_info()
        if not drawdown_info:
            log.error("还款操作终止")
            return

        # 2. 获取用户输入（本金、未结清金额）
        principal_amount = float(input_with_validation(
            prompt="请输入还款本金金额：\n",
            validator=validate_numeric_input,
            error_msg="输入无效，请输入整数或小数！"
        ))
        outstanding_amount = float(input_with_validation(
            prompt="请输入未结清金额：\n",
            validator=validate_numeric_input,
            error_msg="输入无效，请输入整数或小数！"
        ))

        # 3. 获取还款状态
        repayment_status = self._get_repayment_status()

        # 4. 计算总还款金额（本金 + 固定利息88.00）
        interest_amount = 88.00
        total_amount = round(principal_amount + interest_amount, 2)

        # 5. 构建请求体
        request_body = {
            "data": {
                "eventType": "repayment.status",
                "eventId": generate_uuid37(),
                "eventMessage": "还款状态通知",
                "enquiryUrl": "https://api.example.com/enquiry/123",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": drawdown_info["merchant_id"],
                    "dpuLoanId": drawdown_info["loan_id"],
                    "lenderLoanId": drawdown_info["lender_loan_id"],
                    "lenderCompanyId": "LC1122334455",
                    "lenderCreditId": "LCR6677889900",
                    "lenderApproveOfferId": "LAO5566778899",
                    "lenderDrawdownId": "LDD4455667788",
                    "lenderRepaymentId": f"LRP{generate_uuid37()[:10].upper()}",
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system_user_001",
                    "repayment": {
                        "status": repayment_status,
                        "failureReason": None if repayment_status == RepaymentStatus.SUCCESS.value else "还款失败原因",
                        "fundSource": "BankTransfer",
                        "paidOn": get_current_time(),
                        "totalPaidAmount": {"currency": "USD", "amount": total_amount},
                        "principalPaidAmount": {"currency": "USD", "amount": principal_amount},
                        "interestPaidAmount": {"currency": "USD", "amount": interest_amount},
                        "feePaidAmount": {"currency": "USD", "amount": 0.00},
                        "outstandingAmount": {"currency": "USD", "amount": outstanding_amount}
                    }
                }
            }
        }

        # 6. 发送请求
        log.info(f"还款请求信息：状态={repayment_status}，总金额={total_amount} USD")
        self._send_webhook_request(request_body)

    def _get_repayment_status(self) -> str:
        """获取还款状态（内部辅助方法）"""
        status_map = {
            "1": RepaymentStatus.SUCCESS.value,
            "2": RepaymentStatus.FAIL.value,
            "3": RepaymentStatus.PENDING.value,
            "4": RepaymentStatus.PARTIAL.value
        }
        status_input = input_with_validation(
            prompt="""请输入还款状态：
1-Success(成功)  2-Fail(失败)  
3-Pending(处理中)  4-Partial(部分还款)
""",
            validator=lambda x: x in status_map.keys(),
            error_msg="输入错误，请输入1-4！"
        )
        return status_map[status_input]


# ============================ 辅助函数 ============================
def check_is_registered(phone_number: str, db_executor: DatabaseExecutor) -> bool:
    """检查手机号是否已注册（包含merchant_id和3PL授权校验）"""
    try:
        # 校验merchant_id是否存在
        sql = f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone_number}' LIMIT 1;"
        merchant_id = db_executor.execute_sql(sql)
        if not merchant_id:
            log.error(f"手机号 {phone_number} 未注册")
            return False

        # 校验3PL授权记录
        sql = f"""
            SELECT authorization_id FROM dpu_auth_token 
            WHERE merchant_id = '{merchant_id}' 
            AND authorization_party = '3PL' 
            ORDER BY created_at DESC LIMIT 1;
        """
        offer_id = db_executor.execute_sql(sql)
        if offer_id:
            log.info(f"手机号 {phone_number} 已注册，offer_id: {offer_id}")
        else:
            log.warning(f"手机号 {phone_number} 已注册，但无3PL授权记录")

        return True
    except Exception as e:
        log.error(f"查询注册状态失败: {e}")
        return False


# ============================ 主函数 ============================
def main():
    """程序入口（控制整体流程）"""
    log.info(f"当前环境：{ENV}")
    log.info("=" * 50)

    # 初始化数据库连接（使用上下文管理器，自动管理连接生命周期）
    with DatabaseExecutor() as db_executor:
        # 选择注册方式
        register_choice = input_with_validation(
            prompt="请选择操作：1-注册新账号 2-使用现有账号 \n",
            validator=lambda x: x in ["1", "2"],
            error_msg="输入错误，请重新输入！"
        )

        # 处理注册/登录
        phone_number: str
        if register_choice == "1":
            phone_number = DPUMockService.register_new_account()
        else:
            # 校验现有账号
            phone_number = input_with_validation(
                prompt="请输入手机号：\n",
                validator=lambda x: validate_phone_number(x) and check_is_registered(x, db_executor),
                error_msg="请输入有效的已注册手机号（8位或11位数字）！"
            )

        # 初始化DPU服务
        mock_service = DPUMockService(phone_number, db_executor)

        # 主菜单循环
        menu = """
请输入要执行的操作：
1 - spapi授权回调  2 - link-sp-3pl关联    3 - 核保(underwritten)
4 - 审批(approved)       5 - 创建psp记录(不用做) 6 - psp开始(psp_start)
7 - psp完成(psp_completed) 8 - 电子签(esign)     9 - 放款(drawdown)
11 - 还款(repayment)     12 - SP店铺绑定（多店铺第一步）  13 - 3PL重定向（多店铺第二步）
q - 退出
"""

        operation_map: Dict[str, Callable[[], None]] = {
            "1": mock_service.mock_spapi_auth,
            "2": mock_service.mock_link_sp_3pl_shop,
            "3": mock_service.mock_underwritten_status,
            "4": mock_service.mock_approved_offer_status,
            "5": mock_service.mock_create_psp_record,
            "6": mock_service.mock_psp_start_status,
            "7": mock_service.mock_psp_completed_status,
            "8": mock_service.mock_esign_status,
            "9": mock_service.mock_drawdown_status,
            "11": mock_service.mock_repayment_status,
            "12": mock_service.mock_multi_shop_binding,
            "13": mock_service.mock_multi_shop_3pl_redirect
        }

        while True:
            log.info(menu)
            operator = input("请输入操作编号：\n").strip().lower()

            # 退出逻辑
            if operator == "q":
                log.info("程序已退出")
                break

            # 执行对应操作
            try:
                if operator in operation_map:
                    operation_map[operator]()
                else:
                    log.error("输入无效，请输入正确的操作编号！")
            except Exception as e:
                log.error(f"操作执行失败: {e}")

            log.info("=" * 50)


# ============================ 程序启动 ============================
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n程序被用户中断")
    except Exception as e:
        log.error(f"程序异常退出: {e}")
        exit(1)