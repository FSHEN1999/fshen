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
        self.selected_application_unique_id: Optional[str] = None
        self.generated_selling_partner_id: Optional[str] = None
        self.session_user_token: str = ""
        self.cached_lender_repayment_id: Optional[str] = None
        self.dowsure_application_code: Optional[str] = None
        self.dowsure_credit_contract_no: Optional[str] = None
        self.dowsure_loan_code: Optional[str] = None
        self.dowsure_loan_contract_no: Optional[str] = None
        self.hsbc_psp_pending_account_id_by_merchant: Dict[str, str] = {}
        self.hsbc_psp_completed_account_ids_in_session: set = set()
        super().__init__(phone_number, db_executor)

    # ======================== 辅助方法 ========================

    def select_application(self, application_unique_id: Optional[str]) -> None:
        """Bind subsequent webhook payloads to the chosen dpu_application."""
        self.selected_application_unique_id = str(application_unique_id or "").strip() or None

    @property
    def application_unique_id(self) -> Optional[str]:
        if self.selected_application_unique_id:
            return self.selected_application_unique_id
        return super().application_unique_id

    @property
    def credit_offer_application_unique_id(self) -> Optional[str]:
        if not self.selected_application_unique_id:
            return super().credit_offer_application_unique_id

        sql = (
            "SELECT application_unique_id FROM dpu_credit_offer "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f"AND application_unique_id = {self._sql_literal(self.selected_application_unique_id)} "
            "ORDER BY created_at DESC LIMIT 1"
        )
        return self.db_executor.execute_sql(sql) or self.selected_application_unique_id

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
        try:
            columns = db_executor.execute_query_all("SHOW COLUMNS FROM dpu_users LIKE 'token'")
        except Exception as exc:
            log.warning(f"Lookup user token schema check skipped: {exc}")
            return ""
        if not columns:
            log.warning("Lookup user token skipped: dpu_users.token column is not available in this environment")
            return ""
        phone_literal = WebDPUMockService._sql_literal(phone_number)
        sql = (
            "SELECT token FROM dpu_users "
            f"WHERE phone_number = {phone_literal} "
            "AND token IS NOT NULL AND token != '' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        try:
            token = db_executor.execute_sql(sql)
        except Exception as exc:
            log.warning(f"Lookup user token skipped: {exc}")
            return ""
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

    def _resolve_latest_platform_offer_id(self, offer_id: Optional[str] = None) -> Optional[str]:
        cleaned_offer_id = str(offer_id or "").strip()
        if cleaned_offer_id and not (cleaned_offer_id.startswith("${") and cleaned_offer_id.endswith("}")):
            return cleaned_offer_id
        manual_offer_row = self._wait_for_manual_offer(
            selling_partner_id=self.generated_selling_partner_id,
            merchant_id=self.merchant_id,
            timeout_seconds=5,
            interval_seconds=1,
        )
        if manual_offer_row and manual_offer_row.get("platform_offer_id"):
            return manual_offer_row.get("platform_offer_id")
        return None

    def update_shop_performance_cny_boost_web(self, offer_id: Optional[str] = None) -> dict:
        resolved_offer_id = self._resolve_latest_platform_offer_id(offer_id)
        if not resolved_offer_id:
            return {
                "success": False,
                "error": "未查询到前置步骤生成的 platform_offer_id，无法更新 dpu_3pl_shop_performance",
                "offer_id": offer_id,
            }

        sql = f"""
UPDATE dpu_3pl_shop_performance
SET
    amazon_tenure = 1825,
    marketplace_country = 'US',
    primary_product_category = 'Electronics',
    seller_status = 'NORMAL',
    report_card_data_date = '2026-05-18 00:00:00',
    year1_sales_value = 4000000.00,
    year2_sales_value = 3500000.00,
    year1_disbursements_value = 3800000.00,
    year2_disbursements_value = 3200000.00,
    quarter1_sales_value = 1210000.00,
    quarter2_sales_value = 1020000.00,
    quarter3_sales_value = 930000.00,
    quarter4_sales_value = 870000.00,
    quarter5_sales_value = 810000.00,
    quarter6_sales_value = 750000.00,
    quarter7_sales_value = 700000.00,
    quarter8_sales_value = 650000.00,
    quarter1_disbursements_value = 1150000.00,
    quarter2_disbursements_value = 960000.00,
    quarter3_disbursements_value = 880000.00,
    quarter4_disbursements_value = 820000.00,
    quarter5_disbursements_value = 760000.00,
    quarter6_disbursements_value = 700000.00,
    quarter7_disbursements_value = 650000.00,
    quarter8_disbursements_value = 600000.00,
    month1_sales_value = 440000.00,
    month2_sales_value = 400000.00,
    month3_sales_value = 370000.00,
    month4_sales_value = 340000.00,
    month5_sales_value = 310000.00,
    month6_sales_value = 290000.00,
    month7_sales_value = 270000.00,
    month8_sales_value = 250000.00,
    month9_sales_value = 230000.00,
    month10_sales_value = 215000.00,
    month11_sales_value = 200000.00,
    month12_sales_value = 190000.00,
    month1_disbursements_value = 420000.00,
    month2_disbursements_value = 380000.00,
    month3_disbursements_value = 350000.00,
    month4_disbursements_value = 320000.00,
    month5_disbursements_value = 300000.00,
    month6_disbursements_value = 280000.00,
    month7_disbursements_value = 260000.00,
    month8_disbursements_value = 240000.00,
    month9_disbursements_value = 220000.00,
    month10_disbursements_value = 200000.00,
    month11_disbursements_value = 190000.00,
    month12_disbursements_value = 180000.00,
    week1_sales_value = 125000.75,
    week2_sales_value = 118000.00,
    week3_sales_value = 110000.00,
    week4_sales_value = 105000.00,
    week5_sales_value = 98000.00,
    week6_sales_value = 92000.00,
    week1_disbursements_value = 118500.20,
    week2_disbursements_value = 105000.00,
    week3_disbursements_value = 98000.00,
    week4_disbursements_value = 112000.00,
    week5_disbursements_value = 95000.00,
    week6_disbursements_value = 88000.00,
    last13week_fba_rate = 85.5,
    last3month_fba_inventory_value = 120000.00,
    latest_fba_inventory_value = 115000.00,
    primary_category_last3month_sales_value = 54000.10,
    ttm_cancellations = 12,
    ttm_feedback = 320,
    ttm_late_shipments = 8,
    ttm_negative_feedback = 9,
    ttm_order_defects = 3,
    ttm_orders = 1520,
    ttm_returns = 45,
    ttm_seller_warnings = 1,
    updated_at = NOW()
WHERE amazon_3pl_offer_id = {self._sql_literal(resolved_offer_id)}
"""
        self.db_executor.execute_sql(sql)
        return {
            "success": True,
            "offer_id": resolved_offer_id,
            "updated_table": "dpu_3pl_shop_performance",
            "where": {"amazon_3pl_offer_id": resolved_offer_id},
            "sql": sql.strip(),
        }

    def ensure_application_context_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        tier_code: Optional[int] = None,
        offer_id: Optional[str] = None,
    ) -> dict:
        """Create or bind the FP application row for the scenario's application step."""
        application_unique_id = self.application_unique_id
        limit_application_unique_id = self.dpu_limit_application_id
        lender_approved_offer_id = self.credit_offer_lender_approved_offer_id

        bootstrap_steps = []
        if not application_unique_id:
            bootstrap_result = self._create_fp_application(
                journey=journey,
                currency=currency,
                funder_resource=funder_resource,
                tier_code=tier_code,
                offer_id=offer_id,
            )
            bootstrap_steps = bootstrap_result.get("steps", [])
            if not bootstrap_result.get("success"):
                return {
                    "success": False,
                    "merchant_id": self.merchant_id,
                    "application_unique_id": None,
                    "limit_application_unique_id": None,
                    "lender_approved_offer_id": self.lender_approved_offer_id,
                    "journey": journey,
                    "currency": currency or self.preferred_currency,
                    "funder_resource": funder_resource or "FUNDPARK",
                    "error": bootstrap_result.get("error", "创建申请单上下文失败"),
                    "steps": bootstrap_steps,
                }
            application_unique_id = bootstrap_result.get("application_unique_id") or self.application_unique_id
            limit_application_unique_id = bootstrap_result.get("limit_application_unique_id") or self.dpu_limit_application_id
            lender_approved_offer_id = bootstrap_result.get("lender_approved_offer_id") or self.credit_offer_lender_approved_offer_id
        elif not self.selected_application_unique_id:
            self.select_application(application_unique_id)

        return {
            "success": bool(application_unique_id),
            "merchant_id": self.merchant_id,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": limit_application_unique_id,
            "lender_approved_offer_id": lender_approved_offer_id or self.lender_approved_offer_id,
            "journey": journey,
            "currency": currency or self.preferred_currency,
            "funder_resource": funder_resource or "FUNDPARK",
            "error": None if application_unique_id else "未查询到 dpu_application.application_unique_id",
            "steps": bootstrap_steps,
        }

    def _run_fp_scene_sql_fallback(self, journey: Optional[str] = None) -> dict:
        application_unique_id = self.application_unique_id
        if not application_unique_id:
            return {"success": False, "error": "缺少 application_unique_id，无法执行 scene SQL fallback"}

        limit_amount = float(self._resolve_limit_selection_amount(journey))
        currency = self.preferred_currency or "USD"
        credit_offer_id = self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id or f"lender-{application_unique_id}"
        auth_row = self.db_executor.execute_query(
            "SELECT id, merchant_account_id, authorization_id FROM dpu_seller_center.dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            "AND status = 'ACTIVE' "
            "AND authorization_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1"
        )
        if not auth_row:
            return {"success": False, "error": "缺少 ACTIVE SP auth token，无法执行 scene SQL fallback"}

        self.db_executor.execute_sql(
            "UPDATE dpu_seller_center.dpu_application "
            "SET application_status='SUBMITTED', "
            "application_submit_datetime=COALESCE(application_submit_datetime, NOW()), "
            "updated_at=NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f"AND application_unique_id = {self._sql_literal(application_unique_id)}"
        )

        self.db_executor.execute_sql(
            "INSERT INTO dpu_seller_center.dpu_limit_application ("
            "id, merchant_id, lender_code, product, limit_application_unique_id, "
            "status, currency, underwritten_limit, created_at, updated_at, create_by, update_by"
            ") "
            "SELECT REPLACE(UUID(),'-',''), "
            f"{self._sql_literal(self.merchant_id)}, "
            "'FUNDPARK', 'LINE_OF_CREDIT', "
            "CONCAT('EFAL', DATE_FORMAT(NOW(), '%Y%m%d%H%i%s'), UPPER(SUBSTRING(REPLACE(UUID(),'-',''), 1, 5))), "
            f"'SUBMITTED', {self._sql_literal(currency)}, {limit_amount:.2f}, NOW(), NOW(), 'SYSTEM', 'SYSTEM' "
            "FROM DUAL WHERE NOT EXISTS ("
            "SELECT 1 FROM dpu_seller_center.dpu_limit_application "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)}"
            ")"
        )

        self.db_executor.execute_sql(
            "UPDATE dpu_seller_center.dpu_limit_application "
            "SET status='SUBMITTED', "
            f"currency={self._sql_literal(currency)}, "
            f"underwritten_limit=COALESCE(underwritten_limit, {limit_amount:.2f}), "
            "updated_at=NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)}"
        )

        limit_application_row = self.db_executor.execute_query(
            "SELECT id, limit_application_unique_id FROM dpu_seller_center.dpu_limit_application "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "ORDER BY created_at DESC LIMIT 1"
        )
        if not limit_application_row:
            return {"success": False, "error": "scene SQL fallback 后仍未获取到 dpu_limit_application 行"}

        self.db_executor.execute_sql(
            "INSERT INTO dpu_seller_center.dpu_limit_application_account ("
            "id, merchant_id, limit_application_unique_id, merchant_account_id, "
            "authorization_id, currency, indicative_limit, underwritten_limit, "
            "approved_limit, signed_limit, activated_limit, psp_status, "
            "created_at, updated_at, create_by, update_by, limit_application_id"
            ") "
            "SELECT REPLACE(UUID(),'-',''), "
            f"{self._sql_literal(self.merchant_id)}, "
            f"{self._sql_literal(limit_application_row['limit_application_unique_id'])}, "
            f"{self._sql_literal(auth_row['merchant_account_id'])}, "
            f"{self._sql_literal(auth_row['authorization_id'])}, "
            f"{self._sql_literal(currency)}, "
            f"0.00, {limit_amount:.2f}, 0.00, 0.00, 0.00, 'INITIAL', "
            "NOW(), NOW(), 'SYSTEM', 'SYSTEM', "
            f"{self._sql_literal(auth_row['id'] if False else limit_application_row['id'])} "
            "FROM DUAL WHERE NOT EXISTS ("
            "SELECT 1 FROM dpu_seller_center.dpu_limit_application_account "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)}"
            ")"
        )

        self.db_executor.execute_sql(
            "INSERT INTO dpu_seller_center.dpu_credit_offer ("
            "id, lender_approved_offer_id, application_id, application_unique_id, "
            "limit_application_id, finance_product, lender_code, merchant_id, "
            "status, e_sign_status, approved_limit_currency, approved_limit_amount, "
            "signed_limit_currency, signed_limit_amount, created_at, updated_at, created_by, updated_by"
            ") "
            "SELECT REPLACE(UUID(),'-',''), "
            f"{self._sql_literal(credit_offer_id)}, "
            "(SELECT id FROM dpu_seller_center.dpu_application "
            f" WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            f" AND application_unique_id = {self._sql_literal(application_unique_id)} "
            " ORDER BY created_at DESC LIMIT 1), "
            f"{self._sql_literal(application_unique_id)}, "
            f"{self._sql_literal(limit_application_row['id'])}, "
            "'LINE_OF_CREDIT', 'FUNDPARK', "
            f"{self._sql_literal(self.merchant_id)}, "
            "'SUBMITTED', 'INITIAL', "
            f"{self._sql_literal(currency)}, {limit_amount:.2f}, "
            f"{self._sql_literal(currency)}, 0.00, NOW(), NOW(), 'SYSTEM', 'SYSTEM' "
            "FROM DUAL WHERE NOT EXISTS ("
            "SELECT 1 FROM dpu_seller_center.dpu_credit_offer "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)}"
            ")"
        )

        self.db_executor.execute_sql(
            "UPDATE dpu_seller_center.dpu_credit_offer "
            "SET status='SUBMITTED', "
            f"lender_approved_offer_id=COALESCE(lender_approved_offer_id, {self._sql_literal(credit_offer_id)}), "
            f"approved_limit_currency={self._sql_literal(currency)}, "
            f"approved_limit_amount={limit_amount:.2f}, "
            "updated_at=NOW() "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)}"
        )

        return {
            "success": True,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": limit_application_row["limit_application_unique_id"],
            "lender_approved_offer_id": credit_offer_id,
            "merchant_account_id": auth_row["merchant_account_id"],
            "authorization_id": auth_row["authorization_id"],
            "currency": currency,
            "limit_amount": limit_amount,
        }

    def _create_fp_application(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        tier_code: Optional[int] = None,
        offer_id: Optional[str] = None,
    ) -> dict:
        """Create only the application row owned by the UI's create-application step."""
        if not self.merchant_id:
            return {"success": False, "error": "未获取到 merchant_id，无法创建申请单上下文", "steps": []}

        steps = []
        auth_token = str(self.session_user_token or "").strip()
        if not auth_token:
            auth_token = self._lookup_user_token(self.db_executor, self.phone_number)
        if not auth_token:
            return {"success": False, "error": "未查询到用户 token，无法创建申请单上下文", "steps": steps}

        product_currency = currency or self.preferred_currency or "USD"
        resource = funder_resource or "FUNDPARK"
        resolved_tier_code = tier_code if tier_code is not None else ("1" if journey == "200K" else "2")
        common_headers = {
            "Authorization": f"Bearer {auth_token}",
            "content-type": "application/json",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": resource,
            "product-currency": product_currency,
            "referer": f"{self._build_portal_base_url(self.db_executor.env)}/",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        }

        create_payload = {"tierCode": resolved_tier_code, "tierSnapshotValue": 0}
        if offer_id is not None:
            create_payload["offerId"] = offer_id
        create_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/create"
        create_result = self._do_post_custom_with_retry(
            create_url,
            "创建申请单",
            json_data=create_payload,
            headers=common_headers,
            attempts=3,
            require_json_data=True,
        )
        created_application_unique_id = None
        if create_result.get("success"):
            create_payload_result = create_result.get("response_json") or {}
            if isinstance(create_payload_result, dict):
                created_application_unique_id = create_payload_result.get("data")
        steps.append({
            "step": "fundpark-application.create",
            "endpoint": create_url,
            "payload": create_payload,
            "result": create_result,
        })
        if not create_result.get("success"):
            return {"success": False, "error": "fundpark-application/create 失败", "steps": steps}

        application_unique_id = self._wait_for_application_unique_id(timeout_seconds=120) or created_application_unique_id
        if not application_unique_id:
            return {"success": False, "error": "等待 dpu_application.application_unique_id 超时", "steps": steps}

        self.select_application(application_unique_id)
        return {
            "success": True,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": self.dpu_limit_application_id,
            "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
            "currency": product_currency,
            "funder_resource": resource,
            "tier_code": resolved_tier_code,
            "steps": steps,
        }

    def _bootstrap_fp_application_context(self, journey: Optional[str] = None) -> dict:
        """Run the remaining FP application preparation needed before tail webhooks."""
        steps = []
        for runner in (
            self.submit_fp_business_profile_web,
            self.submit_fp_director_info_web,
            self.select_fp_offer_limit_web,
            self.activate_fp_offer_quote_web,
            self.link_fp_sp_3pl_shops_web,
            self.run_fp_scheduled_tasks_and_poll_submitted_web,
        ):
            result = runner(journey)
            steps.extend(result.get("steps", []))
            if not result.get("success"):
                result["steps"] = steps
                return result
        return {
            "success": True,
            "application_unique_id": self.application_unique_id,
            "limit_application_unique_id": self.dpu_limit_application_id,
            "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
            "steps": steps,
        }

    def _application_headers_or_error(
        self,
        steps: list,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> tuple[Optional[dict], Optional[dict]]:
        application_unique_id = self.application_unique_id
        if not application_unique_id:
            create_result = self._create_fp_application(journey=None)
            steps.extend(create_result.get("steps", []))
            if not create_result.get("success"):
                return None, create_result
            application_unique_id = create_result.get("application_unique_id") or self.application_unique_id
        self.select_application(application_unique_id)

        auth_token = str(self.session_user_token or "").strip()
        if not auth_token:
            auth_token = self._lookup_user_token(self.db_executor, self.phone_number)
        if not auth_token:
            return None, {"success": False, "error": "未查询到用户 token，无法准备申请单上下文", "steps": steps}

        return {
            "Authorization": f"Bearer {auth_token}",
            "content-type": "application/json",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": funder_resource or "FUNDPARK",
            "product-currency": currency or self.preferred_currency or "USD",
            "referer": f"{self._build_portal_base_url(self.db_executor.env)}/",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        }, None

    def _build_business_info_payload(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        if (currency or self.preferred_currency or "").upper() == "CNY" and (funder_resource or "").upper() == "DOWSURE":
            return {
                "step": "2",
                "isDraft": False,
                "data": {
                    "bizDetail": {
                        "enName": "",
                        "cnName": "广州测试科技有限公司",
                        "regNo": "91440101MA5D3DC9XJ",
                        "contactNumber": {
                            "countryCode": "+86",
                            "number": self.phone_number,
                        },
                        "address": "广州市天河区测试路1号",
                        "operationAddressFlag": True,
                        "operationAddress": "",
                        "id": "bac1c4e04d86407c8927b1fe9e072859",
                    },
                },
                "clear": False,
            }

        return {
            "step": "2",
            "isDraft": False,
            "data": {
                "bizDetail": {
                    "id": None,
                    "applicationId": None,
                    "enName": "Testing Co., Ltd.",
                    "cnName": "",
                    "regNo": "00000001",
                    "companyDate": None,
                    "country": None,
                    "countryCode": None,
                    "area": None,
                    "areaCode": None,
                    "address": None,
                    "mailAddressFlag": None,
                    "mailArea": None,
                    "mailAreaCode": None,
                    "mailCountry": None,
                    "mailCountryCode": None,
                    "mailOfficeAddress1": None,
                    "relationshipHsbcGroupFlag": None,
                    "relationshipHsbcGroupCountry": None,
                    "relationshipHsbcGroupCountryCode": None,
                    "companyType": None,
                    "registeredCountryCode": None,
                    "contactNumber": None,
                    "operationAddressFlag": None,
                    "operationAddress": None,
                },
                "bizInfo": {
                    "topBuyers": ["China", "Hong Kong", "Macao"],
                    "topSuppliers": ["China"],
                    "fundingCountry": "Hong Kong",
                    "industry": "Furniture",
                    "mainProducts": "Home Improvement",
                    "initWealth": ["savings"],
                    "fundSources": ["bizOperations"],
                    "ongoingWealth": ["operationProfit"],
                },
            },
            "clear": True,
        }

    def submit_fp_business_profile_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        business_info_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/business-info"
        business_info_payload = self._build_business_info_payload(currency, funder_resource)
        business_info_result = self._do_post_custom(
            business_info_url,
            "提交 business-info",
            json_data=business_info_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.business-info",
            "endpoint": business_info_url,
            "payload": business_info_payload,
            "result": business_info_result,
        })
        if not business_info_result.get("success"):
            return {"success": False, "error": "business-info 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def submit_fp_director_info_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        name_cn: Optional[str] = None,
        address_detail: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error
        director_info_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/director-info"
        director_info_payload = self._build_director_info_payload(currency, funder_resource, name_cn, address_detail)
        director_info_result = self._do_post_custom(
            director_info_url,
            "提交 director-info",
            json_data=director_info_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.director-info",
            "endpoint": director_info_url,
            "payload": director_info_payload,
            "result": director_info_result,
        })
        if not director_info_result.get("success"):
            return {"success": False, "error": "director-info 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def start_reassessment_web(
        self,
        journey: Optional[str] = None,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
    ) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps, currency, funder_resource)
        if error:
            return error

        reassessment_url = f"{self.api_config.base_url}/dpu-merchant/reassessment/start-reassessment"
        reassessment_payload = {}
        reassessment_result = self._do_post_custom(
            reassessment_url,
            "开始信用评估",
            json_data=reassessment_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "reassessment.start-reassessment",
            "endpoint": reassessment_url,
            "payload": reassessment_payload,
            "result": reassessment_result,
        })
        if not reassessment_result.get("success"):
            return {"success": False, "error": "start-reassessment 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "steps": steps}

    def select_fp_offer_limit_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps)
        if error:
            return error
        limit_selection = self._resolve_limit_selection_amount(journey)
        cache_limit_url = f"{self.api_config.base_url}/dpu-merchant/fundpark-application/cache-higher-limit"
        cache_limit_payload = {"limitSelection": limit_selection}
        cache_limit_result = self._do_post_custom(
            cache_limit_url,
            "缓存高额度选择",
            json_data=cache_limit_payload,
            headers=common_headers,
        )
        steps.append({
            "step": "fundpark-application.cache-higher-limit",
            "endpoint": cache_limit_url,
            "payload": cache_limit_payload,
            "result": cache_limit_result,
        })
        if not cache_limit_result.get("success"):
            return {"success": False, "error": "cache-higher-limit 失败", "steps": steps}

        final_offer_select_url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/final-offer-select"
        final_offer_select_result = self._do_get_custom(
            final_offer_select_url,
            "确认最终 offer 选择",
            headers=common_headers,
        )
        steps.append({
            "step": "credit-offer.final-offer-select",
            "endpoint": final_offer_select_url,
            "payload": None,
            "result": final_offer_select_result,
        })
        if not final_offer_select_result.get("success"):
            return {"success": False, "error": "final-offer-select 失败", "steps": steps}

        return {"success": True, "application_unique_id": self.application_unique_id, "limit_selection": limit_selection, "steps": steps}

    def activate_fp_offer_quote_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps)
        if error:
            return error
        activate_offer_url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/activate-offer"
        activate_offer_result = self._do_post_custom(
            activate_offer_url,
            "激活 offer",
            headers=common_headers,
        )
        steps.append({
            "step": "credit-offer.activate-offer",
            "endpoint": activate_offer_url,
            "payload": None,
            "result": activate_offer_result,
        })
        if not activate_offer_result.get("success"):
            return {"success": False, "error": "activate-offer 失败", "steps": steps}

        credit_offer_url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/create"
        credit_offer_result = self._do_post_custom(
            credit_offer_url,
            "创建 credit offer",
            headers=common_headers,
        )
        steps.append({
            "step": "credit-offer.create",
            "endpoint": credit_offer_url,
            "payload": None,
            "result": credit_offer_result,
        })
        if not credit_offer_result.get("success"):
            return {"success": False, "error": "credit-offer/create 失败", "steps": steps}
        return {"success": True, "application_unique_id": self.application_unique_id, "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id, "steps": steps}

    def link_fp_sp_3pl_shops_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        link_url = f"{self.api_config.base_url}/dpu-merchant/mock/link-sp-3pl-shops"
        link_result = self._do_post_custom(
            link_url,
            "关联 SP/3PL 店铺",
            params={"phone": self.phone_number},
        )
        steps.append({
            "step": "link-sp-3pl-shops",
            "endpoint": link_url,
            "payload": {"phone": self.phone_number},
            "result": link_result,
        })
        if not link_result.get("success"):
            return {"success": False, "error": "link-sp-3pl-shops 失败", "steps": steps}
        return {"success": True, "phone_number": self.phone_number, "steps": steps}

    def run_fp_scheduled_tasks_and_poll_submitted_web(self, journey: Optional[str] = None) -> dict:
        steps = []
        common_headers, error = self._application_headers_or_error(steps)
        if error:
            return error
        application_unique_id = self.application_unique_id
        auth_token = str(common_headers.get("Authorization", "")).replace("Bearer ", "", 1).strip()
        sanction_url = f"{self.api_config.base_url}/dpu-merchant/test/scheduled-tasks/hsbcSanctionTask"
        sanction_result = self._do_post_custom(
            sanction_url,
            "触发 sanction 任务",
            headers=common_headers,
        )
        steps.append({
            "step": "scheduled-tasks.hsbcSanctionTask",
            "endpoint": sanction_url,
            "payload": None,
            "result": sanction_result,
        })
        if not sanction_result.get("success"):
            return {"success": False, "error": "hsbcSanctionTask 失败", "steps": steps}

        first_credit_model_url = f"{self.api_config.base_url}/dpu-merchant/test/scheduled-tasks/first-credit-model"
        first_credit_model_result = self._do_post_custom(
            first_credit_model_url,
            "触发 first-credit-model",
            headers=common_headers,
        )
        steps.append({
            "step": "scheduled-tasks.first-credit-model",
            "endpoint": first_credit_model_url,
            "payload": None,
            "result": first_credit_model_result,
        })
        if not first_credit_model_result.get("success"):
            return {"success": False, "error": "first-credit-model 失败", "steps": steps}

        scheduled_url = f"{self.api_config.base_url}/dpu-merchant/test/scheduled-tasks/first-application-start"
        scheduled_result = self._do_post_custom(
            scheduled_url,
            "触发 first-application-start",
            headers=common_headers,
        )
        steps.append({
            "step": "scheduled-tasks.first-application-start",
            "endpoint": scheduled_url,
            "payload": None,
            "result": scheduled_result,
        })
        if not scheduled_result.get("success"):
            return {"success": False, "error": "first-application-start 失败", "steps": steps}

        application_status_url = f"{self.api_config.base_url}/dpu-merchant/hsbc/application-status"
        application_status_result = self._do_get_custom(
            application_status_url,
            "查询 application-status",
            headers=common_headers,
        )
        steps.append({
            "step": "hsbc.application-status",
            "endpoint": application_status_url,
            "payload": None,
            "result": application_status_result,
        })

        app_status_payload = application_status_result.get("response_json") or {}
        app_status_data = app_status_payload.get("data") if isinstance(app_status_payload, dict) else {}
        app_status_value = (app_status_data or {}).get("status") or ""
        application_unique_id = (
            (app_status_data or {}).get("applicationUniqueId")
            or self.application_unique_id
        )
        app_submitted = application_status_result.get("success") and str(app_status_value).upper() == "SUBMITTED"

        if app_submitted:
            limit_application_unique_id = self._wait_for_limit_application_unique_id(timeout_seconds=600)
            if limit_application_unique_id:
                return {
                    "success": True,
                    "application_unique_id": application_unique_id,
                    "limit_application_unique_id": limit_application_unique_id,
                    "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
                    "application_status": app_status_value,
                    "credit_offer_status": "SKIPPED_AFTER_APPLICATION_SUBMITTED",
                    "steps": steps,
                }

            fallback_result = self._run_fp_scene_sql_fallback(journey)
            steps.append({
                "step": "scene-sql-fallback",
                "endpoint": "dpu_seller_center SQL",
                "payload": {
                    "merchant_id": self.merchant_id,
                    "application_unique_id": application_unique_id,
                    "journey": journey,
                },
                "result": fallback_result,
            })
            if fallback_result.get("success"):
                return {
                    "success": True,
                    "application_unique_id": fallback_result.get("application_unique_id") or application_unique_id,
                    "limit_application_unique_id": fallback_result.get("limit_application_unique_id"),
                    "lender_approved_offer_id": fallback_result.get("lender_approved_offer_id") or self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
                    "application_status": app_status_value,
                    "credit_offer_status": "SUBMITTED_WITH_SCENE_SQL_FALLBACK",
                    "steps": steps,
                }

            return {
                "success": False,
                "error": "application-status 已到 SUBMITTED，但 limit_application_unique_id 未在等待窗口内落库，且 scene SQL fallback 失败",
                "application_unique_id": application_unique_id,
                "limit_application_unique_id": None,
                "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
                "application_status": app_status_value,
                "credit_offer_status": "SUBMITTED_LIMIT_ID_MISSING",
                "steps": steps,
            }

        # MeterSphere treats this script step as successful once the scheduled
        # chain completes its HTTP calls, even if `credit-offer/status` is still
        # warming up. Keep a moderate poll window here so the web endpoint stays
        # aligned with that behavior instead of hard-failing too early.
        submitted_status = self._wait_for_credit_offer_submitted(auth_token, timeout_seconds=75)
        steps.append({
            "step": "credit-offer.status",
            "endpoint": f"{self.api_config.base_url}/dpu-merchant/credit-offer/status",
            "payload": None,
            "result": submitted_status,
        })

        limit_application_unique_id = self._wait_for_limit_application_unique_id(timeout_seconds=30)

        if not limit_application_unique_id and not app_submitted and not submitted_status.get("success"):
            fallback_result = self._run_fp_scene_sql_fallback(journey)
            steps.append({
                "step": "scene-sql-fallback",
                "endpoint": "dpu_seller_center SQL",
                "payload": {
                    "merchant_id": self.merchant_id,
                    "application_unique_id": application_unique_id,
                    "journey": journey,
                },
                "result": fallback_result,
            })
            if fallback_result.get("success"):
                return {
                    "success": True,
                    "application_unique_id": fallback_result.get("application_unique_id") or application_unique_id,
                    "limit_application_unique_id": fallback_result.get("limit_application_unique_id"),
                    "lender_approved_offer_id": fallback_result.get("lender_approved_offer_id") or self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
                    "application_status": app_status_value or None,
                    "credit_offer_status": "SCENE_SQL_FALLBACK_AFTER_STATUS_NEW",
                    "steps": steps,
                }

            return {
                "success": False,
                "error": "scheduled-submit 完成后，credit-offer/status 未就绪且 limit_application_unique_id 未落库",
                "application_unique_id": application_unique_id,
                "limit_application_unique_id": None,
                "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
                "application_status": app_status_value or None,
                "credit_offer_status": submitted_status.get("status"),
                "steps": steps,
            }

        return {
            "success": True,
            "application_unique_id": application_unique_id,
            "limit_application_unique_id": limit_application_unique_id,
            "lender_approved_offer_id": self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id,
            "application_status": app_status_value or None,
            "credit_offer_status": submitted_status.get("status"),
            "steps": steps,
        }

    def _wait_for_application_unique_id(self, timeout_seconds: int = 120, interval_seconds: int = 2) -> Optional[str]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            application_unique_id = self.application_unique_id
            if application_unique_id:
                return application_unique_id
            time.sleep(interval_seconds)
        return None

    def _wait_for_limit_application_unique_id(self, timeout_seconds: int = 120, interval_seconds: int = 2) -> Optional[str]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            limit_application_unique_id = self.dpu_limit_application_id
            if limit_application_unique_id:
                return limit_application_unique_id
            time.sleep(interval_seconds)
        return None

    @staticmethod
    def _resolve_limit_selection_amount(journey: Optional[str]) -> int:
        if journey == "200K":
            return 2000
        if journey == "2000K":
            return 2000000
        return 500000

    def _wait_for_credit_offer_submitted(self, auth_token: str, timeout_seconds: int = 180, interval_seconds: int = 3) -> dict:
        url = f"{self.api_config.base_url}/dpu-merchant/credit-offer/status"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": "FUNDPARK",
            "product-currency": self.preferred_currency or "USD",
            "referer": f"{self._build_portal_base_url(self.db_executor.env)}/",
            "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        }
        deadline = time.time() + timeout_seconds
        attempt = 0
        last_result = None
        poll_history = []
        while time.time() < deadline:
            attempt += 1
            result = self._do_get_custom(url, f"轮询 credit-offer/status 第{attempt}次", headers=headers)
            last_result = result
            payload = result.get("response_json") or {}
            status = ((payload.get("data") or {}).get("status") if isinstance(payload, dict) else None) or ""
            poll_history.append({
                "attempt": attempt,
                "success": bool(result.get("success")),
                "status": status or None,
                "status_code": result.get("status_code"),
                "error": result.get("error") or result.get("error_message"),
            })
            if result.get("success") and str(status).upper() == "SUBMITTED":
                result["status"] = status
                result["poll_attempts"] = attempt
                result["poll_history"] = poll_history[-10:]
                return result
            time.sleep(interval_seconds)

        application_unique_id = self.application_unique_id
        limit_application_unique_id = self.dpu_limit_application_id
        lender_approved_offer_id = self.credit_offer_lender_approved_offer_id or self.lender_approved_offer_id
        if application_unique_id and limit_application_unique_id and lender_approved_offer_id:
            return {
                "success": True,
                "status": "ASSUMED_READY_AFTER_POLL_TIMEOUT",
                "warning": "credit-offer/status did not return SUBMITTED before timeout, but DB identifiers required by webhook tail are available",
                "application_unique_id": application_unique_id,
                "limit_application_unique_id": limit_application_unique_id,
                "lender_approved_offer_id": lender_approved_offer_id,
                "last_result": last_result,
                "poll_attempts": attempt,
                "poll_history": poll_history[-10:],
            }

        error = "credit-offer/status 未在限定时间内到达 SUBMITTED"
        if isinstance(last_result, dict):
            last_result["success"] = False
            last_result["error"] = error
            last_result["poll_attempts"] = attempt
            last_result["poll_history"] = poll_history[-10:]
            return last_result
        return {"success": False, "error": error, "poll_attempts": attempt, "poll_history": poll_history[-10:]}

    @staticmethod
    def _generate_prc_id_number() -> str:
        weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        check_codes = "10X98765432"
        area_code = "440106"
        birth_date = "19900603"
        sequence = f"{random.randint(1, 999):03d}"
        body = f"{area_code}{birth_date}{sequence}"
        checksum = sum(int(value) * weight for value, weight in zip(body, weights)) % 11
        return f"{body}{check_codes[checksum]}"

    def _build_director_info_payload(
        self,
        currency: Optional[str] = None,
        funder_resource: Optional[str] = None,
        name_cn: Optional[str] = None,
        address_detail: Optional[str] = None,
    ) -> dict:
        if (currency or self.preferred_currency or "").upper() == "CNY" and (funder_resource or "").upper() == "DOWSURE":
            return {
                "step": "2",
                "isDraft": False,
                "data": {
                    "persons": [
                        {
                            "position": "LEGAL_REPRESENTATIVE",
                            "nameCn": name_cn or "   ",
                            "nameEn": "Mi",
                            "mobileNumber": {
                                "countryCode": "+86",
                                "number": self.phone_number,
                            },
                            "dowsurePersonInfoExtend": {
                                "idNumber": self._generate_prc_id_number(),
                                "idCardStartDate": "02/06/2026",
                                "idCardEndDate": "",
                                "longTermFlag": "true",
                                "addressDetail": address_detail or "           ",
                            },
                            "dateOfBirth": "03/06/2026",
                            "id": "73f006d1f66b4a18ac0ff3789055d33e",
                        }
                    ],
                    "guarantorList": [],
                },
            }

        return {
            "step": "2",
            "isDraft": False,
            "data": {
                "persons": [
                    {
                        "id": str(uuid.uuid4()),
                        "businessKey": None,
                        "equityRatio": 100,
                        "position": "DIRECTOR_SHAREHOLDER_UBO",
                        "roles": ["DIRECTOR", "SHAREHOLDER", "UBO"],
                        "nameCn": "    ",
                        "nameEn": "LAUTSZ LAN",
                        "firstChiName": None,
                        "lastChiName": None,
                        "frontDocName": "PRC ID-Front@3x-2Sh4SffG.png",
                        "backDocName": "PRC ID-Back@3x-DPHeKKi2.png",
                        "idDocumentType": "PRC_RESIDENT_ID_CARD",
                        "idDocumentFrontUrl": "uploads/default/default/default/file_20260608101214_084c1c663cdb.png",
                        "idDocumentBackUrl": "uploads/default/default/default/file_20260608101217_b73417787427.png",
                        "idDocumentFrontFile": None,
                        "idDocumentBackFile": None,
                        "dateOfBirth": "01/06/2026",
                        "nationality": "China",
                        "mobileNumber": {"countryCode": "+86", "number": "15533906473"},
                        "emailAddress": "15533906473@qq.com",
                        "countryAndRegion": "",
                        "adressLine": "",
                        "secAdressLine": "",
                        "city": "",
                        "postalCode": "",
                        "percentageOfShares": 100,
                        "idFrontFlag": True,
                        "idBackFlag": True,
                        "addStatus": "API",
                        "hsbcPersonInfoExtend": None,
                        "dowsurePersonInfoExtend": None,
                        "guarantorList": None,
                        "mobileNumber.number": "15533906473",
                    }
                ]
            },
        }

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

    def _do_post_webhook(self, data: dict, label: str, headers: Optional[dict] = None) -> dict:
        """统一的 webhook POST 发送 + 日志 + 结果封装"""
        request_headers = headers or {"Content-Type": "application/json"}
        request_info = {
            "method": "POST",
            "url": self.api_config.webhook_url,
            "headers": request_headers,
            "body": data,
        }
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: POST")
        log.info(f"请求URL: {self.api_config.webhook_url}")
        log.info("请求Headers:")
        log.info(json.dumps(request_info["headers"], indent=2, ensure_ascii=False))
        log.info("请求Body（JSON）:")
        log.info(json.dumps(data, indent=2, ensure_ascii=False))
        log.info("=" * 60)

        try:
            response = http_requests.post(self.api_config.webhook_url, json=data, headers=request_headers, timeout=30)
            log.info(f"\n【{label}】完整响应信息")
            log.info("=" * 60)
            log.info(f"响应状态码: {response.status_code}")
            log.info("响应Headers:")
            log.info(self._format_http_headers_for_log(response.headers))
            log.info(f"响应Body: {response.text}")
            log.info("=" * 60)

            success = response.status_code == 200
            response_body = self._format_http_body_for_log(response.text)
            response_json = None
            try:
                response_json = response.json()
            except ValueError:
                response_json = None
            if success:
                log.info(f"{label}成功")
            else:
                headers_for_log = self._format_http_headers_for_log(response.headers)
                request_summary = self._summarize_webhook_request(data)
                log.error(
                    f"{label}失败 | 状态码={response.status_code}\n"
                    f"请求URL: {self.api_config.webhook_url}\n"
                    f"请求摘要:\n{request_summary}\n"
                    f"响应Headers:\n{headers_for_log}\n"
                    f"响应Body:\n{response_body}"
                )
            return {
                "success": success,
                "status_code": response.status_code,
                "response": response.text,
                "response_body": response_body,
                "response_headers": dict(response.headers),
                "response_json": response_json,
                "request_info": request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": response_json,
                },
            }
        except http_requests.exceptions.RequestException as e:
            detail = [f"【{label}】请求异常: {type(e).__name__}: {e}", f"请求URL: {self.api_config.webhook_url}"]
            response_info = None
            if getattr(e, "response", None) is not None:
                response_body = self._format_http_body_for_log(e.response.text)
                response_json = None
                try:
                    response_json = e.response.json()
                except ValueError:
                    response_json = None
                response_info = {
                    "status_code": e.response.status_code,
                    "headers": dict(e.response.headers),
                    "body": response_body,
                    "json": response_json,
                }
                detail.extend([
                    f"响应状态码: {e.response.status_code}",
                    f"响应Headers:\n{self._format_http_headers_for_log(e.response.headers)}",
                    f"响应Body:\n{response_body}",
                ])
            log.error("\n".join(detail))
            return {
                "success": False,
                "error": str(e),
                "error_message": str(e),
                "request_info": request_info,
                "response_info": response_info,
            }

    def _do_post_custom(self, url: str, label: str, json_data: dict = None,
                        params: dict = None, headers: dict = None) -> dict:
        """统一的自定义 URL POST 发送"""
        request_info = {
            "method": "POST",
            "url": url,
            "headers": headers or {},
            "params": params,
            "body": json_data,
        }
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: POST")
        log.info(f"请求URL: {url}")
        if json_data is not None:
            log.info(f"请求Body（JSON）: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
        if params:
            log.info(f"请求Params: {params}")
        if headers:
            log.info(f"请求Headers: {json.dumps(headers, ensure_ascii=False)}")
        log.info("=" * 60)

        try:
            kwargs = {"timeout": 30}
            if json_data is not None:
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
                "response_headers": dict(response.headers),
                "response_json": response_payload if isinstance(response_payload, dict) else None,
                "error_message": business_error,
                "request_info": request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": response_payload if isinstance(response_payload, dict) else None,
                },
            }
        except http_requests.exceptions.RequestException as e:
            detail = [f"【{label}】请求异常: {type(e).__name__}: {e}", f"请求URL: {url}"]
            response_info = None
            if getattr(e, "response", None) is not None:
                response_body = self._format_http_body_for_log(e.response.text)
                response_json = None
                try:
                    response_json = e.response.json()
                except ValueError:
                    response_json = None
                response_info = {
                    "status_code": e.response.status_code,
                    "headers": dict(e.response.headers),
                    "body": response_body,
                    "json": response_json,
                }
                detail.extend([
                    f"响应状态码: {e.response.status_code}",
                    f"响应Headers:\n{self._format_http_headers_for_log(e.response.headers)}",
                    f"响应Body:\n{response_body}",
                ])
            log.error("\n".join(detail))
            return {
                "success": False,
                "error": str(e),
                "error_message": str(e),
                "request_info": request_info,
                "response_info": response_info,
            }

    def _do_post_custom_with_retry(
        self,
        url: str,
        label: str,
        json_data: dict = None,
        params: dict = None,
        headers: dict = None,
        attempts: int = 2,
        interval_seconds: int = 2,
        require_json_data: bool = False,
    ) -> dict:
        """POST helper with a small retry for transient REG gateway timeouts."""
        last_result = None
        for attempt in range(1, max(1, attempts) + 1):
            retry_label = label if attempt == 1 else f"{label} retry {attempt}"
            result = self._do_post_custom(
                url,
                retry_label,
                json_data=json_data,
                params=params,
                headers=headers,
            )
            result["attempt"] = attempt
            last_result = result
            retryable_empty_data = False
            if result.get("success") and require_json_data:
                response_payload = result.get("response_json") or {}
                response_data = response_payload.get("data") if isinstance(response_payload, dict) else None
                if response_data in (None, "", [], {}):
                    result["success"] = False
                    result["error"] = f"{label} response data is empty"
                    result["error_message"] = result["error"]
                    retryable_empty_data = True
            if result.get("success"):
                return result
            error_text = str(result.get("error") or result.get("error_message") or "")
            if (
                not retryable_empty_data
                and "timed out" not in error_text.lower()
                and "timeout" not in error_text.lower()
            ):
                return result
            if attempt < attempts:
                time.sleep(interval_seconds)
        return last_result or {"success": False, "error": f"{label} failed without result"}

    def _do_get_custom(self, url: str, label: str, params: dict = None, headers: dict = None) -> dict:
        """统一的自定义 URL GET 发送"""
        request_info = {
            "method": "GET",
            "url": url,
            "headers": headers or {},
            "params": params,
            "body": None,
        }
        log.info("=" * 60)
        log.info(f"【{label}】完整请求信息")
        log.info("=" * 60)
        log.info("请求方法: GET")
        log.info(f"请求URL: {url}")
        if params:
            log.info(f"请求Params: {params}")
        if headers:
            log.info(f"请求Headers: {json.dumps(headers, ensure_ascii=False)}")
        log.info("=" * 60)

        try:
            kwargs = {"timeout": 30}
            if params:
                kwargs["params"] = params
            if headers:
                kwargs["headers"] = headers
            response = http_requests.get(url, **kwargs)
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
                "response_headers": dict(response.headers),
                "response_json": response_payload if isinstance(response_payload, dict) else None,
                "error_message": business_error,
                "request_info": request_info,
                "response_info": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "json": response_payload if isinstance(response_payload, dict) else None,
                },
            }
        except http_requests.exceptions.RequestException as e:
            response_info = None
            if getattr(e, "response", None) is not None:
                response_body = self._format_http_body_for_log(e.response.text)
                response_json = None
                try:
                    response_json = e.response.json()
                except ValueError:
                    response_json = None
                response_info = {
                    "status_code": e.response.status_code,
                    "headers": dict(e.response.headers),
                    "body": response_body,
                    "json": response_json,
                }
            log.error(f"{label}请求异常: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_message": str(e),
                "request_info": request_info,
                "response_info": response_info,
            }

    def _do_get_custom_with_retry(
        self,
        url: str,
        label: str,
        params: dict = None,
        headers: dict = None,
        attempts: int = 2,
        interval_seconds: int = 2,
    ) -> dict:
        """GET helper with a small retry for transient REG gateway timeouts."""
        last_result = None
        for attempt in range(1, max(1, attempts) + 1):
            retry_label = label if attempt == 1 else f"{label} retry {attempt}"
            result = self._do_get_custom(
                url,
                retry_label,
                params=params,
                headers=headers,
            )
            result["attempt"] = attempt
            last_result = result
            if result.get("success"):
                return result
            error_text = str(result.get("error") or result.get("error_message") or "")
            if "timed out" not in error_text.lower() and "timeout" not in error_text.lower():
                return result
            if attempt < attempts:
                time.sleep(interval_seconds)
        return last_result or {"success": False, "error": f"{label} failed without result"}

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
        """Return the latest SP merchant accounts available for DOWSURE underwriting."""
        auth_rows = self.db_executor.execute_query_all(
            "SELECT authorization_id, merchant_account_id, status, created_at, updated_at "
            "FROM dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND authorization_party = 'SP' "
            "AND authorization_id IS NOT NULL "
            "AND authorization_id != '' "
            "ORDER BY created_at DESC"
        )
        accounts = []
        seen_authorization_ids = set()
        for row in auth_rows or []:
            authorization_id = row.get("authorization_id")
            if not authorization_id or authorization_id in seen_authorization_ids:
                continue
            seen_authorization_ids.add(authorization_id)
            merchant_account_id = row.get("merchant_account_id")
            limit_row = None
            if merchant_account_id:
                limit_row = self.db_executor.execute_query(
                    "SELECT merchant_account_id, created_at, updated_at "
                    "FROM dpu_merchant_account_limit "
                    f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                    f"AND merchant_account_id = {self._sql_literal(merchant_account_id)} "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            if not limit_row:
                limit_row = self.db_executor.execute_query(
                    "SELECT merchant_account_id, created_at, updated_at "
                    "FROM dpu_merchant_account_limit "
                    f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                    f"AND merchant_account_id = {self._sql_literal(authorization_id)} "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            resolved_merchant_account_id = (
                (limit_row or {}).get("merchant_account_id")
                or merchant_account_id
                or ""
            )
            accounts.append({
                "merchantAccountId": authorization_id,
                "merchant_account_id": resolved_merchant_account_id,
                "status": row.get("status"),
                "created_at": row.get("created_at"),
                "updated_at": (limit_row or {}).get("updated_at") or row.get("updated_at"),
                "merchantAccountLimit": None,
            })

        if not accounts:
            limit_rows = self.db_executor.execute_query_all(
                "SELECT merchant_account_id, created_at, updated_at "
                "FROM dpu_merchant_account_limit "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                "AND merchant_account_id IS NOT NULL "
                "AND merchant_account_id != '' "
                "ORDER BY created_at DESC"
            )
            for row in limit_rows or []:
                merchant_account_id = row.get("merchant_account_id")
                if not merchant_account_id:
                    continue
                accounts.append({
                    "merchantAccountId": merchant_account_id,
                    "merchant_account_id": merchant_account_id,
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "merchantAccountLimit": None,
                })

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
        limit_application_unique_id = self.dpu_limit_application_id or "DEFAULT_LIMIT_APP_ID"
        data = self._build_common_webhook_data(
            "underwrittenLimit.completed",
            underwritten_status,
            {
                "dpuMerchantAccountId": [
                    {"MerchantAccountId": self.dpu_auth_token_seller_id}
                ] if self.dpu_auth_token_seller_id else [],
                "dpuApplicationId": self.application_unique_id,
                "dpuLimitApplicationId": limit_application_unique_id,
                "originalRequestId": "req_EFAL17621784619057169",
                "status": underwritten_status,
                "credit": {
                    "marginRate": "2.5",
                    "chargeBases": "Fixed" if self.preferred_currency == "CNY" else "Float",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "creditLimit": {
                        "currency": self.preferred_currency,
                        "underwrittenAmount": {"currency": self.preferred_currency, "amount": amount},
                        "availableLimit": {"currency": self.preferred_currency, "amount": 0.00},
                        "signedLimit": {"currency": self.preferred_currency, "amount": 0.00},
                        "watermark": {"currency": self.preferred_currency, "amount": 0.00},
                    }
                }
            }
        )
        result = self._do_post_webhook(data, "核保状态")
        result.update({
            "amount": amount,
            "status": underwritten_status,
            "limit_application_unique_id": limit_application_unique_id,
        })
        return result

    # ======================== 3. 审批 ========================

    def mock_underwritten_status_dowsure(
        self,
        status: str = None,
        merchant_accounts: Optional[list[dict]] = None,
    ) -> dict:
        """Send the DOWSURE underwritten webhook without interactive input."""
        if status is None:
            return super().mock_underwritten_status_dowsure()

        if status not in {"APPROVED", "REJECTED"}:
            return {"success": False, "error": f"Unsupported DOWSURE underwritten status: {status}"}

        if not merchant_accounts:
            dowsure_accounts = self.get_dowsure_merchant_accounts()
            merchant_accounts = [
                {
                    "merchantAccountId": item["merchantAccountId"],
                    "merchantAccountLimit": item.get("merchantAccountLimit"),
                }
                for item in dowsure_accounts.get("accounts", [])
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
        underwritten_amount = total_underwritten_amount
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
        result = self._do_post_webhook(
            data,
            "DOWSURE核保状态",
            headers={
                "Authorization": "",
                "Content-Type": "application/json",
                "Cookie": "Cookie_1=value",
            },
        )
        result.update({
            "amount": underwritten_amount,
            "total_merchant_account_limit": total_underwritten_amount,
            "status": underwritten_status,
            "merchant_accounts": clean_accounts,
        })
        return result

    # ======================== 18-20. DOWSURE test callbacks ========================

    @staticmethod
    def _dowsure_headers() -> dict:
        return {
            "clientid": "f4527684987a4d48aaf191a03d8a3176",
            "Content-Type": "application/json",
        }

    def send_dowsure_credit_result_web(
        self,
        application_code: str,
        amount: float,
    ) -> dict:
        """Send DOWSURE credit-result callback without interactive input."""
        application_code = str(application_code or "").strip()
        if not application_code:
            return {"success": False, "error": "applicationCode is required"}

        amount = float(amount)
        payload = {
            "applicationCode": application_code,
            "creditStatus": "APPROVE",
            "startTime": "2026-05-26 00:00:00",
            "endTime": "2027-05-26 00:00:00",
            "term": 12,
            "termUnit": "MONTH",
            "apr": 5.4,
            "creditCode": f"CREDIT_HSEF_TEST_{application_code}",
            "creditContractNo": "",
            "amount": amount,
            "currency": "CNY",
            "processingFee": 0.00,
            "reason": "",
            "isLock": "NO",
            "creditResultList": [],
        }

        result = self._do_post_custom(
            "https://sandbox-api.dowsure.com/saasapi/v1/test/credit-result",
            "DOWSURE授信结果",
            json_data=payload,
            headers=self._dowsure_headers(),
        )
        if result.get("success"):
            self.dowsure_application_code = application_code
            self.dowsure_credit_contract_no = ""
        result.update({
            "applicationCode": application_code,
            "creditContractNo": "",
            "amount": amount,
            "currency": "CNY",
            "payload": payload,
        })
        return result

    def send_dowsure_esign_drawdown_result_web(
        self,
        amount: float,
        processing_fee: float,
        application_code: Optional[str] = None,
        credit_contract_no: Optional[str] = None,
    ) -> dict:
        """Send DOWSURE eSign and drawdown callback without interactive input."""
        application_code = str(application_code or self.dowsure_application_code or "").strip()
        credit_contract_no = str(credit_contract_no if credit_contract_no is not None else self.dowsure_credit_contract_no or "")
        if not application_code:
            return {
                "success": False,
                "error": "applicationCode is required. Please run DOWSURE credit result first or input it manually.",
            }

        amount = float(amount)
        processing_fee = float(processing_fee)
        loan_code = f"LOAN_{random.randint(10000, 99999)}"
        payload = {
            "applicationCode": application_code,
            "creditContractNo": credit_contract_no,
            "loanCode": loan_code,
            "loanContractNo": "",
            "amount": amount,
            "startTime": "2026-05-27 12:00:00",
            "endTime": "2027-05-27 12:00:00",
            "term": 12,
            "termUnit": "MONTH",
            "apr": 5.4,
            "currency": "CNY",
            "processingFee": processing_fee,
            "loanStatus": "REPAYMENT",
        }

        result = self._do_post_custom(
            "https://sandbox-api.dowsure.com/saasapi/v1/test/loan",
            "DOWSURE eSign&drawdown结果",
            json_data=payload,
            headers=self._dowsure_headers(),
        )
        if result.get("success"):
            self.dowsure_application_code = application_code
            self.dowsure_credit_contract_no = credit_contract_no
            self.dowsure_loan_code = loan_code
            self.dowsure_loan_contract_no = ""
        result.update({
            "applicationCode": application_code,
            "creditContractNo": credit_contract_no,
            "loanCode": loan_code,
            "loanContractNo": "",
            "amount": amount,
            "processingFee": processing_fee,
            "currency": "CNY",
            "payload": payload,
        })
        return result

    def send_dowsure_repayment_result_web(
        self,
        payment_principal: float,
        payment_interest: float,
        payment_overdue_interest: float,
        deal_amount: float,
        surplus_principal: float,
        application_code: Optional[str] = None,
        loan_code: Optional[str] = None,
    ) -> dict:
        """Send DOWSURE repayment callback without interactive input."""
        application_code = str(application_code or self.dowsure_application_code or "").strip()
        loan_code = str(loan_code or self.dowsure_loan_code or "").strip()
        if not application_code or not loan_code:
            return {
                "success": False,
                "error": "applicationCode/loanCode is required. Please run DOWSURE eSign&drawdown first or input them manually.",
            }

        payment_principal = float(payment_principal)
        payment_interest = float(payment_interest)
        payment_overdue_interest = float(payment_overdue_interest)
        deal_amount = float(deal_amount)
        surplus_principal = float(surplus_principal)
        payload = {
            "applicationCode": application_code,
            "currentTerm": 1,
            "loanCode": loan_code,
            "loanContractNo": "",
            "serialNo": f"RPM_{random.randint(10000, 99999)}",
            "paymentPrincipal": payment_principal,
            "realPaymentPrincipal": payment_principal,
            "paymentInterest": payment_interest,
            "realPaymentInterest": payment_interest,
            "paymentOverdueInterest": payment_overdue_interest,
            "realPaymentOverdueInterest": payment_overdue_interest,
            "dealAmount": deal_amount,
            "surplusPrincipal": surplus_principal,
            "dealDate": "2026-05-27 00:00:00",
            "realDate": "2026-05-27 00:00:00",
        }

        result = self._do_post_custom(
            "https://sandbox-api.dowsure.com/saasapi/v1/test/repayment",
            "DOWSURE还款结果",
            json_data=payload,
            headers=self._dowsure_headers(),
        )
        result.update({
            "applicationCode": application_code,
            "loanCode": loan_code,
            "loanContractNo": "",
            "dealAmount": deal_amount,
            "payload": payload,
        })
        return result

    def retry_dowsure_callback_web(self) -> dict:
        """Retry DOWSURE callback delivery without interactive input."""
        url = "https://sandbox-api.dowsure.com/saasapi/partner/hsef/internal/result/callback/retry?limit=100"
        headers = {
            "clientid": "f4527684987a4d48aaf191a03d8a3176",
        }

        result = self._do_post_custom(
            url,
            "DOWSURE重试请求",
            headers=headers,
        )
        result.update({
            "request_method": "POST",
            "request_url": url,
            "request_headers": headers,
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

    def _mock_psp_status(
        self,
        is_start: bool = True,
        psp_status: str = None,
        merchant_account_id: Optional[str] = None,
    ) -> dict:
        """模拟PSP状态更新（参数化版本）"""
        if psp_status is None:
            return super()._mock_psp_status(is_start)

        event_type = "psp.verification.started" if is_start else "psp.verification.completed"

        requested_account_id = str(merchant_account_id or "").strip()
        sp_auth_info = None
        if requested_account_id:
            limit_row = self.db_executor.execute_query(
                "SELECT psp_status FROM dpu_merchant_account_limit "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if str((limit_row or {}).get("psp_status") or "").upper() == "SUCCESS":
                return {
                    "success": False,
                    "error": f"PSP状态已为SUCCESS，不允许选择 | merchant_account_id={requested_account_id}",
                }
            sp_auth_info = self.db_executor.execute_query(
                "SELECT merchant_id, authorization_id, merchant_account_id, status FROM dpu_auth_token "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "AND authorization_party = 'SP' "
                "AND status = 'ACTIVE' "
                "AND authorization_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if not sp_auth_info:
                return {
                    "success": False,
                    "error": f"未查询到可用SP授权记录 | merchant_account_id={requested_account_id}",
                }
        else:
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

        result.update({
            "status": psp_status,
            "merchant_account_id": merchant_account_id,
            "selected_merchant_account_id": requested_account_id or None,
        })
        return result

    def mock_psp_start_status(self, status: str = None, merchant_account_id: Optional[str] = None) -> dict:
        """模拟PSP开始状态"""
        return self._mock_psp_status(is_start=True, psp_status=status, merchant_account_id=merchant_account_id)

    def mock_psp_completed_status(self, status: str = None, merchant_account_id: Optional[str] = None) -> dict:
        """模拟PSP完成状态"""
        return self._mock_psp_status(is_start=False, psp_status=status, merchant_account_id=merchant_account_id)

    def get_psp_authorization_rows(self) -> dict:
        """Return SP/3PL/PSP status rows grouped by merchant_account_id."""
        if not self.merchant_id:
            return {"success": False, "error": "未获取到 merchant_id", "rows": []}

        auth_rows = self.db_executor.execute_query_all(
            "SELECT merchant_account_id, authorization_party, authorization_id, status, state, "
            "processing_stage, created_at, updated_at "
            "FROM dpu_auth_token "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND merchant_account_id IS NOT NULL "
            "AND merchant_account_id != '' "
            "AND authorization_party IN ('SP', '3PL') "
            "ORDER BY merchant_account_id, authorization_party, created_at DESC"
        )

        limit_rows = self.db_executor.execute_query_all(
            "SELECT merchant_account_id, psp_status, created_at, updated_at "
            "FROM dpu_merchant_account_limit "
            f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
            "AND merchant_account_id IS NOT NULL "
            "AND merchant_account_id != '' "
            "ORDER BY merchant_account_id, created_at DESC"
        )

        grouped: dict[str, dict] = {}
        for row in auth_rows or []:
            merchant_account_id = row.get("merchant_account_id")
            if not merchant_account_id:
                continue
            item = grouped.setdefault(
                merchant_account_id,
                {
                    "merchant_account_id": merchant_account_id,
                    "sp_authorization_id": None,
                    "sp_status": None,
                    "three_pl_authorization_id": None,
                    "three_pl_status": None,
                    "psp_status": None,
                    "psp_updated_at": None,
                },
            )
            party = row.get("authorization_party")
            if party == "SP" and not item.get("sp_status"):
                item["sp_authorization_id"] = row.get("authorization_id")
                item["sp_status"] = row.get("status")
                item["sp_state"] = row.get("state")
                item["sp_processing_stage"] = row.get("processing_stage")
            elif party == "3PL" and not item.get("three_pl_status"):
                item["three_pl_authorization_id"] = row.get("authorization_id")
                item["three_pl_status"] = row.get("status")

        for row in limit_rows or []:
            merchant_account_id = row.get("merchant_account_id")
            if not merchant_account_id:
                continue
            item = grouped.setdefault(
                merchant_account_id,
                {
                    "merchant_account_id": merchant_account_id,
                    "sp_authorization_id": None,
                    "sp_status": None,
                    "three_pl_authorization_id": None,
                    "three_pl_status": None,
                    "psp_status": None,
                    "psp_updated_at": None,
                },
            )
            if item.get("psp_status") is None:
                item["psp_status"] = row.get("psp_status")
                item["psp_updated_at"] = row.get("updated_at") or row.get("created_at")

        rows = sorted(grouped.values(), key=lambda item: item.get("merchant_account_id") or "")
        default_selected_merchant_account_id = None
        default_sp_row = next(
            (
                row for row in auth_rows or []
                if row.get("authorization_party") == "SP"
                and row.get("status") == "ACTIVE"
                and row.get("authorization_id")
            ),
            None,
        )
        if default_sp_row:
            default_selected_merchant_account_id = default_sp_row.get("merchant_account_id")
        return {
            "success": True,
            "rows": rows,
            "default_selected_merchant_account_id": default_selected_merchant_account_id,
        }

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
            service.session_user_token = auth_token

            generated_selling_partner_id = f"spshouquanfs{random.randint(10000, 99999)}"
            service.generated_selling_partner_id = generated_selling_partner_id

            sp_auth_url = f"{service.api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-auth-url"
            sp_auth_payload = {
                "state": state,
                "sceneCode": "SHOP_BIND" if offline else "SHOP_BIND_NO_OFFER",
                "sourceCode": funder_resource,
                "redirectUrl": f"{WebDPUMockService._build_portal_base_url(env)}/redirect-loading?state={state}",
            }
            sp_auth_headers = {
                "Authorization": f"Bearer {auth_token}",
                "content-type": "application/json",
                "finance-product": "LINE_OF_CREDIT",
                "funder-resource": funder_resource,
                "product-currency": currency,
                "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            }
            sp_auth_result = service._do_post_custom_with_retry(
                sp_auth_url,
                "SP auth-url",
                json_data=sp_auth_payload,
                headers=sp_auth_headers,
                attempts=3,
                require_json_data=True,
            )
            sp_auth_response_body = sp_auth_result.get("response_body") or ""
            sp_auth_payload_result = sp_auth_result.get("response_json")
            sp_auth_url_recorded = False
            if not sp_auth_result.get("success"):
                sp_auth_state_exists = service.db_executor.execute_sql(
                    "SELECT state FROM dpu_auth_token "
                    f"WHERE merchant_id = '{session_ctx.merchant_id}' "
                    "AND authorization_party = 'SP' "
                    f"AND state = '{state}' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                if sp_auth_state_exists:
                    sp_auth_result["warning"] = "sp-auth-url response data was empty, but dpu_auth_token.state exists; continue"
                    steps.append({
                        "step": "SP auth-url",
                        "endpoint": sp_auth_url,
                        "payload": sp_auth_payload,
                        "result": {**sp_auth_result, "selling_partner_id": generated_selling_partner_id, "auth_token_source": auth_token_source, "db_state": sp_auth_state_exists},
                    })
                    sp_auth_url_recorded = True
                else:
                    return {
                        "success": False,
                        "stage": "sp_auth_url",
                        "error": sp_auth_result.get("error") or sp_auth_result.get("error_message") or "sp-auth-url failed",
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
                            "result": {**sp_auth_result, "selling_partner_id": generated_selling_partner_id, "auth_token_source": auth_token_source},
                        }],
                    }

            if not sp_auth_url_recorded:
                steps.append({
                    "step": "SP auth-url",
                    "endpoint": sp_auth_url,
                    "payload": sp_auth_payload,
                    "result": {
                        "success": True,
                        "status_code": sp_auth_result.get("status_code"),
                        "response_body": sp_auth_response_body,
                        "response_json": sp_auth_payload_result if isinstance(sp_auth_payload_result, dict) else None,
                        "selling_partner_id": generated_selling_partner_id,
                        "auth_token_source": auth_token_source,
                    },
                })
            sp_auth_result_url = f"{service.api_config.base_url}/dpu-merchant/shop-authorization/v2/sp-shop-auth-result?state={state}"
            sp_auth_result_headers = {
                "Authorization": f"Bearer {auth_token}",
                "finance-product": "LINE_OF_CREDIT",
                "product-currency": currency,
                "referer": f"{WebDPUMockService._build_portal_base_url(env)}/",
                "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
            }
            sp_auth_result = service._do_get_custom_with_retry(
                sp_auth_result_url,
                "SP auth-result",
                headers=sp_auth_result_headers,
                attempts=2,
            )
            sp_auth_result_body = sp_auth_result.get("response_body") or ""
            sp_auth_result_payload = sp_auth_result.get("response_json")
            sp_auth_result_recorded = False
            if not sp_auth_result.get("success"):
                state_exists = service.db_executor.execute_sql(
                    "SELECT state FROM dpu_auth_token "
                    f"WHERE merchant_id = '{session_ctx.merchant_id}' "
                    "AND authorization_party = 'SP' "
                    f"AND state = '{state}' "
                    "ORDER BY created_at DESC LIMIT 1"
                )
                if state_exists:
                    sp_auth_result["warning"] = "sp-shop-auth-result timed out, but dpu_auth_token.state exists; continue with SP auth callback"
                    steps.append({
                        "step": "SP auth-result",
                        "endpoint": sp_auth_result_url,
                        "payload": {"state": state},
                        "result": {**sp_auth_result, "auth_token_source": auth_token_source, "db_state": state_exists},
                    })
                    sp_auth_result_recorded = True
                else:
                    return {
                        "success": False,
                        "stage": "sp_shop_auth_result",
                        "error": sp_auth_result.get("error") or sp_auth_result.get("error_message") or "sp-shop-auth-result failed",
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
                            "result": {**sp_auth_result, "auth_token_source": auth_token_source},
                        }],
                    }

            if not sp_auth_result_recorded:
                steps.append({
                    "step": "SP auth-result",
                    "endpoint": sp_auth_result_url,
                    "payload": {"state": state},
                    "result": {
                        "success": True,
                        "status_code": sp_auth_result.get("status_code"),
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

            redirect_result = service._run_multishop_3pl_redirect_with_post()
            steps.append({
                "step": "3PL redirect",
                "endpoint": "/api/register-and-run-multishop:3pl-redirect",
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
                1: "The lender country doesn't match with the Seller reporting country",
                2: "Active credit approval exists",
                3: "An offer already exists for the seller for the same partner product combination",
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

    def _run_multishop_3pl_redirect_with_post(self) -> dict:
        """Run the register-and-bind 3PL redirect flow, including the required POST callback."""
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
        log.info("【注册并完成绑店-3PL重定向】")
        log.info("=" * 60)

        try:
            response = http_requests.get(self.api_config.redirect_url, params={"offerId": platform_offer_id}, timeout=30)
            response_body = self._format_redirect_body_for_log(response.text)
            log.info(f"3PL GET URL: {self.api_config.redirect_url}")
            log.info(f"3PL GET Params: offerId={platform_offer_id}")
            log.info(f"3PL GET status: {response.status_code}")
            log.info(f"3PL GET response: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_response_body = None
            if getattr(e, "response", None) is not None:
                error_response_body = self._format_redirect_body_for_log(e.response.text)
            log.error(f"3PL GET failed: {type(e).__name__}: {e}")
            return {
                "success": False,
                "error": str(e),
                "selling_partner_id": seller_id,
                "platform_offer_id": platform_offer_id,
                "redirect_url": full_redirect_url,
                "redirect_get": {
                    "status_code": e.response.status_code if getattr(e, "response", None) is not None else None,
                    "response_body": error_response_body,
                },
            }

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
            log.info(f"请求URL: {self.api_config.redirect_url}")
            log.info(f"请求Params: offerId={platform_offer_id}")
            log.info(f"响应状态码: {response.status_code}")
            log.info(f"响应Body: {response_body}")
            response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            error_detail = f"【多店铺-3PL重定向】请求失败: {type(e).__name__}: {e}\n  - 请求URL: {full_redirect_url}"
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

        return {
            "success": True,
            "selling_partner_id": seller_id,
            "platform_offer_id": platform_offer_id,
            "redirect_url": full_redirect_url,
            "status_code": response.status_code,
            "response_body": response_body,
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

    def mock_psp_start_status_hsbc(self, merchant_account_id: Optional[str] = None) -> dict:
        """发送HSBC版PSP开始通知"""
        log.info("开始处理PSP开始（HSBC）...")
        return self._send_hsbc_psp_notification_web(
            event_type="psp.verification.started",
            result="PROCESSING",
            failure_reason=None,
            title="PSP开始（HSBC）",
            for_completed=False,
            merchant_account_id=merchant_account_id,
        )

    # ======================== 15. PSP 完成（HSBC） ========================

    def mock_psp_completed_status_hsbc(self, result: str = None, merchant_account_id: Optional[str] = None) -> dict:
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
            for_completed=True,
            merchant_account_id=merchant_account_id,
        )

    def _get_hsbc_psp_notification_context_web(
        self,
        for_completed: bool = False,
        merchant_account_id: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """获取HSBC版PSP通知上下文（Web版，不调用 input）"""
        requested_account_id = str(merchant_account_id or "").strip()
        if requested_account_id:
            limit_row = self.db_executor.execute_query(
                "SELECT psp_status FROM dpu_merchant_account_limit "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "ORDER BY created_at DESC LIMIT 1"
            )
            if str((limit_row or {}).get("psp_status") or "").upper() == "SUCCESS":
                log.error(f"PSP状态已为SUCCESS，不允许选择 | merchant_account_id={requested_account_id}")
                return None
            sp_auth_info = self.db_executor.execute_query(
                "SELECT merchant_id, authorization_id, merchant_account_id, status FROM dpu_auth_token "
                f"WHERE merchant_id = {self._sql_literal(self.merchant_id)} "
                f"AND merchant_account_id = {self._sql_literal(requested_account_id)} "
                "AND authorization_party = 'SP' "
                "AND status = 'ACTIVE' "
                "AND authorization_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1"
            )
        else:
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
                                         for_completed: bool = False,
                                         merchant_account_id: Optional[str] = None) -> dict:
        """发送HSBC版PSP通知（Web版）"""
        context = self._get_hsbc_psp_notification_context_web(
            for_completed=for_completed,
            merchant_account_id=merchant_account_id,
        )
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

        api_result.update({
            "result": result,
            "merchant_account_id": context["merchant_account_id"],
            "selected_merchant_account_id": str(merchant_account_id or "").strip() or None,
        })
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
