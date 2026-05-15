# -*- coding: utf-8 -*-
"""Run the latest FP-CNY-1500k MeterSphere REG scenario and save evidence."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


MS_BASE = "https://loan-tools-dpu-sit.dowsure.com"
PROJECT_ID = "771977421840384"
ENVIRONMENT_ID = "849939668205568"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

MS_TOKEN = os.environ.get("MS_TOKEN", "2c850cda-9743-4d41-af22-2d92abe2727a")
MS_CSRF = os.environ.get(
    "MS_CSRF",
    "JE/ZnP0+uIIZLsYz3vXhNbnb6VRRRLcs7ToF4M0Dx3qGlCrmU3lvPqCnFsWr8zHqlHNiP1sIXzye9Domab5dmzo5yYCX/9Fv7DVo/Z4AAPk=",
)


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def headers(json_content: bool = False) -> dict[str, str]:
    result = {
        "x-auth-token": MS_TOKEN,
        "csrf-token": MS_CSRF,
        "organization": "100001",
        "project": PROJECT_ID,
        "accept": "application/json, text/plain, */*",
        "referer": MS_BASE + "/",
    }
    if json_content:
        result["content-type"] = "application/json;charset=UTF-8"
    return result


def ensure_json(response: requests.Response, label: str) -> dict[str, Any]:
    if "application/json" not in (response.headers.get("content-type") or ""):
        raise RuntimeError(
            f"{label} returned non-JSON: status={response.status_code}, "
            f"location={response.headers.get('location')}, body={response.text[:300]!r}"
        )
    payload = response.json()
    if payload.get("code") != 100200:
        raise RuntimeError(f"{label} failed: {payload}")
    return payload


def ms_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        MS_BASE + path,
        headers=headers(json_content=True),
        json=payload,
        timeout=60,
        allow_redirects=False,
    )
    return ensure_json(response, f"POST {path}")


def ms_get(path: str) -> dict[str, Any]:
    response = requests.get(
        MS_BASE + path,
        headers=headers(),
        timeout=60,
        allow_redirects=False,
    )
    return ensure_json(response, f"GET {path}")


def find_latest_cny_scenario() -> dict[str, Any]:
    explicit = os.environ.get("MS_SCENARIO_ID")
    if explicit:
        scenario = ms_get(f"/api/scenario/get/{explicit}")["data"]
        log(f"SCENARIO explicit id={scenario['id']} name={scenario['name']} stepTotal={scenario.get('stepTotal')}")
        return scenario

    payload = {
        "current": 1,
        "pageSize": 20,
        "keyword": "CNY",
        "sort": {},
        "moduleIds": [],
        "projectId": PROJECT_ID,
        "viewId": "",
        "combineSearch": {"searchMode": "AND", "conditions": []},
        "filter": {},
    }
    scenarios = ms_post("/api/scenario/page", payload)["data"]["list"]
    for item in scenarios:
        if "1500" in item.get("name", "") and int(item.get("stepTotal") or 0) == 19:
            log(f"SCENARIO id={item['id']} name={item['name']} stepTotal={item['stepTotal']}")
            return item
    raise RuntimeError("No imported FP-CNY-1500k scenario with 19 steps was found")


def latest_execution(scenario_id: str) -> dict[str, Any] | None:
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
    return (ms_post("/api/scenario/execute/page", payload)["data"].get("list") or [None])[0]


def run_scenario(scenario_id: str) -> str:
    previous = latest_execution(scenario_id)
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
            "poolId": "100001100001",
            "grouped": False,
            "environmentId": ENVIRONMENT_ID,
        },
        "apiDefinitionId": "",
        "versionId": "",
        "refId": "",
    }
    result = ms_post("/api/scenario/batch-operation/run", payload)
    log(f"run_response={json.dumps(result, ensure_ascii=False)[:300]}")

    for _ in range(60):
        execution = latest_execution(scenario_id)
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


def get_report(report_id: str) -> dict[str, Any]:
    return ms_get(f"/api/report/scenario/get/{report_id}")["data"]


def step_status_map(report: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for index, child in enumerate(report.get("children") or [], start=1):
        result[str(child.get("sort") or index)] = child.get("status") or ""
    return result


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def collect_step_details(report: dict[str, Any], label: str) -> None:
    report_id = report["id"]
    for child in report.get("children") or []:
        sort = child.get("sort")
        status = child.get("status")
        if status == "SUCCESS" and int(sort or 0) < 14:
            continue
        step_id = child.get("stepId") or child.get("id")
        if not step_id:
            continue
        try:
            detail = ms_get(f"/api/report/scenario/task-report/{report_id}/{step_id}")
        except Exception as exc:
            log(f"detail_fetch_failed sort={sort} step_id={step_id} error={exc}")
            continue
        detail_path = OUTPUT_DIR / f"api_report_scenario_task-report_{report_id}_{step_id}_{label}.json"
        save_json(detail_path, detail)
        log(f"SAVED_DETAIL sort={sort} status={status} path={detail_path}")


def extract_phone(report: dict[str, Any]) -> str | None:
    text = report.get("console") or ""
    for child in report.get("children") or []:
        for key in ("console", "requestBody", "responseBody"):
            value = child.get(key)
            if value:
                text += "\n" + str(value)
    phones = re.findall(r"(?<!\d)1\d{10}(?!\d)", text)
    return phones[0] if phones else None


def main() -> int:
    scenario = find_latest_cny_scenario()
    report_id = run_scenario(scenario["id"])
    label = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(160):
        report = get_report(report_id)
        status_map = step_status_map(report)
        if i < 15 or i % 5 == 0:
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
                        "step_status": status_map,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
        if report.get("execStatus") == "COMPLETED":
            report_path = OUTPUT_DIR / f"metersphere_report_fp_cny_1500k_{report_id}_{label}_latest.json"
            save_json(report_path, {"code": 100200, "data": report})
            log(f"SAVED_REPORT {report_path}")
            collect_step_details(report, label)
            phone = extract_phone(report)
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
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
            return 0 if report.get("status") == "SUCCESS" else 2
        time.sleep(5)

    report = get_report(report_id)
    report_path = OUTPUT_DIR / f"metersphere_report_fp_cny_1500k_{report_id}_{label}_timeout.json"
    save_json(report_path, {"code": 100200, "data": report})
    log(f"TIMEOUT saved_report={report_path}")
    collect_step_details(report, label)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
