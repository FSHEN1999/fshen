from __future__ import annotations

import copy
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pymysql
import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCENARIO = next(ROOT.glob(os.environ.get("SCENARIO_SOURCE_GLOB", "*/scenario_fp_usd_2k.ms")))
OUTPUT_DIR = ROOT / "output"
TMP_DIR = ROOT / "tmp"

MS_BASE = "https://loan-tools-dpu-sit.dowsure.com"
PROJECT_ID = "771977421840384"
ENVIRONMENT_ID = "849939668205568"
MODULE_ID = os.environ.get("MS_MODULE_ID", "23326603039817750")
POOL_ID = os.environ.get("MS_POOL_ID", "100001100001")
BUILD = datetime.now().strftime("%Y%m%d_%H%M%S")
SCENARIO_NAME_PREFIX = os.environ.get("SCENARIO_NAME_PREFIX", "FP-USD-2K_REG_DISBURSEMENT_BUILD_")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "fp_usd_2k")
SCENARIO_NAME = f"{SCENARIO_NAME_PREFIX}{BUILD}"

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


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def build_auth_headers(token: str, csrf: str) -> dict[str, str]:
    return {
        "x-auth-token": token,
        "csrf-token": csrf,
        "organization": "100001",
        "project": PROJECT_ID,
        "accept": "application/json, text/plain, */*",
        "referer": MS_BASE + "/",
    }


def probe_headers(candidate_headers: dict[str, str]) -> bool:
    response = requests.post(
        MS_BASE + "/api/scenario/page",
        headers={**candidate_headers, "content-type": "application/json;charset=UTF-8"},
        json={
            "projectId": PROJECT_ID,
            "keyword": SCENARIO_NAME,
            "current": 1,
            "pageSize": 5,
            "sort": {},
            "moduleIds": [],
            "viewId": "",
            "combineSearch": {"searchMode": "AND", "conditions": []},
            "filter": {},
        },
        timeout=20,
        allow_redirects=False,
    )
    try:
        code = response.json().get("code")
    except Exception:
        code = None
    log(f"AUTH_PROBE status={response.status_code} code={code} loc={response.headers.get('location')}")
    return response.status_code == 200 and code == 100200


def discover_headers() -> dict[str, str]:
    candidates: list[dict[str, str]] = []
    env_token = os.environ.get("MS_TOKEN")
    env_csrf = os.environ.get("MS_CSRF")
    if env_token and env_csrf:
        candidates.append(build_auth_headers(env_token, env_csrf))
    candidates.extend(
        [
            build_auth_headers(
                "2c850cda-9743-4d41-af22-2d92abe2727a",
                "JE/ZnP0+uIIZLsYz3vXhNbnb6VRRRLcs7ToF4M0Dx3qGlCrmU3lvPqCnFsWr8zHqlHNiP1sIXzye9Domab5dmzo5yYCX/9Fv7DVo/Z4AAPk=",
            ),
            build_auth_headers(
                "389fdc8c-c523-482f-9169-e470014449b0",
                "+5UtkPOH4732ZwcZvW/sQLnPW01I5jFbzpAqrRa0XdzmAVHjPt2vLY/lEilcguQE0C37EZbaLWLsoXc2ukwwjA==",
            ),
        ]
    )

    for headers in candidates:
        if probe_headers(headers):
            return headers

    raise RuntimeError("Unable to authenticate to MeterSphere with known token candidates")


def ms_post(headers: dict[str, str], path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        MS_BASE + path,
        headers={**headers, "content-type": "application/json;charset=UTF-8"},
        json=payload,
        timeout=60,
        allow_redirects=False,
    )
    try:
        code = response.json().get("code")
    except Exception:
        code = None
    log(f"POST {path} status={response.status_code} code={code} loc={response.headers.get('location')} body={response.text[:300].replace(chr(10), ' ')}")
    response.raise_for_status()
    payload_json = response.json()
    if payload_json.get("code") != 100200:
        raise RuntimeError(f"{path} failed: {payload_json}")
    return payload_json


def ms_get(headers: dict[str, str], path: str) -> dict[str, Any]:
    response = requests.get(MS_BASE + path, headers=headers, timeout=60, allow_redirects=False)
    try:
        code = response.json().get("code")
    except Exception:
        code = None
    log(f"GET {path} status={response.status_code} code={code} loc={response.headers.get('location')} body={response.text[:300].replace(chr(10), ' ')}")
    response.raise_for_status()
    payload_json = response.json()
    if payload_json.get("code") != 100200:
        raise RuntimeError(f"{path} failed: {payload_json}")
    return payload_json


