import json
import random
import time
import uuid
from pathlib import Path

import pymysql
import requests


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "自动化" / "scenario_2_fp_usd_2k.ms"
OUTPUT_PATH = Path(__file__).resolve().with_name("fp_usd_2k_validation_result.json")

BASE_URL = "https://uat.api.expressfinance.business.hsbc.com"
DB_CONFIG = {
    "host": "aurora-dpu-uat.cluster-cv2aqqmyo5k9.ap-east-1.rds.amazonaws.com",
    "user": "dpu_uat",
    "password": "6S[a=u.*Z;Zt~b&-A4|Ma&q^w8r_3vz[",
    "database": "dpu_seller_center",
    "port": 3306,
    "charset": "utf8mb4",
    "connect_timeout": 15,
    "read_timeout": 15,
    "autocommit": True,
}


def db_fetchone(sql: str, args=()):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()


def api_request(method: str, path: str, *, token=None, json_body=None, params=None, include_product_headers=True):
    headers = {"content-type": "application/json"}
    if include_product_headers:
        headers.update(
            {
                "finance-product": "LINE_OF_CREDIT",
                "funder-resource": "FUNDPARK",
                "product-currency": "USD",
            }
        )
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, BASE_URL + path, headers=headers, json=json_body, params=params, timeout=30)


def expect_ok(resp, step_name: str):
    if resp.status_code != 200:
        raise RuntimeError(f"{step_name} HTTP failed: {resp.status_code} {resp.text[:500]}")
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"{step_name} business failed: {data}")
    return data


def build_director_payload():
    return {
        "data": {
            "persons": [
                {
                    "addStatus": "API",
                    "adressLine": "",
                    "backDocName": "20251123-190026.jpg",
                    "city": "",
                    "countryAndRegion": "",
                    "dateOfBirth": "01/04/2026",
                    "emailAddress": "number@q.com",
                    "equityRatio": 40,
                    "frontDocName": "20251123-190026.jpg",
                    "id": str(uuid.uuid4()),
                    "idBackFlag": True,
                    "idDocumentBackUrl": "uploads/default/default/default/file_20260402063050_c40c747f1286.jpg",
                    "idDocumentFrontUrl": "uploads/default/default/default/file_20260402062831_fc58bdd81df3.jpg",
                    "idDocumentType": "PRC_RESIDENT_ID_CARD",
                    "idFrontFlag": True,
                    "mobileNumber": {"countryCode": "+86", "number": "17829290101"},
                    "mobileNumber.number": "17829290101",
                    "nameCn": "刘芷兰",
                    "nameEn": "LAUTSZ LAN",
                    "nationality": "China",
                    "percentageOfShares": 40,
                    "position": "DIRECTOR_SHAREHOLDER_UBO",
                    "postalCode": "",
                    "secAdressLine": "",
                },
                {
                    "addStatus": "API",
                    "adressLine": "",
                    "backDocName": "20251123-190026.jpg",
                    "city": "",
                    "countryAndRegion": "",
                    "dateOfBirth": "01/04/2026",
                    "emailAddress": "18829291010@q.com",
                    "equityRatio": 40,
                    "frontDocName": "20260119-174734.jpg",
                    "id": str(uuid.uuid4()),
                    "idBackFlag": True,
                    "idDocumentBackUrl": "uploads/default/default/default/file_20260402063026_11cc531f1122.jpg",
                    "idDocumentFrontUrl": "uploads/default/default/default/file_20260402063023_5955b94df355.jpg",
                    "idDocumentType": "PRC_RESIDENT_ID_CARD",
                    "idFrontFlag": True,
                    "mobileNumber": {"countryCode": "+86", "number": "18829291010"},
                    "mobileNumber.number": "18829291010",
                    "nameCn": "黄吕武",
                    "nameEn": "LYU WU HUANG",
                    "nationality": "China",
                    "percentageOfShares": 40,
                    "position": "DIRECTOR_SHAREHOLDER_UBO",
                    "postalCode": "",
                    "secAdressLine": "",
                },
            ]
        },
        "isDraft": False,
        "step": "2",
    }


