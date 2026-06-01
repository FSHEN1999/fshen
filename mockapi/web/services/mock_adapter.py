# -*- coding: utf-8 -*-
"""Web 适配器：将 DPUMockService 的 input() 调用改为参数传入，返回结构化结果"""
import sys
import json
import random
import logging
import uuid
import time
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlencode

# 确保能导入项目根目录的 mock_sit 模块
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mock_sit import (
    DPUMockService, DatabaseExecutor, ApiConfig, DatabaseConfig,
    DPUStatus, RepaymentStatus, DrawdownFailureReason, ReturnedFailureReason,
    generate_uuid37, get_utc_time, get_current_time, calculate_future_date,
    validate_numeric_input, validate_phone_number, SCRIPT_DIR,
    fetch_sms_verification_code,
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

    @staticmethod
    def _sql_literal(value: Optional[str]) -> str:
        """Quote a small SQL literal for legacy execute_sql helpers."""
        if value is None:
            return "NULL"
        return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"

    @staticmethod
    def _lookup_user_token(db_executor: DatabaseExecutor, phone_number: str) -> str:
        """Fetch the latest user token when signup does not return one."""
        if not phone_number:
            return ""
        phone_literal = WebDPUMockService._sql_literal(phone_number)
        sql = (
            "SELECT token FROM dpu_users "
            f"WHERE phone_number = {phone_literal} "
            "AND token IS NOT NULL AND token != '' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        token = db_executor.execute_sql(sql)
        return str(token or "").strip()

    def _build_manual_offer_lookup_sql(
        self,
        selling_partner_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        ready_only: bool = True,
        limit: int = 1,
    ) -> Optional[str]:
        conditions = []
        if selling_partner_id:
            conditions.append(f"platform_seller_id = {self._sql_literal(selling_partner_id)}")
        if merchant_id:
            conditions.append(f"merchant_id = {self._sql_literal(merchant_id)}")
        if not conditions:
            return None

        ready_condition = (
            "AND idempotency_key IS NOT NULL AND idempotency_key != '' "
            "AND platform_offer_id IS NOT NULL AND platform_offer_id != '' "
            if ready_only
            else ""
        )
        return (
            "SELECT id, merchant_id, merchant_account_id, platform_seller_id, "
            "idempotency_key, platform_offer_id, send_status, created_at, updated_at "
            "FROM dpu_seller_center.dpu_manual_offer "
            f"WHERE ({' OR '.join(conditions)}) "
            f"{ready_condition}"
            "ORDER BY created_at DESC "
            f"LIMIT {int(limit)}"
        )

    def _get_manual_offer_debug_rows(
        self,
        selling_partner_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
    ) -> list[dict]:
        sql = self._build_manual_offer_lookup_sql(
            selling_partner_id=selling_partner_id,
            merchant_id=merchant_id,
            ready_only=False,
            limit=5,
        )
        if not sql:
            return []

        try:
            rows = self.db_executor.execute_query_all(sql)
        except AttributeError:
            first_row = self.db_executor.execute_query(sql)
            rows = [first_row] if first_row else []
        except Exception as exc:
            return [{"error": str(exc), "sql": sql}]

        if not rows:
            return []
        if isinstance(rows, dict):
            return [rows]
        return rows

    def _wait_for_manual_offer(
        self,
        selling_partner_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        timeout_seconds: int = 30,
        interval_seconds: int = 2,
    ) -> Optional[dict]:
        """Poll dpu_manual_offer until platform_offer_id and idempotency_key are available."""
        deadline = time.time() + timeout_seconds
        sql = self._build_manual_offer_lookup_sql(
            selling_partner_id=selling_partner_id,
            merchant_id=merchant_id,
            ready_only=True,
            limit=1,
        )
        if not sql:
            return None

        while time.time() < deadline:
            row = self.db_executor.execute_query(sql)
            if row and row.get("idempotency_key") and row.get("platform_offer_id"):
                resolved_seller_id = row.get("platform_seller_id")
                if resolved_seller_id:
                    self.generated_selling_partner_id = resolved_seller_id
                return row
            time.sleep(interval_seconds)
        return None

    def _ensure_sp_auth_active_from_manual_offer(self, seller_id: Optional[str] = None) -> dict:
        """Normalize SP auth rows so each seller ends with one canonical ACTIVE token."""
        resolved_seller_id = self._resolve_platform_seller_id(seller_id)
        manual_offer = self._wait_for_manual_offer(
            selling_partner_id=resolved_seller_id,
            merchant_id=self.merchant_id,
            timeout_seconds=1,
            interval_seconds=1,
        )
        if not manual_offer:
            return {
                "success": False,
                "error": "No ready dpu_manual_offer found for SP auth fallback",
                "seller_id": resolved_seller_id,
                "merchant_id": self.merchant_id,
            }

        seller_id = manual_offer.get("platform_seller_id") or resolved_seller_id
        merchant_account_id = manual_offer.get("merchant_account_id")
        if not seller_id or not merchant_account_id:
            return {
                "success": False,
                "error": "manual offer missing platform_seller_id or merchant_account_id",
                "manual_offer": manual_offer,
            }

        token_rows = self.db_executor.execute_query_all(
            "SELECT id, merchant_account_id, authorization_id, status, state, reason, "
            "scene_code, processing_stage, auth_start_time, auth_complete_time, created_at, updated_at "
            "FROM dpu_seller_center.dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            f"AND (authorization_id = {self._sql_literal(seller_id)} "
            "OR authorization_id IS NULL OR authorization_id = '') "
            "ORDER BY created_at DESC, id DESC"
        )
        if not token_rows:
            return {
                "success": False,
                "error": "No SP token rows found for normalization",
                "seller_id": seller_id,
                "merchant_account_id": merchant_account_id,
            }

        def _token_rank(row: dict) -> tuple:
            return (
                1 if row.get("authorization_id") == seller_id and row.get("status") == "ACTIVE" else 0,
                1 if row.get("scene_code") else 0,
                1 if row.get("auth_complete_time") else 0,
                1 if row.get("auth_start_time") else 0,
                row.get("updated_at") or row.get("created_at"),
                row.get("id"),
            )

        canonical_token = max(token_rows, key=_token_rank)
        canonical_id = canonical_token["id"]

        normalize_canonical_sql = (
            "UPDATE dpu_seller_center.dpu_auth_token "
            f"SET merchant_account_id = {self._sql_literal(merchant_account_id)}, "
            f"authorization_id = {self._sql_literal(seller_id)}, "
            "status = 'ACTIVE', "
            "reason = NULL, "
            "auth_complete_time = COALESCE(auth_complete_time, NOW()), "
            "updated_at = NOW() "
            f"WHERE id = {self._sql_literal(canonical_id)}"
        )
        self.db_executor.execute_sql(normalize_canonical_sql)

        suppress_duplicate_sql = (
            "UPDATE dpu_seller_center.dpu_auth_token "
            "SET status = 'REVOKED', "
            "reason = 'mockapi normalized duplicate SP token', "
            "updated_at = NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            f"AND id <> {self._sql_literal(canonical_id)} "
            f"AND (authorization_id = {self._sql_literal(seller_id)} "
            "OR authorization_id IS NULL OR authorization_id = '') "
            "AND status IN ('NEW', 'FAIL', 'PENDING', 'ACTIVE')"
        )
        self.db_executor.execute_sql(suppress_duplicate_sql)

        active_token = self.db_executor.execute_query(
            "SELECT id, state, status, authorization_id, merchant_account_id "
            "FROM dpu_seller_center.dpu_auth_token "
            f"WHERE id = {self._sql_literal(canonical_id)} "
            "LIMIT 1"
        )
        if not active_token:
            return {
                "success": False,
                "error": "SP token was not ACTIVE after fallback update",
                "seller_id": seller_id,
                "merchant_account_id": merchant_account_id,
            }

        inserted_shops = []
        for country_code in ("US", "CA"):
            exists_sql = (
                "SELECT id FROM dpu_seller_center.dpu_shops "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                "AND emarketplace = 'AMAZON' "
                "AND emarketplace_data_type = 'SP' "
                f"AND shop_reference_id = {self._sql_literal(seller_id)} "
                f"AND country_code = {self._sql_literal(country_code)} "
                "AND is_deleted = 0 "
                "LIMIT 1"
            )
            if self.db_executor.execute_sql(exists_sql):
                continue
            insert_shop_sql = (
                "INSERT INTO dpu_seller_center.dpu_shops ("
                "id, merchant_id, emarketplace, emarketplace_data_type, auth_id, "
                "shop_reference_id, merchant_account_id, shop_status, country_code, "
                "created_at, updated_at, create_by, update_by, is_deleted"
                ") VALUES ("
                "REPLACE(UUID(), '-', ''), "
                f"{self._sql_literal(self.merchant_id)}, "
                "'AMAZON', 'SP', "
                f"{self._sql_literal(canonical_id)}, "
                f"{self._sql_literal(seller_id)}, "
                f"{self._sql_literal(merchant_account_id)}, "
                "'ACTIVE', "
                f"{self._sql_literal(country_code)}, "
                "NOW(), NOW(), 'mockapi', 'mockapi', 0)"
            )
            self.db_executor.execute_sql(insert_shop_sql)
            inserted_shops.append(country_code)

        repoint_shop_sql = (
            "UPDATE dpu_seller_center.dpu_shops "
            f"SET auth_id = {self._sql_literal(canonical_id)}, "
            f"merchant_account_id = {self._sql_literal(merchant_account_id)}, "
            "updated_at = NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND emarketplace = 'AMAZON' "
            "AND emarketplace_data_type = 'SP' "
            f"AND shop_reference_id = {self._sql_literal(seller_id)} "
            "AND is_deleted = 0"
        )
        self.db_executor.execute_sql(repoint_shop_sql)

        latest_token = self.db_executor.execute_query(
            "SELECT id, state, status, authorization_id, merchant_account_id, reason, created_at, updated_at "
            "FROM dpu_seller_center.dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        shop_rows = self.db_executor.execute_query_all(
            "SELECT id, auth_id, shop_reference_id, merchant_account_id, shop_status, country_code "
            "FROM dpu_seller_center.dpu_shops "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND emarketplace = 'AMAZON' "
            "AND emarketplace_data_type = 'SP' "
            f"AND shop_reference_id = {self._sql_literal(seller_id)} "
            "AND is_deleted = 0 "
            "ORDER BY country_code"
        )
        return {
            "success": bool(active_token and active_token.get("status") == "ACTIVE"),
            "seller_id": seller_id,
            "merchant_account_id": merchant_account_id,
            "manual_offer": manual_offer,
            "canonical_token_id": canonical_id,
            "active_token": active_token,
            "latest_sp_token": latest_token,
            "inserted_shops": inserted_shops,
            "shops": shop_rows,
        }

    @staticmethod
    def _build_api_config(env: str) -> ApiConfig:
        base_url_dict = {
            "sit": "https://sit.api.expressfinance.business.hsbc.com",
            "dev": "https://dpu-gateway-dev.dowsure.com",
            "uat": "https://uat.api.expressfinance.business.hsbc.com",
            "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
            "reg": "https://dpu-gateway-reg.dowsure.com",
            "local": "http://192.168.11.3:8080",
        }
        base_url = base_url_dict[env]
        redirect_url_base = (
            f"{base_url}/dpu-merchant/amazon/redirect"
            if env in ("uat", "preprod")
            else f"https://dpu-gateway-{env}.dowsure.com/dpu-merchant/amazon/redirect"
        )
        return ApiConfig(
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
            txt_path=str(SCRIPT_DIR / f"register_{env}.txt"),
        )

    @staticmethod
    def _build_portal_base_url(env: str) -> str:
        portal_base_url_dict = {
            "sit": "https://expressfinance-dpu-sit.dowsure.com",
            "dev": "https://expressfinance-dpu-dev.dowsure.com",
            "uat": "https://expressfinance-uat.business.hsbc.com",
            "preprod": "https://expressfinance-preprod.business.hsbc.com",
            "reg": "https://expressfinance-dpu-reg.dowsure.com",
            "local": "http://localhost:5173",
        }
        return portal_base_url_dict[env]

    @staticmethod
    def _format_http_body_for_log(text: str, max_chars: int = 4000) -> str:
        """Pretty-print JSON response bodies and keep long payloads bounded for the UI log."""
        if text is None:
            return ""
        body = str(text)
        try:
            body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
        except (TypeError, json.JSONDecodeError):
            pass
        if len(body) > max_chars:
            return f"{body[:max_chars]}\n...<truncated {len(body) - max_chars} chars>"
        return body

    @staticmethod
    def _format_http_headers_for_log(headers: dict, max_chars: int = 2000) -> str:
        header_text = json.dumps(dict(headers or {}), indent=2, ensure_ascii=False)
        if len(header_text) > max_chars:
            return f"{header_text[:max_chars]}\n...<truncated {len(header_text) - max_chars} chars>"
        return header_text

    @staticmethod
    def _format_redirect_body_for_log(text: str, max_chars: int = 500) -> str:
        """Do not flood operation results with redirected HTML pages."""
        if text is None:
            return ""
        body = str(text)
        stripped = body.lstrip().lower()
        if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
            return f"<HTML response omitted; {len(body)} chars>"
        if len(body) > max_chars:
            return f"{body[:max_chars]}\n...<truncated {len(body) - max_chars} chars>"
        return body

    @staticmethod
    def _interpret_api_success(response: http_requests.Response) -> tuple[bool, Optional[dict], Optional[str]]:
        """Treat business-level error payloads as failures even when HTTP status is 200."""
        http_success = 200 <= response.status_code < 300
        try:
            payload = response.json()
        except ValueError:
            return http_success, None, None

        if not isinstance(payload, dict):
            return http_success, payload, None

        # Some auth bootstrap APIs return authStatus=UNAUTHORIZED together with an authorization URL.
        # That means the request succeeded and produced the next-step consent entrypoint.
        if (
            str(payload.get("code")) == "200"
            and isinstance(payload.get("data"), dict)
            and payload["data"].get("authorizationUrl")
        ):
            return http_success, payload, None

        business_success = True
        if "isSuccess" in payload:
            business_success = bool(payload.get("isSuccess"))
        elif "success" in payload:
            business_success = bool(payload.get("success"))
        elif "code" in payload:
            business_success = str(payload.get("code")) == "200"

        error_message = None
        if not business_success:
            error_message = str(
                payload.get("message")
                or payload.get("detail")
                or payload.get("title")
                or "Business response indicated failure"
            )
        return http_success and business_success, payload, error_message

    @staticmethod
    def _summarize_webhook_request(data: dict) -> str:
        details = (data or {}).get("data", {}).get("details", {})
        summary = {
            "eventType": (data or {}).get("data", {}).get("eventType"),
            "merchantId": details.get("merchantId"),
            "status": details.get("status") or details.get("result") or details.get("drawdownStatus"),
            "dpuLimitApplicationId": details.get("dpuLimitApplicationId"),
            "dpuApplicationId": details.get("dpuApplicationId"),
            "dpuMerchantAccountId": details.get("dpuMerchantAccountId"),
            "creditLimit": details.get("credit", {}).get("creditLimit") if isinstance(details.get("credit"), dict) else None,
        }
        return json.dumps({k: v for k, v in summary.items() if v is not None}, indent=2, ensure_ascii=False)

    def _do_post_webhook(self, data: dict, label: str) -> dict:
        """统一的 webhook POST 发送 + 日志 + 结果封装"""
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: POST")
        log.info(f"请求URL: {self.api_config.webhook_url}")
        log.info("请求Body（JSON）:")
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
                body_for_log = self._format_http_body_for_log(response.text)
                headers_for_log = self._format_http_headers_for_log(response.headers)
                request_summary = self._summarize_webhook_request(data)
                log.error(
                    f"{label}失败 | 状态码={response.status_code}\n"
                    f"请求URL: {self.api_config.webhook_url}\n"
                    f"请求摘要:\n{request_summary}\n"
                    f"响应Headers:\n{headers_for_log}\n"
                    f"响应Body:\n{body_for_log}"
                )
            return {
                "success": success,
                "status_code": response.status_code,
                "response": response.text,
                "response_body": self._format_http_body_for_log(response.text),
            }
        except http_requests.exceptions.RequestException as e:
            detail = [f"【{label}】请求异常: {type(e).__name__}: {e}", f"请求URL: {self.api_config.webhook_url}"]
            if getattr(e, "response", None) is not None:
                detail.extend([
                    f"响应状态码: {e.response.status_code}",
                    f"响应Headers:\n{self._format_http_headers_for_log(e.response.headers)}",
                    f"响应Body:\n{self._format_http_body_for_log(e.response.text)}",
                ])
            log.error("\n".join(detail))
            return {"success": False, "error": str(e)}

    def _do_post_custom(self, url: str, label: str, json_data: dict = None,
                        params: dict = None, headers: dict = None) -> dict:
        """统一的自定义 URL POST 发送"""
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: POST")
        log.info(f"请求URL: {url}")
        if json_data:
            log.info(f"请求Body（JSON）: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
        if params:
            log.info(f"请求Params: {params}")
        if headers:
            log.info(f"请求Headers: {json.dumps(headers, ensure_ascii=False)}")
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
            success, response_payload, business_error = self._interpret_api_success(response)
            response_body = self._format_http_body_for_log(response.text)
            log.info(f"【{label}】响应状态码: {response.status_code}")
            log.info(f"【{label}】响应Body: {response_body}")
            if not success:
                error_suffix = f"\n业务错误: {business_error}" if business_error else ""
                log.error(
                    f"{label}失败 | 状态码={response.status_code}\n"
                    f"请求URL: {url}\n"
                    f"响应Payload:\n{json.dumps(response_payload, indent=2, ensure_ascii=False) if isinstance(response_payload, dict) else response_body}\n"
                    f"响应Headers:\n{self._format_http_headers_for_log(response.headers)}\n"
                    f"响应Body:\n{response_body}"
                    f"{error_suffix}"
                )
            return {
                "success": success,
                "status_code": response.status_code,
                "response": response.text,
                "response_body": response_body,
                "response_json": response_payload if isinstance(response_payload, dict) else None,
                "error_message": business_error,
            }
        except http_requests.exceptions.RequestException as e:
            detail = [f"【{label}】请求异常: {type(e).__name__}: {e}", f"请求URL: {url}"]
            if getattr(e, "response", None) is not None:
                detail.extend([
                    f"响应状态码: {e.response.status_code}",
                    f"响应Headers:\n{self._format_http_headers_for_log(e.response.headers)}",
                    f"响应Body:\n{self._format_http_body_for_log(e.response.text)}",
                ])
            log.error("\n".join(detail))
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

    def get_dowsure_merchant_accounts(self) -> dict:
        """Return SP merchant accounts that can be used by the DOWSURE underwritten webhook."""
        accounts = self._get_sp_merchant_accounts_for_dowsure()
        return {
            "success": True,
            "merchant_id": self.merchant_id,
            "accounts": accounts,
            "count": len(accounts),
        }

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

    def mock_underwritten_status_dowsure(
        self,
        amount: int = None,
        status: str = None,
        merchant_accounts: Optional[list[dict]] = None,
    ) -> dict:
        """Send the DOWSURE underwritten webhook without interactive input."""
        if status is None:
            return super().mock_underwritten_status_dowsure()

        if status not in {"APPROVED", "REJECTED"}:
            return {"success": False, "error": f"Unsupported DOWSURE underwritten status: {status}"}

        if not merchant_accounts:
            merchant_accounts = [
                {
                    "merchantAccountId": item["merchantAccountId"],
                    "merchantAccountLimit": item.get("merchantAccountLimit"),
                }
                for item in self._get_sp_merchant_accounts_for_dowsure()
            ]

        clean_accounts = []
        for item in merchant_accounts:
            merchant_account_id = str(item.get("merchantAccountId") or "").strip()
            if not merchant_account_id:
                continue
            merchant_account_limit = item.get("merchantAccountLimit")
            clean_accounts.append({
                "merchantAccountId": merchant_account_id,
                "merchantAccountLimit": None if merchant_account_limit is None else float(merchant_account_limit),
            })

        if not clean_accounts:
            return {"success": False, "error": "No SP merchant accounts found for DOWSURE underwritten webhook"}

        total_underwritten_amount = sum(
            item["merchantAccountLimit"]
            for item in clean_accounts
            if item["merchantAccountLimit"] is not None
        )
        underwritten_amount = total_underwritten_amount if amount is None else float(amount)
        underwritten_status = status
        data = self._build_common_webhook_data(
            "underwrittenLimit.completed",
            underwritten_status,
            {
                "dpuMerchantAccountId": clean_accounts,
                "dpuLimitApplicationId": self.dpu_limit_application_id,
                "originalRequestId": "req_50111101",
                "status": underwritten_status,
                "failureReason": None,
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
                        "currency": self.preferred_currency,
                        "underwrittenAmount": {
                            "currency": self.preferred_currency,
                            "amount": f"{underwritten_amount:.2f}",
                        },
                        "availableLimit": {"currency": self.preferred_currency, "amount": "0.00"},
                        "signedLimit": {"currency": self.preferred_currency, "amount": "0.00"},
                        "watermark": {"currency": self.preferred_currency, "amount": "0.00"},
                    },
                },
            },
        )
        result = self._do_post_webhook(data, "DOWSURE核保状态")
        result.update({
            "amount": underwritten_amount,
            "total_merchant_account_limit": total_underwritten_amount,
            "status": underwritten_status,
            "merchant_accounts": clean_accounts,
        })
        return result

    def mock_approved_offer_status(self, amount: int = None, status: str = None,
                                    failure_reason_index: int = None,
                                    rejection_reason: str = None) -> dict:
        """模拟审批状态更新"""
        if amount is None or status is None:
            return super().mock_approved_offer_status()

        approved_amount = round(float(amount), 2)
        approved_status = status

        # Keep Web API behavior aligned with the current mock_sit approval flow.
        failure_reason = None
        if approved_status == "RETURNED" and failure_reason_index is not None:
            reasons = list(ReturnedFailureReason)
            if 1 <= failure_reason_index <= len(reasons):
                failure_reason = reasons[failure_reason_index - 1].value
        elif approved_status == "REJECTED":
            failure_reason = rejection_reason if rejection_reason in {"fraud", "others"} else "others"

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
        result.update({"amount": approved_amount, "status": approved_status, "failure_reason": failure_reason})
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

        generated_selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"
        auth_token = ""
        params = {
            "state": state,
            "selling_partner_id": generated_selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }
        full_auth_url = f"{self.api_config.multi_shop_sp_auth_url}?{urlencode(params)}"

        log.info("=" * 60)
        log.info("【多店铺-SP绑定】")
        log.info("=" * 60)

        try:
            response = http_requests.get(
                self.api_config.multi_shop_sp_auth_url,
                params=params,
                headers={
                    "Authorization": f"Bearer {(auth_token or '').strip()}",
                    "content-type": "application/json",
                    "finance-product": "LINE_OF_CREDIT",
                    "funder-resource": "FUNDPARK",
                    "product-currency": self.preferred_currency or "USD",
                },
                timeout=30,
            )
            response_body = self._format_redirect_body_for_log(response.text)
            log.info(f"请求URL: {full_auth_url}")
            log.info(f"响应状态码: {response.status_code}")
            log.info(f"响应Body: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            self.generated_selling_partner_id = None
            error_detail = f"SP绑定失败: {type(e).__name__}: {e}\n  - 请求URL: {full_auth_url}"
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                error_detail += f"\n  - 响应Body: {error_response_body}"
            log.error(error_detail)
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": None,
                "auth_url": full_auth_url,
                "auth_token_source": "dpu_users.token",
                "response_body": error_response_body,
                "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
            }

        self.generated_selling_partner_id = generated_selling_partner_id
        log.info(f"【多店铺】SP绑定成功 | SP绑定ID：{self.generated_selling_partner_id}")
        log.info(f"【多店铺】SP授权URL：{full_auth_url}")

        return {
            "success": True,
            "selling_partner_id": self.generated_selling_partner_id,
            "auth_url": full_auth_url,
            "auth_token_source": "dpu_users.token",
            "status_code": response.status_code,
            "response_body": response_body,
        }


    # ======================== 11. SP 状态更新 ========================

    @staticmethod
    def register_and_run_multishop_flow_web(
        env: str,
        journey: str = "500K",
        currency: str = "USD",
        offline: bool = False,
        funder_resource: str = "FUNDPARK",
        sp_status: str = "SUCCESS",
    ) -> dict:
        """Register a new account and run the multi-shop flow via amazon-sp/auth plus DB verification."""
        register_result = WebDPUMockService.register_new_account_web(
            env=env,
            journey=journey,
            currency=currency,
            offline=offline,
            funder_resource=funder_resource,
        )
        if not register_result.get("success"):
            return {
                "success": False,
                "stage": "register",
                "error": register_result.get("error", "Register failed"),
                "register_result": register_result,
            }

        session_ctx = None
        steps = []
        try:
            try:
                from web.services.session_manager import session_manager
            except ModuleNotFoundError:
                from mockapi.web.services.session_manager import session_manager

            session_ctx = session_manager.create_session(env, register_result["phone_number"])
            service = session_ctx.service

            state = service.db_executor.execute_sql("SELECT UUID() AS state")
            if not state:
                state = str(uuid.uuid4())

            auth_token = (register_result.get("token") or "").strip()
            auth_token_source = "signup_response.token"
            if not auth_token:
                auth_token = WebDPUMockService._lookup_user_token(
                    service.db_executor,
                    register_result.get("phone_number", ""),
                )
                auth_token_source = "dpu_users.token"
            if not auth_token:
                return {
                    "success": False,
                    "stage": "auth_token",
                    "error": "Signup did not return token and no token was found in dpu_users",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": "missing",
                    "steps": steps,
                }

            generated_selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"
            service.generated_selling_partner_id = generated_selling_partner_id

            sp_auth_url = f"{service.api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-auth-url"
            sp_auth_payload = {
                "state": state,
                "sceneCode": "SHOP_BIND" if offline else "SHOP_BIND_NO_OFFER",
                "sourceCode": funder_resource,
                "redirectUrl": f"{WebDPUMockService._build_portal_base_url(env)}/redirect-loading?state={state}",
            }
            try:
                sp_auth_response = http_requests.post(
                    sp_auth_url,
                    json=sp_auth_payload,
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "content-type": "application/json",
                        "finance-product": "LINE_OF_CREDIT",
                        "funder-resource": funder_resource,
                        "product-currency": currency,
                        "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                        "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
                    },
                    timeout=30,
                )
                sp_auth_response_body = service._format_redirect_body_for_log(sp_auth_response.text)
                sp_auth_success, sp_auth_payload_result, sp_auth_error = service._interpret_api_success(sp_auth_response)
                sp_auth_response.raise_for_status()
                if not sp_auth_success:
                    raise RuntimeError(sp_auth_error or "sp-auth-url business failed")
            except http_requests.exceptions.RequestException as exc:
                return {
                    "success": False,
                    "stage": "sp_auth_url",
                    "error": str(exc),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps + [{
                        "step": "SP auth-url",
                        "endpoint": sp_auth_url,
                        "payload": sp_auth_payload,
                        "result": {
                            "success": False,
                            "status_code": exc.response.status_code if getattr(exc, "response", None) is not None else None,
                            "response_body": None if getattr(exc, "response", None) is None else service._format_redirect_body_for_log(exc.response.text),
                            "auth_token_source": auth_token_source,
                        },
                    }],
                }
            except Exception as exc:
                return {
                    "success": False,
                    "stage": "sp_auth_url",
                    "error": str(exc),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps + [{
                        "step": "SP auth-url",
                        "endpoint": sp_auth_url,
                        "payload": sp_auth_payload,
                        "result": {
                            "success": False,
                            "status_code": sp_auth_response.status_code,
                            "response_body": sp_auth_response_body,
                            "response_json": sp_auth_payload_result if isinstance(sp_auth_payload_result, dict) else None,
                            "auth_token_source": auth_token_source,
                        },
                    }],
                }

            steps.append({
                "step": "SP auth-url",
                "endpoint": sp_auth_url,
                "payload": sp_auth_payload,
                "result": {
                    "success": True,
                    "status_code": sp_auth_response.status_code,
                    "response_body": sp_auth_response_body,
                    "response_json": sp_auth_payload_result if isinstance(sp_auth_payload_result, dict) else None,
                    "selling_partner_id": generated_selling_partner_id,
                    "auth_token_source": auth_token_source,
                },
            })

            sp_auth_result_url = f"{service.api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-shop-auth-result?state={state}"
            try:
                sp_auth_result_response = http_requests.get(
                    sp_auth_result_url,
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "finance-product": "LINE_OF_CREDIT",
                        "product-currency": currency,
                        "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                        "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
                    },
                    timeout=30,
                )
                sp_auth_result_body = service._format_redirect_body_for_log(sp_auth_result_response.text)
                sp_auth_result_success, sp_auth_result_payload, sp_auth_result_error = service._interpret_api_success(sp_auth_result_response)
                sp_auth_result_response.raise_for_status()
                if not sp_auth_result_success:
                    raise RuntimeError(sp_auth_result_error or "sp-shop-auth-result business failed")
            except http_requests.exceptions.RequestException as exc:
                return {
                    "success": False,
                    "stage": "sp_shop_auth_result",
                    "error": str(exc),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps + [{
                        "step": "SP auth-result",
                        "endpoint": sp_auth_result_url,
                        "payload": {"state": state},
                        "result": {
                            "success": False,
                            "status_code": exc.response.status_code if getattr(exc, "response", None) is not None else None,
                            "response_body": None if getattr(exc, "response", None) is None else service._format_redirect_body_for_log(exc.response.text),
                            "auth_token_source": auth_token_source,
                        },
                    }],
                }
            except Exception as exc:
                return {
                    "success": False,
                    "stage": "sp_shop_auth_result",
                    "error": str(exc),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps + [{
                        "step": "SP auth-result",
                        "endpoint": sp_auth_result_url,
                        "payload": {"state": state},
                        "result": {
                            "success": False,
                            "status_code": sp_auth_result_response.status_code,
                            "response_body": sp_auth_result_body,
                            "response_json": sp_auth_result_payload if isinstance(sp_auth_result_payload, dict) else None,
                            "auth_token_source": auth_token_source,
                        },
                    }],
                }

            steps.append({
                "step": "SP auth-result",
                "endpoint": sp_auth_result_url,
                "payload": {"state": state},
                "result": {
                    "success": True,
                    "status_code": sp_auth_result_response.status_code,
                    "response_body": sp_auth_result_body,
                    "response_json": sp_auth_result_payload if isinstance(sp_auth_result_payload, dict) else None,
                    "auth_token_source": auth_token_source,
                },
            })

            db_state_sql = (
                "SELECT state FROM dpu_auth_token "
                f"WHERE merchant_id = '{session_ctx.merchant_id}' "
                "AND authorization_party = 'SP' "
                f"AND state = '{state}' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            db_state = None
            for _ in range(15):
                db_state = service.db_executor.execute_sql(db_state_sql)
                if db_state:
                    break
                time.sleep(1)
            if not db_state:
                return {
                    "success": False,
                    "stage": "wait_sp_state",
                    "error": "Timeout waiting dpu_auth_token.state after sp-auth-url",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps,
                }

            auth_params = {
                "mws_auth_token": "1235",
                "selling_partner_id": generated_selling_partner_id,
                "spapi_oauth_code": "123123",
                "state": db_state,
            }
            auth_get_url = f"{service.api_config.multi_shop_sp_auth_url}?{urlencode(auth_params)}"
            try:
                auth_get_response = http_requests.get(
                    service.api_config.multi_shop_sp_auth_url,
                    params=auth_params,
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "content-type": "application/json",
                        "finance-product": "LINE_OF_CREDIT",
                        "funder-resource": funder_resource,
                        "product-currency": currency,
                    },
                    timeout=30,
                )
                auth_get_body = service._format_redirect_body_for_log(auth_get_response.text)
                auth_get_response.raise_for_status()
            except http_requests.exceptions.RequestException as exc:
                return {
                    "success": False,
                    "stage": "amazon_sp_auth",
                    "error": str(exc),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": db_state,
                    "steps": steps + [{
                        "step": "SP auth",
                        "endpoint": service.api_config.multi_shop_sp_auth_url,
                        "payload": auth_params,
                        "result": {
                            "success": False,
                            "status_code": exc.response.status_code if getattr(exc, "response", None) is not None else None,
                            "response_body": None if getattr(exc, "response", None) is None else service._format_redirect_body_for_log(exc.response.text),
                            "auth_url": auth_get_url,
                            "auth_token_source": auth_token_source,
                        },
                    }],
                }

            steps.append({
                "step": "SP auth",
                "endpoint": service.api_config.multi_shop_sp_auth_url,
                "payload": auth_params,
                "result": {
                    "success": True,
                    "status_code": auth_get_response.status_code,
                    "response_body": auth_get_body,
                    "selling_partner_id": generated_selling_partner_id,
                    "auth_url": auth_get_url,
                    "auth_token_source": auth_token_source,
                },
            })

            if not offline:
                return {
                    "success": True,
                    "stage": "completed",
                    "summary": "Registered, created session, generated state, and completed Amazon SP auth callback. Online registration already carries 3P, so the flow stops here.",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps,
                }

            manual_offer_row = service._wait_for_manual_offer(
                selling_partner_id=generated_selling_partner_id,
                merchant_id=session_ctx.merchant_id,
                timeout_seconds=120 if offline else 30,
            )
            if not manual_offer_row and not offline:
                link_result = service._do_post_custom(
                    service.api_config.link_sap_3pl_url,
                    "SP-3PL关联补偿",
                    params={"phone": session_ctx.phone_number},
                )
                steps.append({
                    "step": "SP-3PL fallback link",
                    "endpoint": service.api_config.link_sap_3pl_url,
                    "payload": {"phone": session_ctx.phone_number},
                    "result": link_result,
                })
                manual_offer_row = service._wait_for_manual_offer(
                    selling_partner_id=generated_selling_partner_id,
                    merchant_id=session_ctx.merchant_id,
                    timeout_seconds=20,
                )
            if not manual_offer_row:
                manual_offer_debug_rows = service._get_manual_offer_debug_rows(
                    selling_partner_id=generated_selling_partner_id,
                    merchant_id=session_ctx.merchant_id,
                )
                return {
                    "success": False,
                    "stage": "wait_manual_offer",
                    "error": (
                        "Timeout waiting ready dpu_manual_offer after amazon-sp/auth. "
                        "Expected the backend to auto-generate platform_offer_id."
                    ),
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": db_state,
                    "manual_offer_debug_rows": manual_offer_debug_rows,
                    "steps": steps,
                }

            ready_selling_partner_id = manual_offer_row.get("platform_seller_id") or generated_selling_partner_id
            service.generated_selling_partner_id = ready_selling_partner_id
            steps.append({
                "step": "manual offer ready",
                "endpoint": "dpu_manual_offer",
                "payload": {
                    "selling_partner_id": generated_selling_partner_id,
                    "merchant_id": session_ctx.merchant_id,
                },
                "result": {
                    "success": True,
                    "requested_selling_partner_id": generated_selling_partner_id,
                    "selling_partner_id": ready_selling_partner_id,
                    "merchant_id": manual_offer_row.get("merchant_id"),
                    "platform_offer_id": manual_offer_row.get("platform_offer_id"),
                    "idempotency_key": manual_offer_row.get("idempotency_key"),
                    "auth_token_source": auth_token_source,
                },
            })

            sp_update_result = service.mock_sp_status_update(
                platform_seller_id=ready_selling_partner_id,
                status=sp_status,
            )
            steps.append({
                "step": "SP status update",
                "endpoint": "/api/mock/sp-status-update",
                "payload": {
                    "session_id": session_ctx.session_id,
                    "platform_seller_id": ready_selling_partner_id,
                    "status": sp_status,
                },
                "result": sp_update_result,
            })
            if not sp_update_result.get("success"):
                return {
                    "success": False,
                    "stage": "sp_status_update",
                    "register_result": register_result,
                    "session": {
                        "session_id": session_ctx.session_id,
                        "env": session_ctx.env,
                        "phone_number": session_ctx.phone_number,
                        "merchant_id": session_ctx.merchant_id,
                    },
                    "auth_token_source": auth_token_source,
                    "state": state,
                    "steps": steps,
                }

            redirect_result = service.mock_multi_shop_3pl_redirect()
            steps.append({
                "step": "3PL redirect",
                "endpoint": "/api/mock/multi-shop-3pl-redirect",
                "payload": {"session_id": session_ctx.session_id},
                "result": redirect_result,
            })

            return {
                "success": redirect_result.get("success", False),
                "stage": "completed" if redirect_result.get("success") else "multi_shop_3pl_redirect",
                "summary": "Registered, created session, generated state, ran SP auth, verified manual offer, updated SP status, and called 3PL redirect.",
                "register_result": register_result,
                "session": {
                    "session_id": session_ctx.session_id,
                    "env": session_ctx.env,
                    "phone_number": session_ctx.phone_number,
                    "merchant_id": session_ctx.merchant_id,
                },
                "auth_token_source": auth_token_source,
                "state": state,
                "steps": steps,
            }
        except Exception as exc:
            return {
                "success": False,
                "stage": "unexpected_exception",
                "error": str(exc),
                "register_result": register_result,
                "session": None if session_ctx is None else {
                    "session_id": session_ctx.session_id,
                    "env": session_ctx.env,
                    "phone_number": session_ctx.phone_number,
                    "merchant_id": session_ctx.merchant_id,
                },
                "auth_token_source": None if session_ctx is None else "signup_response.token",
                "steps": steps,
            }

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
                1: "the seller location does not match the lender location",
                2: "Active credit approval exists",
                3: "offer already exists",
                4: "others"
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
        if result.get("success") and send_status == "SUCCESS":
            result["sp_auth_fallback"] = self._ensure_sp_auth_active_from_manual_offer(seller_id)
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
            response = http_requests.get(self.api_config.redirect_url, params={"offerId": platform_offer_id}, timeout=30)
            response_body = self._format_redirect_body_for_log(response.text)
            log.info(f"请求URL: {full_redirect_url}")
            log.info(f"响应状态码: {response.status_code}")
            log.info(f"响应Body: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_detail = f"3PL重定向失败: {type(e).__name__}: {e}\n  - 请求URL: {full_redirect_url}"
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
                error_detail += f"\n  - 状态码: {e.response.status_code}"
                error_detail += f"\n  - 响应Body: {error_response_body}"
            log.error(error_detail)
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": seller_id,
                "platform_offer_id": platform_offer_id,
                "redirect_url": full_redirect_url,
                "response_body": error_response_body,
                "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
            }

        log.info(f"【多店铺】SP绑定ID：{seller_id}")
        log.info(f"【多店铺】platform_offer_id：{platform_offer_id}")
        log.info(f"【多店铺】3PL重定向URL：{full_redirect_url}")

        post_payload = {
            "authToken": "mock",
            "expireOn": "null",
            "keyId": "null",
            "offerId": platform_offer_id,
            "relayPage": 1,
            "returnUrl": "null",
            "signature": "null",
        }
        try:
            post_response = http_requests.post(
                self.api_config.redirect_url,
                json=post_payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            post_response_body = self._format_redirect_body_for_log(post_response.text)
            log.info(f"3PL POST URL: {self.api_config.redirect_url}")
            log.info(f"3PL POST Body: {json.dumps(post_payload, ensure_ascii=False)}")
            log.info(f"3PL POST status: {post_response.status_code}")
            log.info(f"3PL POST response: {post_response_body}")
            post_response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
            log.error(f"3PL POST failed: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": seller_id,
                "platform_offer_id": platform_offer_id,
                "redirect_url": full_redirect_url,
                "redirect_get": {
                    "status_code": response.status_code,
                    "response_body": response_body,
                },
                "redirect_post": {
                    "payload": post_payload,
                    "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
                    "response_body": error_response_body,
                },
            }

        return {
            "success": True,
            "selling_partner_id": seller_id,
            "platform_offer_id": platform_offer_id,
            "redirect_url": full_redirect_url,
            "status_code": response.status_code,
            "response_body": response_body,
            "redirect_get": {
                "status_code": response.status_code,
                "response_body": response_body,
            },
            "redirect_post": {
                "payload": post_payload,
                "status_code": post_response.status_code,
                "response_body": post_response_body,
            },
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

    # ======================== 16. Abandon(application.status) ========================

    def mock_application_abandon_status(self, abandon_reason: str = None) -> dict:
        """Send application.status Abandoned notification without interactive input."""
        if abandon_reason is None:
            return super().mock_application_abandon_status()

        valid_reasons = {
            "SellerCancelled",
            "OfferExpired",
            "ApplicationInfoNotSubmitted",
            "LenderOfferNotReturned",
        }
        if abandon_reason not in valid_reasons:
            return {"success": False, "error": f"不支持的 abandon_reason: {abandon_reason}"}

        dpu_application_id = self.credit_offer_application_unique_id or self.application_unique_id
        if not self.merchant_id:
            return {"success": False, "error": "未获取到 merchant_id，无法发送 abandon 通知"}
        if not dpu_application_id:
            return {"success": False, "error": "未获取到 dpuApplicationId，无法发送 abandon 通知"}

        request_body = {
            "data": {
                "eventType": "application.status",
                "eventId": generate_uuid37(),
                "eventMessage": "Application approval process completed successfully",
                "enquiryUrl": "https://api.lender.com/enquiry/12345",
                "datetime": get_current_time("%Y-%m-%dT%H:%M:%S"),
                "details": {
                    "merchantId": self.merchant_id,
                    "dpuApplicationId": dpu_application_id,
                    "status": "Abandoned",
                    "abandonReason": abandon_reason,
                    "lastUpdatedOn": get_current_time(),
                    "lastUpdatedBy": "system"
                }
            }
        }

        result = self._do_post_webhook(request_body, "Abandon状态")
        result.update({"dpu_application_id": dpu_application_id, "abandon_reason": abandon_reason})
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
                                  currency: str = "USD", offline: bool = False,
                                  funder_resource: str = "FUNDPARK") -> dict:
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
            offer_id = DPUMockService._create_offer_id(journey, currency, api_config)
            if not offer_id:
                return {"success": False, "error": "创建 offer_id 失败"}
            redirect_url = f"{redirect_url_base}?offerId={offer_id}"

        common_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36",
        }

        # 先触发短信验证码落库，再从 dpu_sms_record 读取真实验证码。
        verification_url = f"{base_url}/dpu-user/auth/verification-codes"
        verification_payload = {"areaCode": "+86", "code": "SIGNUP_VERIFICATION", "phone": phone_number}
        try:
            verify_resp = http_requests.post(
                verification_url,
                json=verification_payload,
                headers=common_headers,
                timeout=30,
            )
            log.info(
                f"验证码触发请求完成 | status={verify_resp.status_code} | phone={phone_number} | body={verify_resp.text}"
            )
            verify_resp.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            log.error(f"验证码触发失败: {e}")
            return {"success": False, "error": f"验证码触发失败: {e}"}

        try:
            with DatabaseExecutor(env=env) as sms_db_executor:
                verification_code = fetch_sms_verification_code(sms_db_executor, phone_number)
        except Exception as e:
            log.error(f"从 dpu_sms_record 获取验证码失败: {e}")
            return {"success": False, "error": f"从 dpu_sms_record 获取验证码失败: {e}"}

        validate_url = f"{base_url}/dpu-user/auth/validateSmsCode-sign"
        validate_payload = {
            "phoneNumber": phone_number,
            "phone": phone_number,
            "areaCode": "+86",
            "code": verification_code,
            "verificationCode": verification_code,
            "smsCode": verification_code,
            "offerId": offer_id,
        }
        try:
            validate_resp = http_requests.post(
                validate_url,
                json=validate_payload,
                headers=common_headers,
                timeout=30,
            )
            log.info(
                f"验证码校验请求完成 | status={validate_resp.status_code} | phone={phone_number} | body={validate_resp.text}"
            )
            validate_resp.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            log.error(f"验证码校验失败: {e}")
            return {"success": False, "error": f"验证码校验失败: {e}"}

        # 注册
        register_payload = {
            "phoneNumber": phone_number,
            "phone": phone_number,
            "areaCode": "+86",
            "code": verification_code,
            "verificationCode": verification_code,
            "smsCode": verification_code,
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
                "journey": journey,
                "currency": currency,
                "funder_resource": funder_resource,
                "token": token,
                "verification_code": verification_code,
                "offer_id": offer_id,
                "redirect_url": redirect_url if not offline else None,
            }
        except http_requests.exceptions.RequestException as e:
            log.error(f"注册失败: {e}")
            return {"success": False, "error": str(e), "phone_number": phone_number}