def make_import_copy() -> Path:
    source = load_json(SOURCE_SCENARIO)
    scenario_build = BUILD
    scenario_name = SCENARIO_NAME
    old_build = None
    for item in source.get("exportScenarioList", [])[0].get("scenarioConfig", {}).get("variable", {}).get("commonVariables", []):
        if item.get("key") == "sceneBuildId" and item.get("value"):
            old_build = str(item["value"])
            item["value"] = scenario_build
            break

    def replace_build(value: Any) -> Any:
        if isinstance(value, str):
            if old_build:
                return value.replace(old_build, scenario_build)
            return value
        if isinstance(value, list):
            return [replace_build(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_build(item) for key, item in value.items()}
        return value

    source = replace_build(source)
    source["exportScenarioList"][0]["name"] = scenario_name
    source["exportScenarioList"][0]["stepTotal"] = 19
    source["exportScenarioList"][0]["latest"] = True
    if source.get("scenarioStepList"):
        source["scenarioStepList"] = sorted(source["scenarioStepList"], key=lambda item: (item.get("sort") or 0, str(item.get("id"))))

    temp_path = TMP_DIR / f"scenario_{OUTPUT_PREFIX}_live_{BUILD}.ms"
    save_json(temp_path, source)
    return temp_path


def import_scenario(headers: dict[str, str], ms_path: Path) -> dict[str, Any]:
    request = {
        "projectId": PROJECT_ID,
        "moduleId": MODULE_ID,
        "coverData": False,
        "type": "MeterSphere",
    }
    with ms_path.open("rb") as handle:
        files = {
            "file": (ms_path.name, handle, "application/octet-stream"),
            "request": (None, json.dumps(request, ensure_ascii=False), "application/json"),
        }
        response = requests.post(
            MS_BASE + "/api/scenario/import",
            headers=headers,
            files=files,
            timeout=180,
            allow_redirects=False,
        )
    log(f"IMPORT status={response.status_code} body={response.text[:800].replace(chr(10), ' ')}")
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 100200:
        raise RuntimeError(f"import failed: {payload}")
    save_json(OUTPUT_DIR / f"metersphere_import_response_{OUTPUT_PREFIX}_{BUILD}.json", payload)
    return payload


def find_latest_scenario(headers: dict[str, str]) -> dict[str, Any]:
    payload = {
        "projectId": PROJECT_ID,
        "keyword": SCENARIO_NAME,
        "current": 1,
        "pageSize": 20,
        "sort": {},
        "moduleIds": [],
        "viewId": "",
        "combineSearch": {"searchMode": "AND", "conditions": []},
        "filter": {},
    }
    page = ms_post(headers, "/api/scenario/page", payload)
    items = page.get("data", {}).get("list") or []
    items = sorted(items, key=lambda item: item.get("createTime") or 0, reverse=True)
    if not items:
        raise RuntimeError("imported scenario not found on page")
    item = items[0]
    log(f"SCENARIO {item['id']} {item.get('name')} stepTotal={item.get('stepTotal')}")
    save_json(OUTPUT_DIR / f"metersphere_scenario_page_{OUTPUT_PREFIX}_{BUILD}.json", page)
    save_json(
        OUTPUT_DIR / f"metersphere_latest_import_{OUTPUT_PREFIX}_{BUILD}.json",
        {"build": BUILD, "name": SCENARIO_NAME, "scenario_id": item["id"], "item": item, "source_ms": str(ms_path_for_import)},
    )
    return item


def latest_execution(headers: dict[str, str], scenario_id: str) -> dict[str, Any] | None:
    payload = {
        "current": 1,
        "pageSize": 10,
        "sort": {},
        "keyword": "",
        "viewId": "",
        "combineSearch": {"searchMode": "AND", "conditions": []},
        "id": scenario_id,
        "filter": {},
    }
    data = ms_post(headers, "/api/scenario/execute/page", payload).get("data", {}).get("list") or []
    return data[0] if data else None


def run_scenario(headers: dict[str, str], scenario_id: str) -> str:
    previous = latest_execution(headers, scenario_id)
    previous_id = previous.get("id") if previous else None
    log(f"previous_report_id={previous_id}")
    payload = {
        "selectIds": [scenario_id],
        "selectAll": False,
        "excludeIds": [],
        "projectId": PROJECT_ID,
        "runModeConfig": {
            "runMode": "PARALLEL",
            "integratedReport": False,
            "integratedReportName": "",
            "stopOnFailure": False,
            "poolId": POOL_ID,
            "grouped": False,
            "environmentId": ENVIRONMENT_ID,
        },
        "apiDefinitionId": "",
        "versionId": "",
        "refId": "",
    }
    result = ms_post(headers, "/api/scenario/batch-operation/run", payload)
    log(f"run_response={json.dumps(result, ensure_ascii=False)[:300]}")
    for _ in range(60):
        execution = latest_execution(headers, scenario_id)
        if execution and execution.get("id") != previous_id:
            report_id = execution["id"]
            log(
                "RUN_REPORT "
                + json.dumps(
                    {
                        "report_id": report_id,
                        "name": execution.get("name"),
                        "status": execution.get("status"),
                        "execStatus": execution.get("execStatus"),
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
            return report_id
        time.sleep(1)
    raise RuntimeError("MeterSphere did not create a new execution report")


def get_report(headers: dict[str, str], report_id: str) -> dict[str, Any]:
    return ms_get(headers, f"/api/report/scenario/get/{report_id}")["data"]


def save_detail(headers: dict[str, str], report_id: str, step_id: str, label: str) -> dict[str, Any]:
    detail = ms_get(headers, f"/api/report/scenario/task-report/{report_id}/{step_id}")
    path = OUTPUT_DIR / f"api_report_scenario_task-report_{report_id}_{step_id}_{label}.json"
    save_json(path, detail)
    return detail


def collect_step_details(headers: dict[str, str], report: dict[str, Any], label: str) -> None:
    report_id = report["id"]
    for child in report.get("children") or []:
        sort = child.get("sort")
        status = child.get("status")
        if status == "SUCCESS" and int(sort or 0) < 12:
            continue
        step_id = child.get("stepId") or child.get("id")
        if not step_id:
            continue
        try:
            save_detail(headers, report_id, step_id, label)
            log(f"SAVED_DETAIL sort={sort} status={status} step_id={step_id}")
        except Exception as exc:
            log(f"detail_fetch_failed sort={sort} step_id={step_id} error={exc}")


def extract_phone(report: dict[str, Any]) -> str | None:
    text = report.get("console") or ""
    for child in report.get("children") or []:
        for key in ("console", "requestBody", "responseBody"):
            value = child.get(key)
            if value:
                text += "\n" + str(value)
    phones = re.findall(r"(?<!\d)1\d{10}(?!\d)", text)
    return phones[0] if phones else None


def inspect_step_12_detail(headers: dict[str, str], report: dict[str, Any], label: str) -> None:
    for child in report.get("children") or []:
        if child.get("sort") == 12:
            detail = save_detail(headers, report["id"], child["stepId"], label)
            body_text = json.dumps(detail, ensure_ascii=False, default=str)
            if "bankAccountNumber" in body_text:
                log("STEP12_DETAIL_CONTAINS_BANK_ACCOUNT_NUMBER")
            return


def db_verify(phone: str | None, merchant_id: str | None) -> dict[str, Any]:
    if not merchant_id and phone:
        row = db_one(
            "SELECT merchant_id FROM dpu_users WHERE phone_number=%s ORDER BY created_at DESC LIMIT 1",
            (phone,),
        )
        merchant_id = row["merchant_id"] if row else None
    if not merchant_id:
        return {"phone": phone, "merchant_id": None, "error": "merchant not extracted"}
    return {
        "phone": phone,
        "merchant_id": merchant_id,
        "users": db_all(
            "SELECT phone_number, merchant_id, email, prefer_finance_product_currency, created_at "
            "FROM dpu_users WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 3",
            (merchant_id,),
        ),
        "applications": db_all(
            "SELECT application_unique_id, application_status, created_at, updated_at "
            "FROM dpu_application WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 3",
            (merchant_id,),
        ),
        "limit_applications": db_all(
            "SELECT limit_application_unique_id, status, currency, underwritten_limit, activated_limit, available_limit, created_at, updated_at "
            "FROM dpu_limit_application WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 3",
            (merchant_id,),
        ),
        "credit_offers": db_all(
            "SELECT lender_approved_offer_id, application_unique_id, status, e_sign_status, approved_limit_amount, approved_limit_currency, "
            "signed_limit_amount, signed_limit_currency, created_at, updated_at "
            "FROM dpu_credit_offer WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 3",
            (merchant_id,),
        ),
        "drawdowns": db_all(
            "SELECT loan_id, lender_loan_id, lender_approved_offer_id, status, currency, drawdown_amount, lender_drawdown_id, created_at, updated_at "
            "FROM dpu_drawdown WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 3",
            (merchant_id,),
        ),
        "event_counts": db_all(
            "SELECT event_type, COUNT(*) cnt, MAX(received_at) latest_received_at "
            "FROM dpu_lender_event WHERE merchant_id=%s GROUP BY event_type ORDER BY event_type",
            (merchant_id,),
        ),
        "latest_events": db_all(
            "SELECT event_type, result, received_at "
            "FROM dpu_lender_event WHERE merchant_id=%s ORDER BY received_at DESC LIMIT 10",
            (merchant_id,),
        ),
    }


def main() -> int:
    global ms_path_for_import
    headers = discover_headers()
    log(f"AUTH OK build={BUILD}")

    ms_path_for_import = make_import_copy()
    log(f"IMPORT_SOURCE {ms_path_for_import}")
    import_scenario(headers, ms_path_for_import)
    scenario = find_latest_scenario(headers)

    report_id = run_scenario(headers, scenario["id"])
    label = BUILD

    for i in range(180):
        report = get_report(headers, report_id)
        if i < 15 or i % 5 == 0:
            step_status = {str(child.get("sort")): child.get("status") for child in report.get("children") or []}
            log(
                "REPORT_POLL "
                + json.dumps(
                    {
                        "i": i,
                        "status": report.get("status"),
                        "execStatus": report.get("execStatus"),
                        "stepTotal": report.get("stepTotal"),
                        "success": report.get("stepSuccessCount"),
                        "pending": report.get("stepPendingCount"),
                        "error": report.get("stepErrorCount"),
                        "step_status": step_status,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
        if report.get("execStatus") == "COMPLETED":
            report_path = OUTPUT_DIR / f"metersphere_report_{OUTPUT_PREFIX}_{report_id}_{label}_latest.json"
            save_json(report_path, {"code": 100200, "data": report})
            log(f"SAVED_REPORT {report_path}")
            inspect_step_12_detail(headers, report, label)
            collect_step_details(headers, report, label)
            phone = extract_phone(report)
            if not phone:
                # fall back to any phone present in the step details or DB
                for child in report.get("children") or []:
                    if child.get("sort") == 1 and child.get("requestBody"):
                        m = re.search(r"1\d{10}", str(child.get("requestBody")))
                        if m:
                            phone = m.group(0)
                            break
            merchant_id = None
            if phone:
                row = db_one(
                    "SELECT merchant_id FROM dpu_users WHERE phone_number=%s ORDER BY created_at DESC LIMIT 1",
                    (phone,),
                )
                merchant_id = row["merchant_id"] if row else None
            verification = db_verify(phone, merchant_id)
            verification.update(
                {
                    "report_id": report_id,
                    "status": report.get("status"),
                    "execStatus": report.get("execStatus"),
                    "stepSuccessCount": report.get("stepSuccessCount"),
                    "stepPendingCount": report.get("stepPendingCount"),
                    "stepErrorCount": report.get("stepErrorCount"),
                    "scriptErrors": report.get("scriptErrors"),
                    "stuck_reason": report.get("stuck_reason"),
                    "report": report,
                }
            )
            save_json(OUTPUT_DIR / f"metersphere_report_{OUTPUT_PREFIX}_{report_id}_{label}_verification.json", verification)
            log(
                "FINAL "
                + json.dumps(
                    {
                        "report_id": report_id,
                        "status": report.get("status"),
                        "execStatus": report.get("execStatus"),
                        "stepSuccessCount": report.get("stepSuccessCount"),
                        "stepPendingCount": report.get("stepPendingCount"),
                        "stepErrorCount": report.get("stepErrorCount"),
                        "phone": phone,
                        "merchant_id": merchant_id,
                        "scriptErrors": report.get("scriptErrors"),
                        "stuck_reason": report.get("stuck_reason"),
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
            if report.get("status") == "SUCCESS" and int(report.get("stepErrorCount") or 0) == 0:
                return 0
            return 2
        time.sleep(5)

    report = get_report(headers, report_id)
    report_path = OUTPUT_DIR / f"metersphere_report_{OUTPUT_PREFIX}_{report_id}_{label}_timeout.json"
    save_json(report_path, {"code": 100200, "data": report})
    log(f"TIMEOUT saved_report={report_path}")
    collect_step_details(headers, report, label)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
