# -*- coding: utf-8 -*-
"""Web 适配器：将 DPUMockService 的 input() 调用改为参数传入，返回结构化结果"""
import sys
import json
import random
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlencode

# 确保能导入项目根目录的 mock_sit 模块
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mock_sit import (
    DPUMockService, DatabaseExecutor, ApiConfig, DatabaseConfig,
    DPUStatus, RepaymentStatus, DrawdownFailureReason, ReturnedFailureReason,
    generate_uuid37, get_utc_time, get_current_time, calculate_future_date,
    validate_numeric_input, validate_phone_number, SCRIPT_DIR,
    log, faker
)
import requests as http_requests

log = logging.getLogger("mock_sit")


class WebDPUMockService(DPUMockService):
    """Web 适配器：所有 input() 改为方法参数，所有方法返回结构化 dict"""

    def __init__(self, phone_number: str, db_executor: DatabaseExecutor):
        # 将类变量覆盖为实例变量，避免多会话并发串扰
        self.generated_selling_partner_id: Optional[str] = None
        self.cached_lender_repayment_id: Optional[str] = None
        self.hsbc_psp_pending_account_id_by_merchant: Dict[str, str] = {}
        self.hsbc_psp_completed_account_ids_in_session: set = set()
        super().__init__(phone_number, db_executor)

    # ======================== 辅助方法 ========================

    def _resolve_platform_seller_id(self, platform_seller_id: Optional[str] = None) -> Optional[str]:
        """解析 SP 状态更新所需 seller_id。

        优先级：
        1. 前端显式传入的 platform_seller_id
        2. 当前 session 中已生成的 selling_partner_id
        3. 根据当前 merchant_id 从 dpu_manual_offer 反查最新 platform_seller_id
        """
        if platform_seller_id and str(platform_seller_id).strip():
            return str(platform_seller_id).strip()

        if self.generated_selling_partner_id:
            return self.generated_selling_partner_id

        if not self.merchant_id:
            return None

        sql = (
            "SELECT platform_seller_id "
            "FROM dpu_seller_center.dpu_manual_offer "
            f"WHERE merchant_id = '{self.merchant_id}' "
            "AND platform_seller_id IS NOT NULL "
            "AND platform_seller_id != '' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        seller_id = self.db_executor.execute_sql(sql)
        if seller_id:
            self.generated_selling_partner_id = seller_id
            log.info(f"根据 merchant_id 自动查询到 platform_seller_id: {seller_id}")
        return seller_id

    def _do_post_webhook(self, data: dict, label: str) -> dict:
        """统一的 webhook POST 发送 + 日志 + 结果封装"""
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info(f"请求URL: {self.api_config.webhook_url}")
        log.info(f"请求方法: POST")
        log.info(f"请求Body（JSON）:")
        log.info(json.dumps(data, indent=2, ensure_ascii=False))
        log.info("=" * 60)

        try:
            response = http_requests.post(self.api_config.webhook_url, json=data, timeout=30)
            log.info(f"\n【{label}】完整响应信息")
            log.info("=" * 60)
            log.info(f"响应状态码: {response.status_code}")
            log.info(f"响应Body: {response.text}")
            log.info("=" * 60)

            success = response.status_code == 200
            if success:
                log.info(f"{label}成功")
            else:
                log.error(f"{label}失败 | 状态码={response.status_code}")
            return {"success": success, "status_code": response.status_code, "response": response.text}
        except http_requests.exceptions.RequestException as e:
            log.error(f"【{label}】请求异常: {e}")
            return {"success": False, "error": str(e)}

    def _do_post_custom(self, url: str, label: str, json_data: dict = None,
                        params: dict = None, headers: dict = None) -> dict:
        """统一的自定义 URL POST 发送"""
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info(f"请求URL: {url}")
        if json_data:
            log.info(f"请求Body: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
        if params:
            log.info(f"请求Params: {params}")
        log.info("=" * 60)

        try:
            kwargs = {"timeout": 30}
            if json_data:
                kwargs["json"] = json_data
            if params:
                kwargs["params"] = params
            if headers:
                kwargs["headers"] = headers
            response = http_requests.post(url, **kwargs)
            log.info(f"【{label}】响应状态码: {response.status_code}")
            log.info(f"【{label}】响应Body: {response.text}")
            success = response.status_code == 200
            return {"success": success, "status_code": response.status_code, "response": response.text}
        except http_requests.exceptions.RequestException as e:
            log.error(f"【{label}】请求异常: {e}")
            return {"success": False, "error": str(e)}

    # ======================== 1. SP-3PL 关联 ========================

    def mock_link_sp_3pl_shop(self) -> dict:
        """模拟关联 SP 和 3PL 店铺（无需用户输入）"""
        log.info("开始关联SP和3PL店铺...")
        result = self._do_post_custom(
            self.api_config.link_sap_3pl_url,
            "SP-3PL关联",
            params={"phone": self.phone_number}
        )
        if result.get("success"):
            try:
                resp_json = json.loads(result.get("response", "{}"))
                if resp_json.get("code") == 200:
                    log.info("SP-3PL关联成功")
                else:
                    log.error(f"SP-3PL关联失败: {resp_json}")
                    result["success"] = False
            except json.JSONDecodeError:
                pass
        return result

    # ======================== 2. 核保 ========================

    def mock_underwritten_status(self, amount: int = None, status: str = None) -> dict:
        """模拟核保状态更新"""
        if amount is None or status is None:
            # 兼容 CLI 模式，但 Web 模式下不会走到这里
            return super().mock_underwritten_status()

        underwritten_status = status
        data = self._build_common_webhook_data(
            "underwrittenLimit.completed",
            underwritten_status,
            {
                "dpuMerchantAccountId": [
                    {"MerchantAccountId": self.dpu_auth_token_seller_id}
                ] if self.dpu_auth_token_seller_id else [],
                "dpuLimitApplicationId": self.dpu_limit_application_id,
                "originalRequestId": "req_EFAL17621784619057169",
                "status": underwritten_status,
                "credit": {
                    "marginRate": "2.5",
                    "chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "creditLimit": {
                        "currency": self.preferred_currency,
                        "underwrittenAmount": {"currency": self.preferred_currency, "amount": amount}
                    }
                }
            }
        )
        result = self._do_post_webhook(data, "核保状态")
        result.update({"amount": amount, "status": underwritten_status})
        return result

    # ======================== 3. 审批 ========================

    def mock_approved_offer_status(self, amount: int = None, status: str = None,
                                    failure_reason_index: int = None) -> dict:
        """模拟审批状态更新"""
        if amount is None or status is None:
            return super().mock_approved_offer_status()

        approved_amount = round(float(amount), 2)
        approved_status = status

        # 处理退回原因
        failure_reason = None
        if approved_status == "RETURNED" and failure_reason_index is not None:
            reasons = list(ReturnedFailureReason)
            if 1 <= failure_reason_index <= len(reasons):
                failure_reason = reasons[failure_reason_index - 1].value

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
                            "chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float",
                            "baseRateType": "SOFR",
                            "baseRate": "0.05",
                            "marginRate": "0.02",
                            "fixedRate": "0.07"
                        },
                        "term": 120,
                        "termUnit": "Days",
                        "mintenor": 3,
                        "maxtenor": 24,
                        "offerEndDate": calculate_future_date(90),
                        "offerStartDate": get_current_time("%Y-%m-%d"),
                        "approvedLimit": {"currency": self.preferred_currency, "amount": approved_amount},
                        "warterMark": {"currency": self.preferred_currency, "amount": 0.00},
                        "signedLimit": {"currency": self.preferred_currency, "amount": 0.00},
                        "feeOrCharge": {
                            "type": "PROCESSING_FEE",
                            "feeOrChargeDate": "2023-10-16",
                            "netAmount": {"currency": self.preferred_currency, "amount": 0.00}
                        }
                    }
                }
            }
        }
        result = self._do_post_webhook(request_body, "审批状态")
        result.update({"amount": approved_amount, "status": approved_status})
        return result

    # ======================== 4/5. PSP 开始/完成 ========================

    def _mock_psp_status(self, is_start: bool = True, psp_status: str = None) -> dict:
        """模拟PSP状态更新（参数化版本）"""
        if psp_status is None:
            return super()._mock_psp_status(is_start)

        event_type = "psp.verification.started" if is_start else "psp.verification.completed"

        sp_auth_info = self._select_hsbc_psp_auth_token_info(for_completed=not is_start)
        if not sp_auth_info:
            return {"success": False, "error": "未查询到SP授权记录"}

        merchant_account_id = sp_auth_info["authorization_id"]
        credit_offer_id = self.credit_offer_lender_approved_offer_id
        if not credit_offer_id:
            msg = f"未查询到dpu_credit_offer.lender_approved_offer_id | merchant_id={self.merchant_id}"
            log.error(msg)
            return {"success": False, "error": msg}

        data = self._build_common_webhook_data(
            event_type, psp_status,
            {
                "applicationId": "EFA17590311621044381",
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": merchant_account_id,
                "lenderApprovedOfferId": credit_offer_id,
                "result": psp_status
            }
        )
        result = self._do_post_webhook(data, f"PSP{'开始' if is_start else '完成'}状态")

        if result.get("success"):
            if is_start:
                self.hsbc_psp_pending_account_id_by_merchant[self.merchant_id] = merchant_account_id
            else:
                self.hsbc_psp_completed_account_ids_in_session.add(merchant_account_id)
                self.hsbc_psp_pending_account_id_by_merchant.pop(self.merchant_id, None)

        result.update({"status": psp_status, "merchant_account_id": merchant_account_id})
        return result

    def mock_psp_start_status(self, status: str = None) -> dict:
        """模拟PSP开始状态"""
        return self._mock_psp_status(is_start=True, psp_status=status)

    def mock_psp_completed_status(self, status: str = None) -> dict:
        """模拟PSP完成状态"""
        return self._mock_psp_status(is_start=False, psp_status=status)

    # ======================== 6. 电子签 ========================

    def mock_esign_status(self, signed_amount: int = None, status: str = None) -> dict:
        """模拟电子签状态更新"""
        if signed_amount is None or status is None:
            return super().mock_esign_status()

        esign_status = status
        credit_offer_id = self.credit_offer_lender_approved_offer_id
        if not credit_offer_id:
            msg = (f"未查询到dpu_credit_offer.lender_approved_offer_id | "
                   f"merchant_id={self.merchant_id} | application_unique_id={self.application_unique_id}")
            log.error(msg)
            return {"success": False, "error": msg}

        data = self._build_common_webhook_data(
            "esign.completed", esign_status,
            {
                "lenderApprovedOfferId": credit_offer_id,
                "result": esign_status,
                "signedLimit": {"amount": round(float(signed_amount), 2), "currency": self.preferred_currency}
            }
        )
        result = self._do_post_webhook(data, "电子签状态")
        result.update({"signed_amount": signed_amount, "status": esign_status})
        return result

    # ======================== 7. 放款 ========================

    def mock_drawdown_status(self, amount: float = None, status: str = None,
                              failure_reason_index: int = None) -> dict:
        """模拟放款状态更新"""
        if amount is None or status is None:
            return super().mock_drawdown_status()

        drawdown_status = status
        failure_reason = None
        if drawdown_status == "REJECTED" and failure_reason_index is not None:
            reasons = list(DrawdownFailureReason)
            if 1 <= failure_reason_index <= len(reasons):
                failure_reason = reasons[failure_reason_index - 1].value[0]

        credit_offer_id = self.credit_offer_lender_approved_offer_id
        if not credit_offer_id:
            msg = (f"未查询到dpu_credit_offer.lender_approved_offer_id | "
                   f"merchant_id={self.merchant_id} | application_unique_id={self.application_unique_id}")
            log.error(msg)
            return {"success": False, "error": msg}

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
                    "lenderApprovedOfferId": credit_offer_id,
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
                        "loanAmount": {"currency": self.preferred_currency, "amount": f"{float(amount):.2f}"},
                        "rate": {"chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float", "baseRateType": "SOFR", "baseRate": "10.00",
                                 "marginRate": "0.00"},
                        "term": "90",
                        "termUnit": "Days",
                        "drawdownSuccessDate": current_date,
                        "actualDrawdownDate": current_date
                    },
                    "repayment": {
                        "expectedRepaymentDate": calculate_future_date(90),
                        "expectedRepaymentAmount": {"currency": self.preferred_currency, "amount": f"{float(amount):.2f}"},
                        "repaymentTerm": "90"
                    }
                }
            }
        }
        result = self._do_post_webhook(request_body, "放款状态")
        result.update({"amount": amount, "status": drawdown_status})
        return result

    # ======================== 8. 还款开始 ========================

    def mock_repayment_start_status(self, principal_amount: float = None,
                                     outstanding_amount: float = None) -> dict:
        """模拟还款开始状态通知"""
        if principal_amount is None or outstanding_amount is None:
            return super().mock_repayment_start_status()

        drawdown_info = self.get_drawdown_info()
        if not drawdown_info:
            return {"success": False, "error": "无放款记录，还款操作终止"}

        repayment_status = RepaymentStatus.START.value
        interest_amount = 88.00
        total_amount = round(principal_amount + interest_amount, 2)
        lender_repayment_id = self._get_or_create_lender_repayment_id()

        data = self._build_common_webhook_data(
            "repayment.status", repayment_status,
            {
                "merchantId": drawdown_info["merchant_id"],
                "dpuLoanId": drawdown_info["loan_id"],
                "lenderLoanId": drawdown_info["lender_loan_id"],
                "lenderRepaymentId": lender_repayment_id,
                "repayment": {
                    "status": repayment_status,
                    "failureReason": None,
                    "fundSource": "BankTransfer",
                    "paidOn": get_current_time(),
                    "totalPaidAmount": {"currency": self.preferred_currency, "amount": total_amount},
                    "principalPaidAmount": {"currency": self.preferred_currency, "amount": principal_amount},
                    "interestPaidAmount": {"currency": self.preferred_currency, "amount": interest_amount},
                    "feePaidAmount": {"currency": self.preferred_currency, "amount": 0.00},
                    "outstandingAmount": {"currency": self.preferred_currency, "amount": outstanding_amount}
                }
            }
        )
        result = self._do_post_webhook(data, "还款开始")
        result.update({"repayment_id": lender_repayment_id, "total_amount": total_amount})
        return result

    # ======================== 9. 还款 ========================

    def mock_repayment_status(self, principal_amount: float = None, outstanding_amount: float = None,
                               status: str = None, failure_reason_index: int = None) -> dict:
        """模拟还款状态通知"""
        if principal_amount is None or outstanding_amount is None or status is None:
            return super().mock_repayment_status()

        drawdown_info = self.get_drawdown_info()
        if not drawdown_info:
            return {"success": False, "error": "无放款记录，还款操作终止"}

        repayment_status = status
        failure_reason = None
        if repayment_status == "Failure" and failure_reason_index is not None:
            reason_map = {1: "ER001", 2: "ER002"}
            failure_reason = reason_map.get(failure_reason_index)

        interest_amount = 88.00
        total_amount = round(principal_amount + interest_amount, 2)
        lender_repayment_id = self._get_or_create_lender_repayment_id()

        data = self._build_common_webhook_data(
            "repayment.status", repayment_status,
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
                    "totalPaidAmount": {"currency": self.preferred_currency, "amount": total_amount},
                    "principalPaidAmount": {"currency": self.preferred_currency, "amount": principal_amount},
                    "interestPaidAmount": {"currency": self.preferred_currency, "amount": interest_amount},
                    "feePaidAmount": {"currency": self.preferred_currency, "amount": 0.00},
                    "outstandingAmount": {"currency": self.preferred_currency, "amount": outstanding_amount}
                }
            }
        )
        result = self._do_post_webhook(data, "还款")

        if result.get("success"):
            self.clear_lender_repayment_id()

        result.update({"repayment_id": lender_repayment_id, "status": repayment_status, "total_amount": total_amount})
        return result

    # ======================== 10. 多店铺 SP 绑定 ========================

    def mock_multi_shop_binding(self, state: str = None) -> dict:
        """SP 店铺绑定（多店铺第一步）"""
        if state is None:
            return super().mock_multi_shop_binding()

        self.generated_selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"
        params = {
            "state": state,
            "selling_partner_id": self.generated_selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }
        full_auth_url = f"{self.api_config.multi_shop_sp_auth_url}?{urlencode(params)}"

        log.info("=" * 60)
        log.info("【多店铺-SP绑定】")
        log.info("=" * 60)

        try:
            http_requests.get(self.api_config.multi_shop_sp_auth_url, params=params, timeout=30)
        except http_requests.exceptions.RequestException as e:
            log.warning(f"SP绑定请求异常（非致命）: {e}")

        log.info(f"【多店铺】SP绑定成功 | SP绑定ID：{self.generated_selling_partner_id}")
        log.info(f"【多店铺】SP授权URL：{full_auth_url}")

        return {
            "success": True,
            "selling_partner_id": self.generated_selling_partner_id,
            "auth_url": full_auth_url
        }

    # ======================== 11. SP 状态更新 ========================

    def mock_sp_status_update(self, platform_seller_id: str = None, status: str = None,
                               failure_reason_index: int = None) -> dict:
        """SP 状态更新"""
        if status is None:
            return super().mock_sp_status_update()

        # 优先使用传入值，其次使用 session 缓存，最后按 merchant_id 自动反查
        seller_id = self._resolve_platform_seller_id(platform_seller_id)
        if not seller_id:
            return {
                "success": False,
                "error": "未找到可用的 platform_seller_id。可手动输入，或先执行多店铺 SP 绑定。",
            }

        log.info(f"使用 platform_seller_id: {seller_id}")

        # 查询 idempotency_key 和 platform_offer_id
        idempotency_key = self.db_executor.execute_sql(
            f"SELECT idempotency_key FROM dpu_seller_center.dpu_manual_offer WHERE platform_seller_id = '{seller_id}'"
        )
        platform_offer_id = self.db_executor.execute_sql(
            f"SELECT platform_offer_id FROM dpu_seller_center.dpu_manual_offer "
            f"WHERE platform_seller_id = '{seller_id}' ORDER BY created_at DESC LIMIT 1"
        )

        if not idempotency_key:
            msg = f"未查询到 idempotency_key，platform_seller_id: {seller_id}"
            log.error(msg)
            return {"success": False, "error": msg}

        log.info(f"查询成功 | idempotency_key: {idempotency_key} | platform_offer_id: {platform_offer_id}")

        send_status = status
        failure_reason = ""
        if send_status == "FAIL" and failure_reason_index is not None:
            reason_map = {
                1: "Lender and seller country not align(User do have US shop）",
                2: "Active credit approval exists",
                3: "An offer already exists for the seller for the same partner product combination"
            }
            failure_reason = reason_map.get(failure_reason_index, "")

        if send_status == "SUCCESS" and not platform_offer_id:
            msg = f"SUCCESS 场景需要 platform_offer_id，platform_seller_id: {seller_id}"
            log.error(msg)
            return {"success": False, "error": msg}

        payload = {
            "idempotencyKey": idempotency_key,
            "sendStatus": send_status,
            "offerId": platform_offer_id if send_status == "SUCCESS" else "",
            "reason": failure_reason
        }

        result = self._do_post_custom(
            self.api_config.update_offer_url, "SP状态更新",
            json_data=payload, headers={"Content-Type": "application/json"}
        )
        result.update({"status": send_status, "platform_seller_id": seller_id})
        return result

    # ======================== 12. 3PL 重定向 ========================

    def mock_multi_shop_3pl_redirect(self) -> dict:
        """3PL 重定向（多店铺第二步）"""
        seller_id = self._resolve_platform_seller_id()
        if not seller_id:
            return {"success": False, "error": "未找到可用的 SP 绑定ID，请先执行SP店铺绑定或确认商户已有记录"}

        platform_offer_id = self.get_platform_offer_id(seller_id)
        if not platform_offer_id:
            msg = f"seller_id: {seller_id} 无对应platform_offer_id"
            log.error(msg)
            return {"success": False, "error": msg}

        full_redirect_url = f"{self.api_config.redirect_url}?offerId={platform_offer_id}"

        log.info("=" * 60)
        log.info("【多店铺-3PL重定向】")
        log.info("=" * 60)

        try:
            http_requests.get(self.api_config.redirect_url, params={"offerId": platform_offer_id}, timeout=30)
        except http_requests.exceptions.RequestException as e:
            log.warning(f"3PL重定向请求异常（非致命）: {e}")

        log.info(f"【多店铺】SP绑定ID：{seller_id}")
        log.info(f"【多店铺】platform_offer_id：{platform_offer_id}")
        log.info(f"【多店铺】3PL重定向URL：{full_redirect_url}")

        return {
            "success": True,
            "selling_partner_id": seller_id,
            "platform_offer_id": platform_offer_id,
            "redirect_url": full_redirect_url
        }

    # ======================== 13. 系统事件通知 ========================

    def mock_system_event_notification(self, event_type: str = None,
                                        application_unique_id: str = None,
                                        error_code: str = None) -> dict:
        """发送系统事件通知"""
        if event_type is None:
            return super().mock_system_event_notification()

        log.info(f"开始发送系统事件通知 | eventType={event_type}")

        # 获取 applicationUniqueId
        app_unique_id = application_unique_id or self.application_unique_id
        if not app_unique_id:
            return {"success": False, "error": "需要提供 application_unique_id"}

        # 查询 applicationId
        application_id = self.db_executor.execute_sql(
            f"SELECT fund_application_id FROM dpu_seller_center.dpu_lender_shop_data_transmission "
            f"WHERE application_unique_id = '{app_unique_id}' LIMIT 1"
        )
        if not application_id:
            log.warning("未找到 applicationId，使用默认值")
            application_id = "PLPUAT000000652489"

        # 查询 thirdPartyCustomerId
        third_party_customer_id = self.db_executor.execute_sql(
            f"SELECT merchant_id FROM dpu_seller_center.dpu_lender_shop_data_transmission "
            f"WHERE application_unique_id = '{app_unique_id}' LIMIT 1"
        )
        if not third_party_customer_id:
            log.warning("未找到 merchant_id，使用默认值")
            third_party_customer_id = "67379738b310487393c3947188e8a204"

        # 处理 errorCode
        actual_error_code = ""
        if event_type == "EXCEPTION-APPLICATION-CREATION":
            actual_error_code = error_code or "B-6003"

        payload = {
            "applicationUniqueId": app_unique_id,
            "eventType": event_type,
            "eventReceiver": "dpu",
            "eventData": {
                "thirdPartyCustomerId": third_party_customer_id,
                "applicationId": application_id,
                "eventTime": get_current_time(),
                "errorCode": actual_error_code,
                "errorMessage": ""
            }
        }

        headers = {
            "Authorization": "JWS eyJ2ZXIiOiIxLjAiLCJraWQiOiJCQzAwMDAxMTA2NyIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJCQzAwMDAxMTA2NyIsImF1ZCI6IkdCQS1FQ09NTSIsInBheWxvYWRfaGFzaF9hbGciOiJTSEEtMjU2IiwicGF5bG9hZF9oYXNoIjoiOWFkNjQyZmM4MGY1YmJkZTYwZDFhMmI1ZjJmMTJkNjY4OTJiZGQ4MGVlMzc4ODUzOTE4NTA2MmJkNjFjMzg5YyIsImlhdCI6MTc2OTA3NjQ4OCwianRpIjoiYjQ1OWJjMWYtZWNkZi00Mjc4LWIwMjMtNTQ2YzM4Y2ZmNWRhIn0.ULI-b7nl8E1n4JXjCR7jAOY1maoUlL5_kBex-FHITCfVa7VPRPPKRiU4RZhFlGVdRS1sJzGmlce4Gn0nidbWUISI7JzN-94N3GxMuMinVoLi6U_3SIH1a3Ykx4LdSACRL7DC2Jw1kcjKqgzaO-30TnR4iR1JtwcUPqcmSII8CxoYDFrrMh-Hqwq16fvj92VcgkMQB_TPu0ZezwBus01YLetiA4wCkCk-1Jq4K5E8EImHzDUISAiHyDovQo79t37bTX18ir0q1MvSqIgCDyMcb7-13REKXDjAE6AJKxprwE6RsrDULc0texMPra2j1PUdIfGGggsBjz0dlHDuaHXyCw",
            "X-HSBC-Request-Correlation-Id": "581772f3-8791-4466-98bf-bd5f13a6daff",
            "X-HSBC-E2E-Trust-Token": "5C2413B10CA3B23A",
            "X-HSBC-Request-Idempotency-Key": "8f5a23ce-a3d2-4b46-98f3-cac50b542abd",
            "X-HSBC-PROFILEID": "DPUSIT-B2B-P-2025-ACTIVE",
            "Accept": "*/*",
            "Funder-Resource": "HSBC",
            "Content-Type": "application/json"
        }

        url = f"{self.api_config.base_url}/dpu-openapi/notification/system-events"
        result = self._do_post_custom(url, "系统事件通知", json_data=payload, headers=headers)
        result.update({"event_type": event_type, "application_unique_id": app_unique_id})
        return result

    # ======================== 14. PSP 开始（HSBC） ========================

    def mock_psp_start_status_hsbc(self) -> dict:
        """发送HSBC版PSP开始通知"""
        log.info("开始处理PSP开始（HSBC）...")
        return self._send_hsbc_psp_notification_web(
            event_type="psp.verification.started",
            result="PROCESSING",
            failure_reason=None,
            title="PSP开始（HSBC）",
            for_completed=False
        )

    # ======================== 15. PSP 完成（HSBC） ========================

    def mock_psp_completed_status_hsbc(self, result: str = None) -> dict:
        """发送HSBC版PSP完成通知"""
        if result is None:
            return super().mock_psp_completed_status_hsbc()

        log.info("开始处理PSP完成（HSBC）...")
        failure_reason = None if result == "SUCCESS" else "Bank account verification failed"
        return self._send_hsbc_psp_notification_web(
            event_type="psp.verification.completed",
            result=result,
            failure_reason=failure_reason,
            title="PSP完成（HSBC）",
            for_completed=True
        )

    def _get_hsbc_psp_notification_context_web(self, for_completed: bool = False) -> Optional[Dict[str, str]]:
        """获取HSBC版PSP通知上下文（Web版，不调用 input）"""
        sp_auth_info = self._select_hsbc_psp_auth_token_info(for_completed=for_completed)
        if not sp_auth_info:
            return None

        limit_application_unique_id = self.dpu_limit_application_id
        if not limit_application_unique_id:
            log.warning("未查询到limitApplicationUniqueId，使用默认值")
            limit_application_unique_id = "DEFAULT_LIMIT_APP_ID"

        return {
            "merchant_id": sp_auth_info["merchant_id"],
            "merchant_account_id": sp_auth_info["authorization_id"],
            "limit_application_unique_id": limit_application_unique_id
        }

    def _send_hsbc_psp_notification_web(self, event_type: str, result: str,
                                         failure_reason: Optional[str], title: str,
                                         for_completed: bool = False) -> dict:
        """发送HSBC版PSP通知（Web版）"""
        context = self._get_hsbc_psp_notification_context_web(for_completed=for_completed)
        if not context:
            return {"success": False, "error": "无法获取HSBC PSP通知上下文"}

        payload = {
            "eventType": event_type,
            "eventReceiver": "DPU",
            "eventData": {
                "merchantId": context["merchant_id"],
                "merchantAccountId": context["merchant_account_id"],
                "limitApplicationUniqueId": context["limit_application_unique_id"],
                "pspName": "Payoneer",
                "pspId": "PSP_12345",
                "result": result,
                "failureReason": failure_reason,
                "lastUpdatedOn": get_current_time("%Y-%m-%dT%H:%M:%S"),
                "lastUpdatedBy": "HSBC_SYSTEM"
            }
        }

        host_header = self.api_config.base_url.replace("https://", "").replace("http://", "")
        headers = {
            "X-Internal-Request": "true",
            "Authorization": "Bearer",
            "Content-Type": "application/json",
            "Host": host_header,
        }
        url = f"{self.api_config.base_url}/dpu-openapi/notification/system-events"

        api_result = self._do_post_custom(url, title, json_data=payload, headers=headers)

        if api_result.get("success"):
            if for_completed:
                self.hsbc_psp_completed_account_ids_in_session.add(context["merchant_account_id"])
                self.hsbc_psp_pending_account_id_by_merchant.pop(self.merchant_id, None)
            else:
                self.hsbc_psp_pending_account_id_by_merchant[self.merchant_id] = context["merchant_account_id"]

        api_result.update({"result": result, "merchant_account_id": context["merchant_account_id"]})
        return api_result

    # ======================== 注册（静态方法改为实例无关的独立函数） ========================

    @staticmethod
    def register_new_account_web(env: str, journey: str = "500K",
                                  currency: str = "USD", offline: bool = False) -> dict:
        """注册新账号（Web 版，接受参数而非 input）"""
        if offline:
            journey = "500K"
            log.info(f"[线下模式] 开始注册新账号，流程: {journey}")
        else:
            log.info(f"开始注册新账号，流程: {journey}")

        log.info(f"融资产品货币: {currency}")

        # 生成账号信息
        phone_number = ''.join(filter(str.isdigit, faker.phone_number()))
        email = f"{phone_number}y@163doushabao.com"
        log.info(f"生成账号信息 | 手机号：{phone_number} | 邮箱：{email}")

        # 初始化 API 配置
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "reg": "https://dpu-gateway-reg.dowsure.com",
            "local": "http://192.168.11.3:8080"
        }
        base_url = base_url_dict[env]
        redirect_url_base = (
            f"{base_url}/dpu-merchant/amazon/redirect"
            if env in ("uat", "preprod")
            else f"https://dpu-gateway-{env}.dowsure.com/dpu-merchant/amazon/redirect"
        )
        api_config = ApiConfig(
            base_url=base_url,
            create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            redirect_url=redirect_url_base,
            register_url=f"{base_url}/dpu-user/auth/signup",
            login_url=f"{base_url}/en/login",
            spapi_auth_url=f"{base_url}/dpu-merchant/amz/sp/shop/auth",
            multi_shop_sp_auth_url=f"{base_url}/dpu-auth/amazon-sp/auth",
            link_sap_3pl_url=f"{base_url}/dpu-merchant/mock/link-sp-3pl-shops",
            create_psp_auth_url=f"{base_url}/dpu-openapi/test/create-psp-auth-token",
            webhook_url=f"{base_url}/dpu-openapi/webhook-notifications",
            update_offer_url=f"{base_url}/dpu-auth/amazon-sp/updateOffer",
            txt_path=str(SCRIPT_DIR / f"register_{env}.txt")
        )

        # 创建 offer_id
        offer_id = ""
        redirect_url = redirect_url_base
        if not offline:
            offer_id = DPUMockService._create_offer_id(journey, api_config)
            if not offer_id:
                return {"success": False, "error": "创建 offer_id 失败"}
            redirect_url = f"{redirect_url_base}?offerId={offer_id}"

        # 验证码验证
        validate_url = f"{base_url}/dpu-user/auth/validateSmsCode-sign"
        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": "FUNDPARK",
        }
        try:
            http_requests.post(validate_url, json={"areaCode": "+86", "code": "666666", "phone": phone_number},
                               headers=common_headers, timeout=30)
        except http_requests.exceptions.RequestException as e:
            log.error(f"验证码验证失败: {e}")

        # 注册
        register_payload = {
            "phone": phone_number, "areaCode": "+86", "code": "666666",
            "email": email, "offerId": offer_id,
            "password": "Aa11111111..", "confirmPassword": "Aa11111111..",
            "isAcceptMarketing": True,
            "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test",
            "preferFinanceProductCurrency": currency
        }

        try:
            if not offline:
                http_requests.get(redirect_url, timeout=30)

            resp = http_requests.post(api_config.register_url, json=register_payload,
                                      headers=common_headers, timeout=30)
            resp.raise_for_status()
            token = resp.json().get("data", {}).get("token", "")
            log.info(f"注册成功！手机号: {phone_number} | Token: {token}")

            with open(api_config.txt_path, 'a', encoding='utf-8') as f:
                line = f"\n{journey}\n{phone_number}\n{'线下' if offline else redirect_url}\n"
                f.write(line)

            return {
                "success": True,
                "phone_number": phone_number,
                "email": email,
                "offer_id": offer_id,
                "redirect_url": redirect_url if not offline else None,
            }
        except http_requests.exceptions.RequestException as e:
            log.error(f"注册失败: {e}")
            return {"success": False, "error": str(e), "phone_number": phone_number}
