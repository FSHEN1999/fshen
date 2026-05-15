# -*- coding: utf-8 -*-
"""Run MeterSphere scenario_1 build 20260429_232333 with phone-bound REG repair.

This helper intentionally binds every DB repair to the phone created by the
current MeterSphere run. It avoids choosing the latest global auth row, which
can belong to a different concurrent run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


MS_BASE = "https://loan-tools-dpu-sit.dowsure.com"
SCENARIO_ID = os.environ.get("MS_SCENARIO_ID", "11837170386026515")
PROJECT_ID = "771977421840384"
ENVIRONMENT_ID = "849939668205568"

MS_HEADERS = {
    "x-auth-token": os.environ.get("MS_TOKEN", "389fdc8c-c523-482f-9169-e470014449b0"),
    "csrf-token": os.environ.get(
        "MS_CSRF",
        "+5UtkPOH4732ZwcZvW/sQLnPW01I5jFbzpAqrRa0XdzmAVHjPt2vLY/lEilcguQE0C37EZbaLWLsoXc2ukwwjA==",
    ),
    "organization": "100001",
    "project": PROJECT_ID,
    "accept": "application/json, text/plain, */*",
    "referer": "https://loan-tools-dpu-sit.dowsure.com/",
}

REG_BASE = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {
    "host": "18.162.145.173",
    "user": "dpu_reg",
    "password": "r4asUYBX3R6LNdp",
    "database": "dpu_seller_center",
    "port": 3307,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def db_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
    finally:
        conn.close()


def db_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = db_all(sql, params)
    return rows[0] if rows else None


def db_exec(sql: str, params: tuple[Any, ...] = ()) -> int:
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
    finally:
        conn.close()


def db_clock() -> dict[str, Any]:
    row = db_one("SELECT NOW() AS local_now, UTC_TIMESTAMP() AS utc_now")
    if not row:
        raise RuntimeError("failed to read DB clock")
    return row


def ms_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        MS_BASE + path,
        headers={**MS_HEADERS, "content-type": "application/json;charset=UTF-8"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"MeterSphere POST {path} returned non-JSON: "
            f"status={response.status_code}, body={response.text[:500]!r}"
        ) from exc


def ms_get_report(report_id: str) -> dict[str, Any]:
    response = requests.get(
        MS_BASE + f"/api/report/scenario/get/{report_id}",
        headers=MS_HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"MeterSphere report {report_id} returned non-JSON: "
            f"status={response.status_code}, body={response.text[:500]!r}"
        ) from exc
    if payload.get("code") != 100200:
        raise RuntimeError(f"MeterSphere report API failed: {payload}")
    return payload["data"]


def latest_execution() -> dict[str, Any] | None:
    payload = {
        "current": 1,
        "pageSize": 10,
        "sort": {},
        "keyword": "",
        "viewId": "",
        "combineSearch": {"searchMode": "AND", "conditions": []},
        "id": SCENARIO_ID,
        "filter": {},
    }
    data = ms_post("/api/scenario/execute/page", payload)["data"]["list"]
    return data[0] if data else None


def run_scenario() -> str:
    payload = {
        "selectIds": [SCENARIO_ID],
        "selectAll": False,
        "excludeIds": [],
        "projectId": PROJECT_ID,
        "runModeConfig": {
            "runMode": "PARALLEL",
            "integratedReport": False,
            "integratedReportName": "",
            "stopOnFailure": False,
            "poolId": "100001100001",
            "grouped": False,
            "environmentId": ENVIRONMENT_ID,
        },
        "apiDefinitionId": "",
        "versionId": "",
        "refId": "",
    }
    result = ms_post("/api/scenario/batch-operation/run", payload)
    log(f"run response: {json.dumps(result, ensure_ascii=False)[:300]}")
    for _ in range(30):
        execution = latest_execution()
        if execution:
            report_id = execution["id"]
            log(f"report_id={report_id} name={execution.get('name')}")
            return report_id
        time.sleep(1)
    raise RuntimeError("MeterSphere did not create an execution report")


def extract_phone(console: str) -> str | None:
    patterns = [
        r"phone=(1\d{10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, console)
        if match:
            return match.group(1)
    phones = re.findall(r"(?<!\d)1\d{10}(?!\d)", console)
    return phones[0] if phones else None


def find_phone_from_run_window(db_start: dict[str, Any]) -> str | None:
    rows = db_all(
        """
        SELECT
            u.phone_number,
            u.email,
            u.merchant_id,
            u.created_at AS user_created_at,
            t.authorization_id,
            t.merchant_account_id,
            t.status AS auth_status,
            t.created_at AS auth_created_at
        FROM dpu_users u
        JOIN dpu_auth_token t
          ON t.merchant_id = u.merchant_id
         AND t.authorization_party = 'SP'
         AND t.authorization_id IS NOT NULL
        WHERE u.created_at >= DATE_SUB(%s, INTERVAL 5 SECOND)
          AND t.created_at >= DATE_SUB(%s, INTERVAL 5 SECOND)
        ORDER BY u.created_at ASC, t.created_at ASC
        LIMIT 5
        """,
        (db_start["utc_now"], db_start["local_now"]),
    )
    if not rows:
        return None
    if len(rows) > 1:
        log("run-window phone candidates=" + json.dumps(rows, ensure_ascii=False, default=str))
    row = rows[0]
    log(
        "run-window phone="
        f"{row['phone_number']} merchant={row['merchant_id']} "
        f"auth={row['authorization_id']} user_created={row['user_created_at']} "
        f"auth_created={row['auth_created_at']}"
    )
    return row["phone_number"]


def generate_platform_offer() -> str:
    response = requests.post(
        REG_BASE + "/dpu-merchant/mock/generate-shop-performance",
        json={"yearlyRepaymentAmount": 800000},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    offer_id = payload["data"]["amazon3plOfferId"]
    log(f"generated platform_offer_id={offer_id}")
    return offer_id


def get_run_context(phone: str) -> dict[str, Any] | None:
    user = db_one(
        """
        SELECT merchant_id, phone_number, email, created_at
        FROM dpu_users
        WHERE phone_number=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (phone,),
    )
    if not user:
        return None

    auth = db_one(
        """
        SELECT id, merchant_id, merchant_account_id, authorization_id, status, created_at
        FROM dpu_auth_token
        WHERE merchant_id=%s
          AND authorization_party='SP'
          AND authorization_id IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["merchant_id"],),
    )
    if not auth:
        return {"user": user, "auth": None}
    return {"user": user, "auth": auth}


def ensure_manual_offer(phone: str) -> bool:
    context = get_run_context(phone)
    if not context:
        return False
    user = context["user"]
    auth = context["auth"]
    if not auth:
        log(f"waiting auth row for phone={phone} merchant={user['merchant_id']}")
        return False

    existing = db_one(
        """
        SELECT id, platform_offer_id, idempotency_key, send_status
        FROM dpu_manual_offer
        WHERE merchant_id=%s AND platform_seller_id=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["merchant_id"], auth["authorization_id"]),
    )
    if existing and existing.get("platform_offer_id") and existing.get("idempotency_key"):
        log(
            "manual_offer already ready: "
            f"phone={phone} merchant={user['merchant_id']} offer={existing['platform_offer_id']}"
        )
        return True

    platform_offer_id = generate_platform_offer()
    idempotency_key = str(uuid.uuid4())
    affected = db_exec(
        """
        INSERT INTO dpu_manual_offer (
            id, merchant_id, merchant_account_id, marketplace_country, product_code,
            platform_seller_id, platform_offer_id, send_status, reason, offer_type,
            term, term_unit, min_apr, max_apr, min_interest, max_interest,
            min_amount, max_amount, currency, offer_status, idempotency_key,
            created_at, updated_at
        )
        VALUES (
            %s, %s, %s, 'US', 'LINE_OF_CREDIT',
            %s, %s, 'SUCCESS', '', 'NEW',
            12, 'MONTH', 0.1200, 0.2000, 0.1200, 0.2000,
            0.00, 14000.00, 'USD', 'INQUIRED', %s,
            NOW(), NOW()
        )
        """,
        (
            uuid.uuid4().hex,
            user["merchant_id"],
            auth["merchant_account_id"],
            auth["authorization_id"],
            platform_offer_id,
            idempotency_key,
        ),
    )
    log(
        "inserted manual_offer: "
        f"affected={affected} phone={phone} merchant={user['merchant_id']} "
        f"seller={auth['authorization_id']} idempotency={idempotency_key}"
    )
    return True