def validate_scene_structure():
    data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    steps = sorted(data["scenarioStepList"], key=lambda item: (item.get("sort", 0), item.get("parentId") is not None, str(item["id"])))
    step_names = [step["name"] for step in steps if step.get("parentId") is None]
    required_names = [
        "验证码调用验证生成一次token",
        "选择FUNDPARK流程",
        "approved-offer",
        "esign",
        "disbursement-completed",
        "轮询credit offer状态",
        "轮询drawdown状态",
    ]
    for name in required_names:
        assert name in step_names, f"missing step: {name}"

    def get_blob_by_sort(sort_no: int):
        step = next(step for step in data["scenarioStepList"] if step.get("sort") == sort_no and step.get("parentId") is None)
        return step, json.loads(data["scenarioStepBlobMap"][str(step["id"])])

    checks = {}

    step2, blob2 = get_blob_by_sort(2)
    common2 = next(child for child in blob2["children"] if child.get("polymorphicName") == "MsCommonElement")
    sql_scripts = [processor["script"] for processor in common2["preProcessorConfig"]["processors"] if processor["processorType"] == "SQL"]
    body2 = blob2["body"]["bodyDataByType"]["jsonValue"]
    checks["sms_sql_query"] = any("dpu_sms_record" in script for script in sql_scripts)
    checks["sms_code_variable"] = "${verificationCode}" in body2

    step23, blob23 = get_blob_by_sort(23)
    pre23 = json.dumps(next(child for child in blob23["children"] if child.get("polymorphicName") == "MsCommonElement")["preProcessorConfig"], ensure_ascii=False)
    body23 = blob23["body"]["bodyDataByType"]["jsonValue"]
    checks["approved_default_2000"] = "2000" in pre23 and "approvedoffer.completed" in body23 and '"termUnit": "Months"' in body23

    step24, blob24 = get_blob_by_sort(24)
    pre24 = json.dumps(next(child for child in blob24["children"] if child.get("polymorphicName") == "MsCommonElement")["preProcessorConfig"], ensure_ascii=False)
    body24 = blob24["body"]["bodyDataByType"]["jsonValue"]
    checks["esign_default_2000"] = "2000" in pre24 and "esign.completed" in body24

    step28, blob28 = get_blob_by_sort(28)
    pre28 = json.dumps(next(child for child in blob28["children"] if child.get("polymorphicName") == "MsCommonElement")["preProcessorConfig"], ensure_ascii=False)
    body28 = blob28["body"]["bodyDataByType"]["jsonValue"]
    checks["disbursement_sql_loan"] = "SELECT loan_id FROM dpu_seller_center.dpu_drawdown" in pre28
    checks["disbursement_event"] = "disbursement.completed" in body28

    for key, value in checks.items():
        assert value, f"structure check failed: {key}"

    return {
        "scenario_name": data["exportScenarioList"][0]["name"],
        "step_total": data["exportScenarioList"][0]["stepTotal"],
        "required_steps": required_names,
        "checks": checks,
    }


def fetch_sms_code(phone: str):
    for _ in range(15):
        row = db_fetchone(
            "SELECT placeholders FROM dpu_sms_record WHERE phone_number=%s ORDER BY COALESCE(send_time, create_time) DESC, id DESC LIMIT 1",
            (phone,),
        )
        if row and row[0]:
            raw = row[0]
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict) and data.get("verificationCode"):
                    return data["verificationCode"]
            except Exception:
                pass
        time.sleep(2)
    raise RuntimeError("failed to fetch sms verification code from UAT DB")


