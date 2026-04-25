import hashlib
import json
import os
import random
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pymysql
import requests

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {
    "host": "18.162.145.173",
    "user": "dpu_reg",
    "password": os.getenv("DPU_REG_DB_PASSWORD", ""),
    "database": "dpu_seller_center",
    "port": 3307,
    "charset": "utf8mb4",
    "connect_timeout": 15,
    "read_timeout": 15,
    "autocommit": True,
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

SCENARIO_PATH = Path(__file__).with_name("scenario_1.ms")
OUTPUT_PATH = Path(__file__).with_name("scenario_1_validation_result.json")
WEBHOOK_EVENT_TYPES = {
    27: "approvedoffer.completed",
    28: "psp.verification.started",
    29: "psp.verification.completed",
    30: "esign.completed",
}
BUSINESS_ASSERTION_STEPS = {4, 5, 6, 7, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22}
WEBHOOK_ASSERTION_STEPS = set(WEBHOOK_EVENT_TYPES)
HTTP_STATUS_SCRIPT_ASSERTION_STEPS = {8, 10}
DEBUG_VARIABLE_KEYS = (
    "phone",
    "phoneNumber",
    "email",
    "state",
    "selling_partner_id",
    "idempotency_key",
    "platform_offer_id",
    "platformOfferId",
    "merchantId",
    "preferredCurrency",
    "dpuLimitApplicationId",
    "dpuApplicationId",
    "dpuMerchantAccountId",
    "lenderApprovedOfferId",
    "lenderCreditId",
    "lenderLoanId",
    "lenderRepaymentScheduled",
    "lenderRepaymentId",
    "underwrittenOriginalRequestId",
    "approvedOriginalRequestId",
    "eventId",
    "approvedAmount",
    "signedAmount",
    "underwrittenAmount",
    "credit_offer_status",
    "poll_count",
)
RUN_CONTEXT = {}


class StepError(RuntimeError):
    pass


def to_jsonable(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def mask_sensitive(value):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"authorization", "password", "confirmpassword", "token", "accesstoken", "refreshtoken"}:
                masked[key] = "***"
            else:
                masked[key] = mask_sensitive(item)
        return masked
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value


def compact_text(text, limit=1000):
    text = "" if text is None else str(text)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def log_section(title):
    print(f"\n===== {title} =====", flush=True)


def snapshot_variables(variables, keys=None):
    keys = keys or DEBUG_VARIABLE_KEYS
    return mask_sensitive({key: variables.get(key) for key in keys if key in variables})


def log_variables(title, variables, keys=None):
    print(
        f"[VARS] {title}: {json.dumps(snapshot_variables(variables, keys), ensure_ascii=False)}",
        flush=True,
    )


def log_request_response(request_spec, response):
    safe_headers = mask_sensitive(request_spec.get("headers") or {})
    safe_body = mask_sensitive(request_spec.get("json_body"))
    elapsed = request_spec.get("elapsed_ms")
    elapsed_text = f" elapsedMs={elapsed}" if elapsed is not None else ""
    print(
        f"[HTTP] {request_spec['method']} {request_spec['path']} -> {response.status_code}{elapsed_text}",
        flush=True,
    )
    if request_spec.get("params"):
        print(f"[HTTP] params={json.dumps(request_spec['params'], ensure_ascii=False)}", flush=True)
    print(f"[HTTP] headers={json.dumps(safe_headers, ensure_ascii=False)}", flush=True)
    if safe_body is not None:
        print(f"[HTTP] body={json.dumps(safe_body, ensure_ascii=False)}", flush=True)
    print(f"[HTTP] response={compact_text(response.text)}", flush=True)


def log_db_result(description, row):
    print(f"[DB] {description}: {to_jsonable(row)}", flush=True)


def ensure_db_password():
    if not DB_CONFIG["password"]:
        raise StepError("Missing DPU_REG_DB_PASSWORD for reg database validation")


def load_scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def get_step(data, sort_no):
    return next(
        step
        for step in data["scenarioStepList"]
        if step.get("sort") == sort_no and step.get("parentId") is None
    )


def get_blob(data, sort_no):
    step = get_step(data, sort_no)
    return json.loads(data["scenarioStepBlobMap"][str(step["id"])])


def substitute(text, variables):
    if text is None:
        return text
    text = str(text).replace("@email", variables.get("email", ""))

    def repl(match):
        return str(variables.get(match.group(1), ""))

    return re.sub(r"\$\{([^}]+)\}", repl, text)


def enabled_headers(blob, variables):
    headers = {}
    for header in blob.get("headers", []):
        if header.get("enable") and header.get("key"):
            headers[header["key"]] = substitute(header.get("value", ""), variables)
    return headers


def enabled_query(blob, variables):
    params = {}
    for item in blob.get("query", []):
        if item.get("enable") and item.get("key"):
            params[item["key"]] = substitute(item.get("value", ""), variables)
    return params


def request_body(blob, variables):
    body = (
        blob.get("body", {}).get("bodyDataByType", {}).get("jsonValue")
        or blob.get("body", {}).get("jsonBody", {}).get("jsonValue")
    )
    if not body:
        return None
    return json.loads(substitute(body, variables))


def build_request(data, sort_no, variables):
    blob = get_blob(data, sort_no)
    return {
        "method": blob["method"].upper(),
        "url": BASE_URL + blob["path"],
        "path": blob["path"],
        "headers": enabled_headers(blob, variables),
        "params": enabled_query(blob, variables),
        "json_body": request_body(blob, variables),
    }


def send_request(request_spec):
    start = time.perf_counter()
    try:
        response = requests.request(
            request_spec["method"],
            request_spec["url"],
            headers=request_spec["headers"],
            params=request_spec["params"] or None,
            json=request_spec["json_body"],
            timeout=60,
        )
    except requests.RequestException as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        print(
            f"[HTTP][ERROR] {request_spec['method']} {request_spec['path']} "
            f"elapsedMs={elapsed_ms} error={exc}",
            flush=True,
        )
        raise
    request_spec["elapsed_ms"] = int((time.perf_counter() - start) * 1000)
    log_request_response(request_spec, response)
    return response


def verify_file_scan_result(variables, file_url, label):
    request_spec = {
        "method": "GET",
        "url": BASE_URL + "/dpu-file/files/upload/getFileScanResult",
        "path": "/dpu-file/files/upload/getFileScanResult",
        "headers": {
            "Authorization": f"Bearer {variables['token']}",
            "content-type": "application/json",
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": "FUNDPARK",
            "product-currency": "USD",
        },
        "params": {"fileUrl": file_url},
        "json_body": None,
    }
    payload = expect_business_ok(send_request(request_spec), f"file scan result {label}")
    data = payload.get("data") or {}
    return {
        "label": label,
        "file_url": file_url,
        "scan_status": data.get("scanStatus"),
        "file_scan_status_count": len(data.get("fileScanStatusDTOs") or []),
    }


def db_fetchone(sql, args=()):
    ensure_db_password()
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()


def db_fetchall(sql, args=()):
    ensure_db_password()
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def db_execute(sql, args=()):
    ensure_db_password()
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            affected = cur.execute(sql, args)
        conn.commit()
        return affected
    finally:
        conn.close()


def safe_db_fetchall(description, sql, args=()):
    try:
        rows = db_fetchall(sql, args)
        print(f"[DB] {description}: {json.dumps(to_jsonable(rows), ensure_ascii=False)}", flush=True)
        return rows
    except Exception as exc:
        print(f"[DB][WARN] {description} failed: {exc}", flush=True)
        return []


def wait_fetchone(sql, args, description, timeout=45, interval=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = db_fetchone(sql, args)
        if row and any(item not in (None, "") for item in row):
            log_db_result(description, row)
            return row
        time.sleep(interval)
    raise StepError(f"Timed out waiting for {description}")


def lender_event_count(merchant_id, event_type, field_name=None, field_value=None):
    if field_name:
        row = db_fetchone(
            "SELECT COUNT(*) FROM dpu_lender_event "
            "WHERE merchant_id=%s AND event_type=%s "
            f"AND (JSON_UNQUOTE(JSON_EXTRACT(event_data, '$.{field_name}'))=%s "
            f"OR JSON_UNQUOTE(JSON_EXTRACT(event_data, '$.details.{field_name}'))=%s)",
            (merchant_id, event_type, field_value, field_value),
        )
    else:
        row = db_fetchone(
            "SELECT COUNT(*) FROM dpu_lender_event WHERE merchant_id=%s AND event_type=%s",
            (merchant_id, event_type),
        )
    count = int(row[0] or 0) if row else 0
    print(f"[DB] lender_event_count eventType={event_type} field={field_name} value={field_value} count={count}", flush=True)
    return count


def wait_lender_event_count(merchant_id, event_type, field_name=None, field_value=None, timeout=12, interval=2):
    deadline = time.time() + timeout
    last_count = 0
    while time.time() < deadline:
        last_count = lender_event_count(merchant_id, event_type, field_name, field_value)
        if last_count:
            return last_count
        time.sleep(interval)
    return last_count


def mark_virus_scan_ready(variables, timeout=20, interval=2):
    """The reg mock file-scan API can leave notify dependencies pending; unblock this test application."""
    phone = variables["phone"]
    deadline = time.time() + timeout
    app_row = None
    total_row = None
    while time.time() < deadline:
        app_row = db_fetchone(
            "SELECT a.application_unique_id, a.merchant_id "
            "FROM dpu_application a JOIN dpu_users u ON u.merchant_id=a.merchant_id "
            "WHERE u.phone_number=%s ORDER BY a.created_at DESC LIMIT 1",
            (phone,),
        )
        if app_row:
            variables["dpuApplicationId"] = app_row[0]
            variables["merchantId"] = app_row[1]
            total_row = db_fetchone(
                "SELECT COUNT(*) FROM dpu_notify_event_dependency d "
                "JOIN dpu_notify_event e ON e.id=d.event_id AND e.event_type=d.event_type AND e.biz_id=d.biz_id "
                "WHERE e.biz_id=%s AND d.dependency_type='VIRUS_SCAN'",
                (variables["dpuApplicationId"],),
            )
            if int((total_row or [0])[0] or 0) > 0:
                break
        time.sleep(interval)

    if not app_row:
        raise StepError(f"Missing dpu_application before VIRUS_SCAN dependency repair, phone={phone}")

    affected = db_execute(
        "UPDATE dpu_notify_event_dependency d "
        "JOIN dpu_notify_event e ON e.id=d.event_id AND e.event_type=d.event_type AND e.biz_id=d.biz_id "
        "SET d.dependency_status='READY', d.dependency_finish_time=NOW(), d.update_time=NOW() "
        "WHERE e.biz_id=%s AND d.dependency_type='VIRUS_SCAN' AND d.dependency_status<>'READY'",
        (variables["dpuApplicationId"],),
    )
    pending_row = db_fetchone(
        "SELECT COUNT(*) FROM dpu_notify_event_dependency d "
        "JOIN dpu_notify_event e ON e.id=d.event_id AND e.event_type=d.event_type AND e.biz_id=d.biz_id "
        "WHERE e.biz_id=%s AND d.dependency_type='VIRUS_SCAN' AND d.dependency_status<>'READY'",
        (variables["dpuApplicationId"],),
    )
    total_count = int((total_row or [0])[0] or 0)
    pending_count = int((pending_row or [0])[0] or 0)
    print(
        "[DB] VIRUS_SCAN dependency repair "
        f"application={variables['dpuApplicationId']} total={total_count} affected={affected} pending={pending_count}",
        flush=True,
    )
    if pending_count:
        raise StepError(f"VIRUS_SCAN dependency is still pending for {variables['dpuApplicationId']}")
    return {"application_id": variables["dpuApplicationId"], "total": total_count, "affected": affected}


def api_request(data, sort_no, variables):
    return send_request(build_request(data, sort_no, variables))


def expect_business_ok(response, step_name):
    if response.status_code != 200:
        raise StepError(f"{step_name} HTTP {response.status_code}: {response.text[:800]}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise StepError(f"{step_name} returned non-JSON: {response.text[:800]}") from exc
    if payload.get("code") != 200:
        raise StepError(f"{step_name} business failed: {payload}")
    return payload


def expect_http_ok(response, step_name):
    if response.status_code != 200:
        raise StepError(f"{step_name} HTTP {response.status_code}: {response.text[:800]}")
    return response


def expect_webhook_ok(response, step_name):
    if response.status_code != 200:
        raise StepError(f"{step_name} HTTP {response.status_code}: {response.text[:800]}")
    return response.text[:1000]


def gen_phone():
    prefixes = [
        "130", "131", "132", "133", "135", "136", "137", "138", "139",
        "150", "151", "152", "155", "156", "157", "158", "159",
        "166", "171", "172", "173", "175", "176", "177", "178",
        "180", "181", "182", "183", "184", "185", "186", "187", "188", "189",
        "191", "193", "195", "196", "198", "199",
    ]
    return random.choice(prefixes) + str(random.randint(0, 99999999)).zfill(8)


def gen_selling_partner_id():
    seed = f"{uuid.uuid4()}-{random.random()}".encode("utf-8")
    return hashlib.md5(seed).hexdigest().upper()


def fetch_sms_code(phone):
    for _ in range(15):
        row = db_fetchone(
            "SELECT placeholders FROM dpu_sms_record "
            "WHERE phone_number=%s "
            "ORDER BY COALESCE(send_time, create_time) DESC, id DESC LIMIT 1",
            (phone,),
        )
        if row and row[0]:
            raw = row[0]
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                code = payload.get("verificationCode") if isinstance(payload, dict) else None
            except Exception:
                match = re.search(r"(?<!\d)(\d{6})(?!\d)", str(raw))
                code = match.group(1) if match else None
            if code:
                return code
        time.sleep(2)
    raise StepError("Failed to fetch SMS verification code from reg DB")


def poll_credit_offer_status(data, variables, steps):
    blob = None
    loop_step = next(
        step
        for step in data["scenarioStepList"]
        if step.get("stepType") == "LOOP_CONTROLLER" and step.get("enable")
    )
    for child in data["scenarioStepList"]:
        if child.get("parentId") == loop_step["id"] and child.get("stepType") == "API":
            blob = json.loads(data["scenarioStepBlobMap"][str(child["id"])])
            break
    if not blob:
        raise StepError("Missing credit-offer/status polling step")

    for attempt in range(1, 101):
        request_spec = {
            "method": "GET",
            "url": BASE_URL + blob["path"],
            "path": blob["path"],
            "headers": enabled_headers(blob, variables),
            "params": enabled_query(blob, variables),
            "json_body": None,
        }
        response = send_request(request_spec)
        payload = expect_business_ok(response, f"poll credit offer status #{attempt}")
        status = str((payload.get("data") or {}).get("status") or "").strip()
        steps.append({"step": "poll credit offer status", "attempt": attempt, "status": status})
        print(f"[POLL] credit_offer_status attempt={attempt} status={status}", flush=True)
        variables["credit_offer_status"] = status
        variables["poll_count"] = str(attempt)
        if status == "SUBMITTED":
            return payload
        time.sleep(3)
    raise StepError(f"credit_offer_status did not reach SUBMITTED, last={variables.get('credit_offer_status')}")


def set_webhook_common_vars(variables):
    preferred_currency = variables.get("preferredCurrency") or "USD"
    variables["eventId"] = str(uuid.uuid4())
    variables["datetime_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    variables["lastUpdatedOn"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variables["chargeBases"] = "Fixed" if preferred_currency == "CNY" else "Float"


def find_unresolved_values(value, path="$"):
    unresolved = []
    if isinstance(value, dict):
        for key, item in value.items():
            unresolved.extend(find_unresolved_values(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            unresolved.extend(find_unresolved_values(item, f"{path}[{index}]"))
    elif isinstance(value, str) and ("${" in value or value == "@email"):
        unresolved.append({"path": path, "value": value})
    return unresolved


def validate_webhook_request(sort_no, request_spec, variables, seen_event_ids):
    body = request_spec["json_body"]
    data = body.get("data") or {}
    details = data.get("details") or {}
    event_id = data.get("eventId")
    expected_event_type = WEBHOOK_EVENT_TYPES[sort_no]

    checks = {
        "event_type": data.get("eventType") == expected_event_type,
        "event_id_present": bool(event_id),
        "event_id_unique": bool(event_id) and event_id not in seen_event_ids,
        "merchant_id": details.get("merchantId") == variables.get("merchantId"),
        "no_unresolved_variables": not find_unresolved_values(body),
    }

    try:
        uuid.UUID(str(event_id))
        checks["event_id_uuid"] = True
    except Exception:
        checks["event_id_uuid"] = False

    if sort_no == 26:
        account_ids = details.get("dpuMerchantAccountId") or []
        actual_account_id = (account_ids[0] or {}).get("MerchantAccountId") if account_ids else None
        credit = details.get("credit") or {}
        credit_limit = credit.get("creditLimit") or {}
        checks.update(
            {
                "sp_merchant_account_id": actual_account_id == variables.get("dpuMerchantAccountId"),
                "limit_application_id": details.get("dpuLimitApplicationId") == variables.get("dpuLimitApplicationId"),
                "failure_reason_null": "failureReason" in details and details.get("failureReason") is None,
                "lender_credit_id": details.get("lenderCreditId") == variables.get("lenderCreditId"),
                "lender_loan_id": details.get("lenderLoanId") == variables.get("lenderLoanId"),
                "lender_repayment_scheduled": details.get("lenderRepaymentScheduled")
                == variables.get("lenderRepaymentScheduled"),
                "lender_repayment_id": details.get("lenderRepaymentId") == variables.get("lenderRepaymentId"),
                "original_request_id_dynamic": str(details.get("originalRequestId") or "").startswith("req_")
                and details.get("originalRequestId") != "req_EFAL17621784619057169",
                "underwritten_amount": str(
                    credit_limit.get("underwrittenAmount", {}).get("amount")
                )
                == str(variables.get("underwrittenAmount")),
                "available_limit_zero": str((credit_limit.get("availableLimit") or {}).get("amount")) in {"0", "0.0", "0.00"},
                "signed_limit_zero": str((credit_limit.get("signedLimit") or {}).get("amount")) in {"0", "0.0", "0.00"},
                "watermark_zero": str((credit_limit.get("watermark") or {}).get("amount")) in {"0", "0.0", "0.00"},
                "esign_pending": credit.get("eSign") == "PENDING",
                "currency": credit_limit.get("currency") == variables.get("preferredCurrency"),
            }
        )
    elif sort_no == 27:
        offer = details.get("offer") or {}
        approved_limit = offer.get("approvedLimit") or {}
        checks.update(
            {
                "application_id": details.get("dpuApplicationId") == variables.get("dpuApplicationId"),
                "lender_approved_offer_id": details.get("lenderApprovedOfferId")
                == variables.get("lenderApprovedOfferId"),
                "original_request_id_dynamic": str(details.get("originalRequestId") or "").startswith("req_")
                and details.get("originalRequestId") != "req_1111113579",
                "approved_amount": str(approved_limit.get("amount")) == str(variables.get("approvedAmount")),
                "currency": approved_limit.get("currency") == variables.get("preferredCurrency"),
            }
        )
    elif sort_no in (28, 29):
        expected_result = "PROCESSING" if sort_no == 28 else "SUCCESS"
        checks.update(
            {
                "merchant_account_id": details.get("merchantAccountId") == variables.get("dpuMerchantAccountId"),
                "lender_approved_offer_id": details.get("lenderApprovedOfferId")
                == variables.get("lenderApprovedOfferId"),
                "result": details.get("result") == expected_result,
            }
        )
    elif sort_no == 30:
        signed_limit = details.get("signedLimit") or {}
        checks.update(
            {
                "lender_approved_offer_id": details.get("lenderApprovedOfferId")
                == variables.get("lenderApprovedOfferId"),
                "signed_amount": str(signed_limit.get("amount")) == str(variables.get("signedAmount")),
                "currency": signed_limit.get("currency") == variables.get("preferredCurrency"),
                "result": details.get("result") == "SUCCESS",
            }
        )

    if event_id:
        seen_event_ids.add(event_id)

    monitor = {
        "step": sort_no,
        "path": request_spec["path"],
        "eventType": data.get("eventType"),
        "eventId": event_id,
        "originalRequestId": details.get("originalRequestId"),
        "checks": checks,
        "unresolved_values": find_unresolved_values(body),
        "actual_body": body,
    }
    failed = [name for name, ok in checks.items() if not ok]
    print(
        f"[ASSERT] webhook step {sort_no} {data.get('eventType')} checks="
        f"{json.dumps(checks, ensure_ascii=False)}",
        flush=True,
    )
    if failed:
        raise StepError(f"webhook step {sort_no} request body check failed: {failed}")
    return monitor


def find_common_child(blob):
    return next((child for child in blob.get("children", []) if child.get("polymorphicName") == "MsCommonElement"), {})


def has_json_path_assertion(blob, expression, expected_value):
    child = find_common_child(blob)
    for assertion in child.get("assertionConfig", {}).get("assertions", []):
        for item in (assertion.get("jsonPathAssertion") or {}).get("assertions", []):
            if item.get("enable") and item.get("expression") == expression and str(item.get("expectedValue")) == str(expected_value):
                return True
    return False


def has_http_status_script_assertion(blob):
    child = find_common_child(blob)
    processors = child.get("postProcessorConfig", {}).get("processors", [])
    for processor in processors:
        script = processor.get("script") or ""
        if "prev.getResponseCode()" in script and 'code != "200"' in script and "raise Exception" in script:
            return True
    return False


def has_debug_response_logger(blob, sort_no):
    child = find_common_child(blob)
    processors = child.get("postProcessorConfig", {}).get("processors", [])
    for processor in processors:
        script = processor.get("script") or ""
        if "[scenario_1][step " in script and "responseCode" in script and "responseBody" in script:
            return True
    return False


def validate_scene_assertions(data):
    missing = []
    for sort_no in sorted(BUSINESS_ASSERTION_STEPS):
        blob = get_blob(data, sort_no)
        if not has_json_path_assertion(blob, "$.code", "200"):
            missing.append({"step": sort_no, "missing": "$.code == 200"})
        if not has_debug_response_logger(blob, sort_no):
            missing.append({"step": sort_no, "missing": "debug response logger"})

    for sort_no in sorted(HTTP_STATUS_SCRIPT_ASSERTION_STEPS):
        blob = get_blob(data, sort_no)
        if not has_http_status_script_assertion(blob):
            missing.append({"step": sort_no, "missing": "HTTP 200 script assertion"})
        if not has_debug_response_logger(blob, sort_no):
            missing.append({"step": sort_no, "missing": "debug response logger"})

    for sort_no in sorted(WEBHOOK_ASSERTION_STEPS):
        blob = get_blob(data, sort_no)
        if not has_json_path_assertion(blob, "$.data", "{}"):
            missing.append({"step": sort_no, "missing": "$.data == {}"})
        if not has_debug_response_logger(blob, sort_no):
            missing.append({"step": sort_no, "missing": "debug response logger"})

    loop_step = next(
        step
        for step in data["scenarioStepList"]
        if step.get("stepType") == "LOOP_CONTROLLER" and step.get("enable")
    )
    poll_child = next(
        (
            child
            for child in data["scenarioStepList"]
            if child.get("parentId") == loop_step["id"] and child.get("stepType") == "API"
        ),
        None,
    )
    if poll_child:
        poll_blob = json.loads(data["scenarioStepBlobMap"][str(poll_child["id"])])
        if not has_json_path_assertion(poll_blob, "$.code", "200"):
            missing.append({"step": "22.1", "missing": "$.code == 200"})
        if not has_http_status_script_assertion(poll_blob):
            missing.append({"step": "22.1", "missing": "HTTP 200 script assertion"})

    if missing:
        raise StepError(f"scenario assertion check failed: {missing}")
    print(
        "[ASSERT] scenario_1.ms assertion structure check passed "
        f"(business={len(BUSINESS_ASSERTION_STEPS)}, "
        f"httpScript={len(HTTP_STATUS_SCRIPT_ASSERTION_STEPS)}, "
        f"webhook={len(WEBHOOK_ASSERTION_STEPS)})",
        flush=True,
    )


def parse_response_payload(response):
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:1000]}


def diagnose_webhook_failure(sort_no, variables, monitor, response):
    log_section(f"webhook step {sort_no} diagnostics")
    payload = parse_response_payload(response)
    print(f"[DIAG] http_status={response.status_code}", flush=True)
    print(f"[DIAG] response_payload={json.dumps(payload, ensure_ascii=False)}", flush=True)
    trace_id = payload.get("traceId") if isinstance(payload, dict) else None
    if trace_id:
        print(f"[DIAG] traceId={trace_id}", flush=True)
    log_variables("webhook variables", variables)
    if monitor:
        print(
            f"[DIAG] webhook_request_body={json.dumps(monitor.get('actual_body'), ensure_ascii=False)}",
            flush=True,
        )

    merchant_id = variables.get("merchantId")
    if not merchant_id:
        print("[DIAG] merchantId is empty; skip DB diagnostics", flush=True)
        return

    safe_db_fetchall(
        "dpu_users by phone",
        "SELECT phone_number, merchant_id, COALESCE(prefer_finance_product_currency, 'USD'), created_at "
        "FROM dpu_users WHERE phone_number=%s ORDER BY created_at DESC LIMIT 3",
        (variables.get("phone"),),
    )
    safe_db_fetchall(
        "dpu_limit_application by merchant",
        "SELECT limit_application_unique_id, merchant_id, created_at "
        "FROM dpu_limit_application WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 5",
        (merchant_id,),
    )
    safe_db_fetchall(
        "dpu_auth_token active SP by merchant",
        "SELECT authorization_id, authorization_party, status, created_at "
        "FROM dpu_auth_token WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 5",
        (merchant_id,),
    )
    safe_db_fetchall(
        "recent dpu_lender_event by merchant",
        "SELECT id, event_type, received_at, result "
        "FROM dpu_lender_event WHERE merchant_id=%s ORDER BY received_at DESC LIMIT 10",
        (merchant_id,),
    )
    if sort_no == 26:
        safe_db_fetchall(
            "current webhook event row",
            "SELECT id, event_type, received_at, result "
            "FROM dpu_lender_event WHERE id=%s LIMIT 1",
            (variables.get("eventId"),),
        )
        safe_db_fetchall(
            "underwritten event count for limit application",
            "SELECT COUNT(*) FROM dpu_lender_event WHERE merchant_id=%s AND event_type=%s "
            "AND (JSON_UNQUOTE(JSON_EXTRACT(event_data, '$.dpuLimitApplicationId'))=%s "
            "OR JSON_UNQUOTE(JSON_EXTRACT(event_data, '$.details.dpuLimitApplicationId'))=%s)",
            (
                merchant_id,
                "underwrittenLimit.completed",
                variables.get("dpuLimitApplicationId"),
                variables.get("dpuLimitApplicationId"),
            ),
        )


def send_webhook(data, sort_no, variables, request_body_monitor, seen_event_ids):
    set_webhook_common_vars(variables)
    if sort_no == 26:
        variables["underwrittenOriginalRequestId"] = "req_" + variables["eventId"].replace("-", "")
        suffix = str(variables.get("dpuLimitApplicationId") or variables["eventId"].replace("-", ""))
        variables["lenderCreditId"] = "lcredit_" + suffix
        variables["lenderLoanId"] = "lloan_" + suffix
        variables["lenderRepaymentScheduled"] = "lrs_" + suffix
        variables["lenderRepaymentId"] = "lrepay_" + suffix
    elif sort_no == 27:
        variables["approvedOriginalRequestId"] = "req_" + variables["eventId"].replace("-", "")
    log_variables(f"webhook step {sort_no} variables before request", variables)
    request_spec = build_request(data, sort_no, variables)
    monitor = validate_webhook_request(sort_no, request_spec, variables, seen_event_ids)
    response = send_request(request_spec)
    monitor["response_status_code"] = response.status_code
    monitor["response_body"] = response.text[:1000]
    request_body_monitor.append(monitor)
    if response.status_code != 200:
        diagnose_webhook_failure(sort_no, variables, monitor, response)
    return expect_webhook_ok(response, f"webhook step {sort_no}")


def run_scenario_1():
    data = load_scenario()
    validate_scene_assertions(data)
    phone = gen_phone()
    log_section("scenario_1 direct reg run")
    print(f"[RUN] base_url={BASE_URL}", flush=True)
    print(f"[RUN] phone={phone}", flush=True)
    variables = {
        "phone": phone,
        "phoneNumber": phone,
        "email": f"{phone}@163.com",
        "approvedAmount": "500000",
        "signedAmount": "500000",
        "underwrittenAmount": "500000",
        "director1_id": str(uuid.uuid4()),
        "director1_front_doc_name": "20251123-190026.jpg",
        "director1_back_doc_name": "20251123-190026.jpg",
        "director1_front_file_url": "uploads/default/default/default/file_20260402062831_fc58bdd81df3.jpg",
        "director1_back_file_url": "uploads/default/default/default/file_20260402063050_c40c747f1286.jpg",
    }
    steps = []
    file_scan_results = []
    request_body_monitor = []
    seen_event_ids = set()
    RUN_CONTEXT.clear()
    RUN_CONTEXT.update(
        {
            "steps": steps,
            "variables": variables,
            "file_scan_results": file_scan_results,
            "request_body_monitor": request_body_monitor,
            "last_step": None,
        }
    )
    log_variables("initial variables", variables)

    def record(name, extra=None):
        payload = {"step": name}
        if extra:
            payload.update(extra)
        steps.append(payload)
        RUN_CONTEXT["last_step"] = payload
        print(f"[OK] {name}", flush=True)

    expect_business_ok(api_request(data, 4, variables), "step 4 send registration sms")
    variables["verificationCode"] = fetch_sms_code(phone)
    record("step 4 send registration sms", {"phone": phone, "verificationCode": variables["verificationCode"]})

    expect_business_ok(api_request(data, 5, variables), "step 5 validate sms code")
    record("step 5 validate sms code")

    signup_payload = expect_business_ok(api_request(data, 6, variables), "step 6 signup")
    variables["token"] = signup_payload["data"]["token"]
    record("step 6 signup", {"token_prefix": variables["token"][:12]})

    variables["state"] = str(uuid.uuid4())
    expect_business_ok(api_request(data, 7, variables), "step 7 generate sp auth url")
    record("step 7 generate sp auth url", {"state": variables["state"]})

    variables["selling_partner_id"] = gen_selling_partner_id()
    expect_http_ok(api_request(data, 8, variables), "step 8 sp auth")
    record("step 8 sp auth", {"selling_partner_id": variables["selling_partner_id"]})

    offer_row = wait_fetchone(
        "SELECT idempotency_key, platform_offer_id FROM dpu_manual_offer "
        "WHERE platform_seller_id=%s ORDER BY created_at DESC LIMIT 1",
        (variables["selling_partner_id"],),
        "dpu_manual_offer after SP auth",
    )
    variables["idempotency_key"] = offer_row[0]
    variables["platform_offer_id"] = offer_row[1]
    variables["platformOfferId"] = offer_row[1]
    log_variables(
        "offer variables after SP auth",
        variables,
        ("selling_partner_id", "idempotency_key", "platform_offer_id", "platformOfferId"),
    )

    expect_business_ok(api_request(data, 9, variables), "step 9 sp updateOffer")
    record("step 9 sp updateOffer", {"platform_offer_id": variables["platform_offer_id"]})

    expect_http_ok(api_request(data, 10, variables), "step 10 3PL redirect GET")
    record("step 10 3PL redirect GET")

    expect_business_ok(api_request(data, 11, variables), "step 11 3PL redirect POST")
    record("step 11 3PL redirect POST")

    for sort_no in range(12, 23):
        if sort_no in (14, 15):
            payload = expect_business_ok(api_request(data, sort_no, variables), f"step {sort_no} file scan result")
            scan_data = payload.get("data") or {}
            scan_result = {
                "label": "director1_front" if sort_no == 14 else "director1_back",
                "file_url": variables["director1_front_file_url"] if sort_no == 14 else variables["director1_back_file_url"],
                "scan_status": scan_data.get("scanStatus"),
                "file_scan_status_count": len(scan_data.get("fileScanStatusDTOs") or []),
            }
            file_scan_results.append(scan_result)
            record(f"step {sort_no} file scan result", scan_result)
            continue
        expect_business_ok(api_request(data, sort_no, variables), f"step {sort_no}")
        record(f"step {sort_no}")
        if sort_no == 16:
            repair_result = mark_virus_scan_ready(variables)
            record("VIRUS_SCAN dependency ready", repair_result)

    poll_credit_offer_status(data, variables, steps)
    record("credit offer reached SUBMITTED", {"attempts": variables["poll_count"]})

    merchant_row = wait_fetchone(
        "SELECT merchant_id, COALESCE(prefer_finance_product_currency, 'USD') "
        "FROM dpu_users WHERE phone_number=%s ORDER BY created_at DESC LIMIT 1",
        (phone,),
        "merchant_id",
    )
    variables["merchantId"] = merchant_row[0]
    variables["preferredCurrency"] = merchant_row[1] or "USD"
    log_variables("merchant variables", variables, ("phone", "merchantId", "preferredCurrency"))

    limit_row = wait_fetchone(
        "SELECT limit_application_unique_id FROM dpu_limit_application "
        "WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (variables["merchantId"],),
        "dpu_limit_application",
    )
    auth_row = wait_fetchone(
        "SELECT authorization_id FROM dpu_auth_token "
        "WHERE merchant_id=%s AND authorization_party='SP' AND status='ACTIVE' "
        "AND authorization_id IS NOT NULL ORDER BY created_at DESC LIMIT 1",
        (variables["merchantId"],),
        "dpu_auth_token.authorization_id",
    )
    variables["dpuLimitApplicationId"] = limit_row[0]
    variables["dpuMerchantAccountId"] = auth_row[0]
    log_variables(
        "underwritten prerequisite variables",
        variables,
        ("merchantId", "preferredCurrency", "dpuLimitApplicationId", "dpuMerchantAccountId"),
    )

    existing_underwritten = wait_lender_event_count(
        variables["merchantId"],
        "underwrittenLimit.completed",
        "dpuLimitApplicationId",
        variables["dpuLimitApplicationId"],
        timeout=12,
        interval=2,
    )
    underwritten_step = next(
        (step for step in data["scenarioStepList"] if step.get("name") == "underwritten" and step.get("parentId") is None),
        None,
    )
    if underwritten_step and not underwritten_step.get("enable", True):
        request_body_monitor.append(
            {
                "step": underwritten_step.get("sort"),
                "path": "/dpu-openapi/webhook-notifications",
                "eventType": "underwrittenLimit.completed",
                "status": "DISABLED_AUTO_GENERATED_EVENT",
                "reason": "manual underwritten webhook is disabled because reg creates underwrittenLimit.completed during the scheduled tasks",
                "checks": {
                    "existing_underwritten_event_count": existing_underwritten,
                    "skip_duplicate_underwritten": True,
                },
            }
        )
        record("underwritten webhook disabled", {"existing_event_count": existing_underwritten})
    elif existing_underwritten:
        request_body_monitor.append(
            {
                "step": underwritten_step.get("sort") if underwritten_step else None,
                "path": "/dpu-openapi/webhook-notifications",
                "eventType": "underwrittenLimit.completed",
                "status": "SKIPPED_EXISTING_EVENT",
                "reason": "underwrittenLimit.completed already exists for this dpuLimitApplicationId",
                "checks": {
                    "existing_underwritten_event_count": existing_underwritten,
                    "skip_duplicate_underwritten": True,
                },
            }
        )
        record("underwritten webhook skipped", {"existing_event_count": existing_underwritten})
    else:
        send_webhook(data, underwritten_step.get("sort") if underwritten_step else 26, variables, request_body_monitor, seen_event_ids)
        record("underwritten webhook", {"eventId": variables["eventId"]})

    application_row = wait_fetchone(
        "SELECT application_unique_id FROM dpu_application "
        "WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (variables["merchantId"],),
        "dpu_application",
    )
    variables["dpuApplicationId"] = application_row[0]
    variables["offerStartDate"] = datetime.now().strftime("%Y-%m-%d")
    variables["offerEndDate"] = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    variables["lenderApprovedOfferId"] = "lender-" + variables["dpuApplicationId"]
    log_variables(
        "approved-offer prerequisite variables",
        variables,
        ("merchantId", "dpuApplicationId", "lenderApprovedOfferId", "offerStartDate", "offerEndDate"),
    )

    existing_approved = wait_lender_event_count(
        variables["merchantId"],
        "approvedoffer.completed",
        "dpuApplicationId",
        variables["dpuApplicationId"],
        timeout=8,
        interval=2,
    )
    if existing_approved:
        request_body_monitor.append(
            {
                "step": 25,
                "path": "/dpu-openapi/webhook-notifications",
                "eventType": "approvedoffer.completed",
                "status": "SKIPPED_EXISTING_EVENT",
                "reason": "approvedoffer.completed already exists for this dpuApplicationId",
                "checks": {
                    "existing_approved_event": True,
                    "skip_duplicate_approved": True,
                },
            }
        )
        record("approved-offer webhook skipped", {"existing_event_count": existing_approved})
    else:
        send_webhook(data, 27, variables, request_body_monitor, seen_event_ids)
        record("step 27 approved-offer webhook", {"eventId": variables["eventId"]})

    credit_offer_row = wait_fetchone(
        "SELECT lender_approved_offer_id, status, approved_limit_amount, e_sign_status "
        "FROM dpu_credit_offer WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (variables["merchantId"],),
        "dpu_credit_offer",
    )
    variables["lenderApprovedOfferId"] = credit_offer_row[0]
    log_variables(
        "psp/esign prerequisite variables",
        variables,
        ("merchantId", "dpuMerchantAccountId", "lenderApprovedOfferId", "approvedAmount", "signedAmount"),
    )

    send_webhook(data, 28, variables, request_body_monitor, seen_event_ids)
    record("step 28 psp-start webhook", {"eventId": variables["eventId"]})

    send_webhook(data, 29, variables, request_body_monitor, seen_event_ids)
    record("step 29 psp-completed webhook", {"eventId": variables["eventId"]})

    send_webhook(data, 30, variables, request_body_monitor, seen_event_ids)
    record("step 30 esign webhook", {"eventId": variables["eventId"]})

    final_credit_offer_row = wait_fetchone(
        "SELECT lender_approved_offer_id, status, approved_limit_amount, e_sign_status "
        "FROM dpu_credit_offer WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (variables["merchantId"],),
        "final dpu_credit_offer",
        timeout=20,
    )
    lender_events = db_fetchone(
        "SELECT COUNT(*) FROM dpu_lender_event WHERE merchant_id=%s "
        "AND event_type IN ('underwrittenLimit.completed','approvedoffer.completed','psp.verification.started','psp.verification.completed','esign.completed')",
        (variables["merchantId"],),
    )

    return {
        "validated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenario_file": SCENARIO_PATH.as_posix(),
        "scenario_name": data["exportScenarioList"][0]["name"],
        "base_url": BASE_URL,
        "result": "PASS",
        "phone": phone,
        "merchant_id": variables["merchantId"],
        "platform_offer_id": variables["platform_offer_id"],
        "dpu_limit_application_id": variables["dpuLimitApplicationId"],
        "dpu_application_id": variables["dpuApplicationId"],
        "lender_approved_offer_id": variables["lenderApprovedOfferId"],
        "steps": steps,
        "file_scan_results": file_scan_results,
        "request_body_monitor": request_body_monitor,
        "final_credit_offer_row": final_credit_offer_row,
        "lender_event_count": lender_events[0] if lender_events else 0,
    }


def main():
    result = None
    try:
        result = run_scenario_1()
        print("[PASS] scenario_1 direct reg validation passed")
    except Exception as exc:
        result = {
            "validated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scenario_file": SCENARIO_PATH.as_posix(),
            "base_url": BASE_URL,
            "result": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "debug_context": {
                "last_step": to_jsonable(RUN_CONTEXT.get("last_step")),
                "steps": to_jsonable(RUN_CONTEXT.get("steps", [])),
                "variables": snapshot_variables(RUN_CONTEXT.get("variables", {})),
                "file_scan_results": to_jsonable(RUN_CONTEXT.get("file_scan_results", [])),
                "request_body_monitor": to_jsonable(RUN_CONTEXT.get("request_body_monitor", [])),
            },
        }
        print(f"[FAIL] {exc}")
        raise
    finally:
        if result is not None:
            OUTPUT_PATH.write_text(json.dumps(to_jsonable(result), ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[RESULT] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