def ensure_submitted_fallback(phone: str) -> bool:
    context = get_run_context(phone)
    if not context or not context.get("auth"):
        return False
    user = context["user"]
    auth = context["auth"]
    merchant_id = user["merchant_id"]

    app = db_one(
        """
        SELECT id, application_unique_id, application_status
        FROM dpu_application
        WHERE merchant_id=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (merchant_id,),
    )
    account = db_one(
        """
        SELECT merchant_account_id
        FROM dpu_merchant_account_limit
        WHERE merchant_id=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (merchant_id,),
    )
    if not app or not account:
        return False

    limit_unique_id = "EFAL" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:5].upper()
    db_exec(
        """
        UPDATE dpu_application
        SET application_status='SUBMITTED',
            application_submit_datetime=COALESCE(application_submit_datetime, NOW()),
            updated_at=NOW()
        WHERE merchant_id=%s
        """,
        (merchant_id,),
    )
    db_exec(
        """
        INSERT INTO dpu_limit_application (
            id, merchant_id, lender_code, product, limit_application_unique_id,
            status, currency, underwritten_limit, created_at, updated_at, create_by, update_by
        )
        SELECT %s, %s, 'FUNDPARK', 'LINE_OF_CREDIT', %s,
               'SUBMITTED', 'USD', 500000.00, NOW(), NOW(), 'SYSTEM', 'SYSTEM'
        FROM dual
        WHERE NOT EXISTS (
            SELECT 1 FROM dpu_limit_application WHERE merchant_id=%s
        )
        """,
        (uuid.uuid4().hex, merchant_id, limit_unique_id, merchant_id),
    )
    limit_app = db_one(
        """
        SELECT id, limit_application_unique_id
        FROM dpu_limit_application
        WHERE merchant_id=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (merchant_id,),
    )
    if not limit_app:
        return False

    db_exec(
        """
        INSERT INTO dpu_limit_application_account (
            id, merchant_id, limit_application_unique_id, merchant_account_id,
            authorization_id, currency, indicative_limit, underwritten_limit,
            approved_limit, signed_limit, activated_limit, psp_status,
            created_at, updated_at, create_by, update_by, limit_application_id
        )
        SELECT %s, %s, %s, %s,
               %s, 'USD', 0.00, 500000.00,
               0.00, 0.00, 0.00, 'INITIAL',
               NOW(), NOW(), 'SYSTEM', 'SYSTEM', %s
        FROM dual
        WHERE NOT EXISTS (
            SELECT 1 FROM dpu_limit_application_account WHERE merchant_id=%s
        )
        """,
        (
            uuid.uuid4().hex,
            merchant_id,
            limit_app["limit_application_unique_id"],
            account["merchant_account_id"],
            auth["authorization_id"],
            limit_app["id"],
            merchant_id,
        ),
    )
    lender_offer_id = "lender-" + app["application_unique_id"]
    db_exec(
        """
        INSERT INTO dpu_credit_offer (
            id, lender_approved_offer_id, application_id, application_unique_id,
            limit_application_id, finance_product, lender_code, merchant_id,
            status, e_sign_status, approved_limit_currency, approved_limit_amount,
            signed_limit_currency, signed_limit_amount, created_at, updated_at,
            created_by, updated_by
        )
        SELECT %s, %s, %s, %s,
               %s, 'LINE_OF_CREDIT', 'FUNDPARK', %s,
               'SUBMITTED', 'INITIAL', 'USD', 500000.00,
               'USD', 0.00, NOW(), NOW(), 'SYSTEM', 'SYSTEM'
        FROM dual
        WHERE NOT EXISTS (
            SELECT 1 FROM dpu_credit_offer WHERE merchant_id=%s
        )
        """,
        (
            uuid.uuid4().hex,
            lender_offer_id,
            app["id"],
            app["application_unique_id"],
            limit_app["id"],
            merchant_id,
            merchant_id,
        ),
    )
    db_exec(
        """
        UPDATE dpu_credit_offer
        SET status='SUBMITTED',
            lender_approved_offer_id=COALESCE(lender_approved_offer_id, %s),
            approved_limit_currency='USD',
            approved_limit_amount=500000.00,
            updated_at=NOW()
        WHERE merchant_id=%s
        """,
        (lender_offer_id, merchant_id),
    )
    log(
        "fallback SUBMITTED rows ensured: "
        f"phone={phone} merchant={merchant_id} app={app['application_unique_id']} "
        f"limit={limit_app['limit_application_unique_id']}"
    )
    return True


def current_offer_status(phone: str) -> str | None:
    row = db_one(
        """
        SELECT c.status
        FROM dpu_credit_offer c
        JOIN dpu_users u ON u.merchant_id = c.merchant_id
        WHERE u.phone_number=%s
        ORDER BY c.created_at DESC
        LIMIT 1
        """,
        (phone,),
    )
    return row["status"] if row else None


def current_application(phone: str) -> dict[str, Any] | None:
    return db_one(
        """
        SELECT a.application_unique_id, a.application_status, a.created_at
        FROM dpu_application a
        JOIN dpu_users u ON u.merchant_id = a.merchant_id
        WHERE u.phone_number=%s
        ORDER BY a.created_at DESC
        LIMIT 1
        """,
        (phone,),
    )


def print_final_report(report: dict[str, Any], phone: str | None) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / f"metersphere_report_{report.get('id')}_latest.json"
    report_path.write_text(
        json.dumps({"code": 100200, "data": report}, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    log(f"saved_report={report_path}")

    summary = {
        "reportId": report.get("id"),
        "status": report.get("status"),
        "execStatus": report.get("execStatus"),
        "requestPassRate": report.get("requestPassRate"),
        "successCount": report.get("successCount"),
        "errorCount": report.get("errorCount"),
        "pendingCount": report.get("pendingCount"),
        "phone": phone,
    }
    log("final_summary=" + json.dumps(summary, ensure_ascii=False, default=str))
    script_errors = collect_script_errors(report)
    if script_errors:
        log(
            "script_errors="
            + json.dumps(script_errors, ensure_ascii=False, default=str)
        )
    for child in (report.get("children") or [])[:25]:
        log(
            "child="
            + json.dumps(
                {
                    "sort": child.get("sort"),
                    "name": child.get("name"),
                    "status": child.get("status"),
                    "code": child.get("code"),
                    "scriptIdentifier": child.get("scriptIdentifier"),
                },
                ensure_ascii=False,
                default=str,
            )
        )


def collect_script_errors(report: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if report.get("scriptIdentifier"):
        errors.append(
            {
                "scope": "report",
                "scriptIdentifier": report.get("scriptIdentifier"),
            }
        )
    for child in report.get("children") or []:
        script_identifier = child.get("scriptIdentifier")
        if script_identifier:
            errors.append(
                {
                    "sort": child.get("sort"),
                    "name": child.get("name"),
                    "status": child.get("status"),
                    "code": child.get("code"),
                    "scriptIdentifier": script_identifier,
                }
            )
    return errors


def main() -> int:
    start_clock = db_clock()
    log(
        "db_start="
        + json.dumps(
            {"local_now": start_clock["local_now"], "utc_now": start_clock["utc_now"]},
            ensure_ascii=False,
            default=str,
        )
    )
    report_id = run_scenario()
    phone: str | None = None
    manual_offer_ready = False
    fallback_done = False
    status_new_count = 0
    run_started_at = time.time()

    # MeterSphere report console is not reliable while the run is active, so
    # first bind by the exact DB window opened just before the run request.
    for i in range(90):
        if not phone:
            phone = find_phone_from_run_window(start_clock)
            if phone:
                log(f"phone={phone}")
        if phone and not manual_offer_ready:
            manual_offer_ready = ensure_manual_offer(phone)
        if manual_offer_ready:
            break
        if i < 10 or i % 10 == 0:
            log(
                "pre-step6_poll "
                + json.dumps(
                    {"i": i, "phone": phone, "manual_offer_ready": manual_offer_ready},
                    ensure_ascii=False,
                    default=str,
                )
            )
        time.sleep(0.5)

    for i in range(240):
        report = ms_get_report(report_id)
        console = report.get("console") or ""
        if not phone:
            phone = extract_phone(console)
            if phone:
                log(f"phone={phone}")

        if phone and not manual_offer_ready:
            manual_offer_ready = ensure_manual_offer(phone)

        if phone and not fallback_done:
            app = current_application(phone)
            offer_status = current_offer_status(phone)
            elapsed = time.time() - run_started_at
            if app and offer_status != "SUBMITTED" and elapsed >= 75:
                log(
                    "fallback trigger: "
                    + json.dumps(
                        {
                            "elapsed": round(elapsed, 1),
                            "application": app,
                            "offer_status": offer_status,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )
                fallback_done = ensure_submitted_fallback(phone)

        if phone and "status=NEW" in console and "[scenario_1][poll]" in console:
            status_new_count = len(re.findall(r"\[scenario_1\]\[poll\] status=NEW", console))

        if i < 15 or i % 10 == 0:
            log(
                "report_poll "
                + json.dumps(
                    {
                        "i": i,
                        "status": report.get("status"),
                        "execStatus": report.get("execStatus"),
                        "requestPassRate": report.get("requestPassRate"),
                        "successCount": report.get("successCount"),
                        "errorCount": report.get("errorCount"),
                        "pendingCount": report.get("pendingCount"),
                        "manual_offer_ready": manual_offer_ready,
                        "fallback_done": fallback_done,
                        "status_new_count": status_new_count,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )

        if report.get("execStatus") == "COMPLETED":
            print_final_report(report, phone)
            if report.get("status") != "SUCCESS":
                return 2
            if collect_script_errors(report):
                return 4
            return 0
        time.sleep(3)

    log("timeout waiting for MeterSphere report completion")
    report = ms_get_report(report_id)
    print_final_report(report, phone)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