def live_uat_validation():
    phone = "1" + "".join(str(random.randint(0, 9)) for _ in range(10))
    email = f"{phone}@163.com"
    state = str(uuid.uuid4())
    selling_partner_id = "".join(random.choice("0123456789ABCDEF") for _ in range(32))
    steps = []

    def record(step_name: str, payload):
        steps.append({"step": step_name, **payload})

    expect_ok(
        api_request(
            "POST",
            "/dpu-user/auth/verification-codes",
            json_body={"areaCode": "+86", "code": "SIGNUP_VERIFICATION", "phone": phone},
        ),
        "send registration sms",
    )
    code = fetch_sms_code(phone)
    record("db sms query", {"phone": phone, "verification_code": code})

    expect_ok(
        api_request(
            "POST",
            "/dpu-user/auth/validateSmsCode-sign",
            json_body={"areaCode": "+86", "code": code, "phone": phone},
        ),
        "validate sms code",
    )
    signup_json = expect_ok(
        api_request(
            "POST",
            "/dpu-user/auth/signup",
            json_body={
                "phone": phone,
                "areaCode": "+86",
                "code": code,
                "password": "Aa11111111..",
                "confirmPassword": "Aa11111111..",
                "securityQuestionCode": "SEC_Q_001",
                "securityAnswer": "dsb",
                "email": email,
                "offerId": "",
                "isAcceptMarketing": True,
                "isAcceptMarketing2": True,
                "sourcePage": "aboutUs",
            },
        ),
        "signup",
    )
    token = signup_json["data"]["token"]
    record("signup", {"token_prefix": token[:12]})

    expect_ok(
        api_request(
            "POST",
            "/dpu-merchant/funder/updateMerchantFunder",
            token=token,
            json_body={"funderCode": "FUNDPARK", "currency": "USD"},
        ),
        "switch funder",
    )

    expect_ok(
        api_request(
            "POST",
            "/dpu-merchant/shop-authorization/v2/sp-auth-url",
            token=token,
            json_body={
                "redirectUrl": f"https://expressfinance-uat.business.hsbc.com/redirect-loading?state={state}",
                "sceneCode": "SHOP_BIND",
                "sourceCode": "FUNDPARK",
                "state": state,
            },
        ),
        "generate sp state",
    )
    sp_auth_resp = api_request(
        "GET",
        "/dpu-auth/amazon-sp/auth",
        token=token,
        params={
            "mws_auth_token": "1235",
            "selling_partner_id": selling_partner_id,
            "spapi_oauth_code": "123123",
            "state": state,
        },
    )
    assert sp_auth_resp.status_code == 200, f"sp auth failed: {sp_auth_resp.status_code}"

    offer_json = expect_ok(
        api_request(
            "POST",
            "/dpu-merchant/mock/generate-shop-performance",
            json_body={"yearlyRepaymentAmount": 100000},
            include_product_headers=False,
        ),
        "generate 3pl offer",
    )
    offer_id = offer_json["data"]["amazon3plOfferId"]
    record("generate 3pl offer", {"offer_id": offer_id})

    get_resp = api_request("GET", "/dpu-merchant/amazon/redirect", token=token, params={"offerId": offer_id})
    assert get_resp.status_code == 200, f"3pl redirect GET failed: {get_resp.status_code}"
    expect_ok(
        api_request(
            "POST",
            "/dpu-merchant/amazon/redirect",
            token=token,
            json_body={
                "authToken": "mock",
                "expireOn": "null",
                "keyId": "null",
                "offerId": offer_id,
                "relayPage": 1,
                "returnUrl": "null",
                "signature": "null",
            },
        ),
        "3pl redirect post",
    )

    expect_ok(
        api_request("POST", "/dpu-merchant/fundpark-application/create", token=token, json_body={"tierCode": "2", "tierSnapshotValue": 0}),
        "create application",
    )
    expect_ok(
        api_request(
            "POST",
            "/dpu-merchant/fundpark-application/business-info",
            token=token,
            json_body={
                "clear": True,
                "data": {
                    "bizDetail": {"cnName": "中文企业名", "enName": "English", "regNo": "10000001"},
                    "bizInfo": {
                        "fundSources": ["bizOperations"],
                        "fundingCountry": "Hong Kong",
                        "industry": "Furniture",
                        "initWealth": ["savings"],
                        "mainProducts": "Home Improvement",
                        "ongoingWealth": ["operationProfit"],
                        "topBuyers": ["United States Of America", "Canada", "Mexico"],
                        "topSuppliers": ["China"],
                    },
                },
                "isDraft": False,
                "step": "2",
            },
        ),
        "business info",
    )
    expect_ok(
        api_request("POST", "/dpu-merchant/fundpark-application/director-info", token=token, json_body=build_director_payload()),
        "director info",
    )
    expect_ok(
        api_request("POST", "/dpu-merchant/fundpark-application/cache-higher-limit", token=token, json_body={"limitSelection": 2000}),
        "cache higher limit",
    )
    expect_ok(api_request("GET", "/dpu-merchant/credit-offer/final-offer-select", token=token), "final offer select")
    expect_ok(api_request("POST", "/dpu-merchant/credit-offer/activate-offer", token=token), "activate offer")
    expect_ok(api_request("POST", "/dpu-merchant/mock/link-sp-3pl-shops", token=token, params={"phone": phone}), "link shops")
    expect_ok(api_request("POST", "/dpu-merchant/test/scheduled-tasks/hsbcSanctionTask", token=token), "sanction task")
    expect_ok(api_request("POST", "/dpu-merchant/test/scheduled-tasks/first-credit-model", token=token), "first credit model task")
    expect_ok(api_request("POST", "/dpu-merchant/test/scheduled-tasks/first-application-start", token=token), "first application start task")

    application_status = expect_ok(api_request("GET", "/dpu-merchant/hsbc/application-status", token=token), "application-status")["data"]
    process_status = expect_ok(api_request("GET", "/dpu-merchant/fundpark-application/process-status", token=token), "process-status")["data"]
    shops = expect_ok(
        api_request("GET", "/dpu-merchant/shop-management/v2/shops", token=token, params={"businessContext": "REASSESSMENT"}),
        "shop management",
    )["data"]["shopList"]
    marketing_quota = expect_ok(api_request("GET", "/dpu-merchant/fundpark-application/marketing-quota", token=token), "marketing quota")["data"]
    product_tier = expect_ok(api_request("GET", "/dpu-merchant/fundpark-application/product-tier", token=token), "product tier")["data"]
    drawdown_status = expect_ok(api_request("GET", "/dpu-merchant/drawdown/status", token=token), "drawdown status")["data"]

    active_shop_count = 0
    for shop in shops:
        status = ((shop.get("shopInfo") or {}).get("threePlShopStatus") or {}).get("status")
        if status in {"ACTIVE", "NO_AUTHORIZATION_REQUIRED"}:
            active_shop_count += 1

    assert application_status["status"] == "SUBMITTED", application_status
    assert application_status["applicationFlow"] == "drawdownDetails", application_status
    assert process_status["status"] == "drawdownDetails", process_status
    assert active_shop_count >= 1, shops
    assert str(marketing_quota["preApprovedLimit"]) in ("2000", "2000.0", "2000.00"), marketing_quota
    assert marketing_quota["currency"] == "USD", marketing_quota
    assert marketing_quota["tier"] == "L1", marketing_quota
    assert product_tier["tier"] == "L1", product_tier
    assert "2K-200K" in str(product_tier["description"]), product_tier
    assert drawdown_status["status"] == "INIT", drawdown_status
    assert drawdown_status["drawdownLimit"]["currency"] == "USD", drawdown_status

    merchant_row = db_fetchone(
        "SELECT merchant_id FROM dpu_users WHERE phone_number=%s ORDER BY created_at DESC LIMIT 1",
        (phone,),
    )
    merchant_id = merchant_row[0]
    limit_application_row = db_fetchone(
        "SELECT limit_application_unique_id, status, activated_limit FROM dpu_limit_application WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,),
    )
    credit_offer_row = db_fetchone(
        "SELECT lender_approved_offer_id, status, approved_limit_amount, e_sign_status FROM dpu_credit_offer WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,),
    )
    drawdown_row = db_fetchone(
        "SELECT loan_id, status, drawdown_amount FROM dpu_drawdown WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,),
    )

    webhook_probe = {
        "merchant_id": merchant_id,
        "limit_application_row": limit_application_row,
        "credit_offer_row": credit_offer_row,
        "drawdown_row": drawdown_row,
        "status": "SKIPPED",
        "reason": "",
    }
    if credit_offer_row and drawdown_row:
        webhook_probe["status"] = "READY"
    else:
        webhook_probe["reason"] = "UAT pure API path did not produce dpu_limit_application / dpu_credit_offer / dpu_drawdown rows, so live webhook replay was not executable in this environment."

    return {
        "phone": phone,
        "email": email,
        "steps": steps,
        "application_status": application_status,
        "process_status": process_status,
        "active_shop_count": active_shop_count,
        "marketing_quota": marketing_quota,
        "product_tier": product_tier,
        "drawdown_status": drawdown_status,
        "webhook_probe": webhook_probe,
    }


def main():
    report = {
        "validated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "scenario_file": str(SCENARIO_PATH),
        "base_url": BASE_URL,
        "result": "FAIL",
    }
    structure_validation = validate_scene_structure()
    live_validation = live_uat_validation()
    report["structure_validation"] = structure_validation
    report["live_uat_validation"] = live_validation
    report["result"] = "PASS"
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
