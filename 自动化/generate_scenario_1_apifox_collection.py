import json
import re
import uuid
from pathlib import Path


SCENARIO_PATH = Path(__file__).with_name("scenario_1.ms")
OUTPUT_PATH = Path(__file__).with_name("scenario_1_apifox_postman_collection.json")
BASE_URL = "https://dpu-gateway-reg.dowsure.com"

COMMON_JS = r"""
function setVar(key, value) {
  const text = value === undefined || value === null ? '' : String(value);
  if (pm.environment && pm.environment.set) pm.environment.set(key, text);
  if (pm.collectionVariables && pm.collectionVariables.set) pm.collectionVariables.set(key, text);
}

function getVar(key) {
  if (pm.environment && pm.environment.get && pm.environment.get(key)) return pm.environment.get(key);
  if (pm.collectionVariables && pm.collectionVariables.get && pm.collectionVariables.get(key)) return pm.collectionVariables.get(key);
  if (pm.variables && pm.variables.get && pm.variables.get(key)) return pm.variables.get(key);
  return '';
}

function uuidv4() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function randomHex32() {
  return (uuidv4().replace(/-/g, '') + uuidv4().replace(/-/g, '')).slice(0, 32).toUpperCase();
}

function randomPhone() {
  const prefixes = ['130','131','132','133','135','136','137','138','139','150','151','152','155','156','157','158','159','166','171','172','173','175','176','177','178','180','181','182','183','184','185','186','187','188','189','191','193','195','196','198','199'];
  const suffix = String(Math.floor(Math.random() * 100000000)).padStart(8, '0');
  return prefixes[Math.floor(Math.random() * prefixes.length)] + suffix;
}

function nowUtcNoMillis() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function nowLocalText() {
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}

function dateText(offsetDays) {
  const d = new Date(Date.now() + offsetDays * 24 * 60 * 60 * 1000);
  const pad = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

function ensureVars(keys, hint) {
  const missing = keys.filter(k => !getVar(k));
  if (missing.length > 0) {
    throw new Error('Missing variables: ' + missing.join(', ') + '. ' + hint);
  }
}
"""


def load_scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def ms_to_postman_vars(value):
    if value is None:
        return ""
    value = str(value)
    value = value.replace("@email", "{{email}}")
    value = value.replace("@phoneNumber", "{{phoneNumber}}")
    return re.sub(r"\$\{([^}]+)\}", r"{{\1}}", value)


def enabled_items(items):
    return [item for item in items or [] if item.get("enable") and item.get("key")]


def postman_headers(blob):
    headers = []
    for header in enabled_items(blob.get("headers")):
        headers.append(
            {
                "key": header.get("key", ""),
                "value": ms_to_postman_vars(header.get("value", "")),
                "description": header.get("description", "") or "",
            }
        )
    return headers


def postman_query(blob):
    query = []
    for item in enabled_items(blob.get("query")):
        query.append(
            {
                "key": item.get("key", ""),
                "value": ms_to_postman_vars(item.get("value", "")),
                "description": item.get("description", "") or "",
            }
        )
    return query


def body_data(blob):
    body = blob.get("body") or {}
    body_type = (body.get("bodyType") or "").upper()
    body_by_type = body.get("bodyDataByType") or {}
    json_value = body_by_type.get("jsonValue") or (body.get("jsonBody") or {}).get("jsonValue") or ""
    raw_value = body_by_type.get("value") or (body.get("rawBody") or {}).get("value") or ""
    form_values = body_by_type.get("formValues") or (body.get("wwwFormBody") or {}).get("formValues") or []
    multipart_values = (body.get("formDataBody") or {}).get("formValues") or []

    if body_type == "JSON" and str(json_value).strip():
        return {
            "mode": "raw",
            "raw": ms_to_postman_vars(json_value),
            "options": {"raw": {"language": "json"}},
        }
    if body_type == "RAW" and str(raw_value).strip():
        return {
            "mode": "raw",
            "raw": ms_to_postman_vars(raw_value),
            "options": {"raw": {"language": "text"}},
        }
    if body_type in {"WWW_FORM", "X_WWW_FORM_URLENCODED"} and form_values:
        return {
            "mode": "urlencoded",
            "urlencoded": [
                {
                    "key": item.get("key", ""),
                    "value": ms_to_postman_vars(item.get("value", "")),
                    "description": item.get("description", "") or "",
                }
                for item in enabled_items(form_values)
            ],
        }
    if body_type == "FORM_DATA" and multipart_values:
        return {
            "mode": "formdata",
            "formdata": [
                {
                    "key": item.get("key", ""),
                    "value": ms_to_postman_vars(item.get("value", "")),
                    "type": "text",
                    "description": item.get("description", "") or "",
                }
                for item in enabled_items(multipart_values)
            ],
        }
    return None


def js_exec(script):
    return [line.rstrip() for line in script.strip("\n").splitlines()]


def prerequest_script(logical_sort):
    scripts = {
        "4": r"""
const phone = getVar('phone') || randomPhone();
setVar('phone', phone);
setVar('phoneNumber', phone);
setVar('email', getVar('email') || (phone + '@163.com'));
setVar('preferredCurrency', getVar('preferredCurrency') || 'USD');
setVar('approvedAmount', getVar('approvedAmount') || '500000');
setVar('signedAmount', getVar('signedAmount') || '500000');
setVar('underwrittenAmount', getVar('underwrittenAmount') || '500000');
setVar('credit_offer_status', 'INIT');
setVar('poll_count', '0');
console.log('[scenario_1] generated phone=' + phone);
""",
        "5": r"""
if (!getVar('verificationCode')) {
  throw new Error('Missing verificationCode. Query dpu_sms_record by phone after step 04, then set verificationCode.');
}
""",
        "7": r"""
setVar('state', getVar('state') || uuidv4());
""",
        "8": r"""
setVar('selling_partner_id', getVar('selling_partner_id') || randomHex32());
""",
        "9": r"""
ensureVars(
  ['idempotency_key', 'platform_offer_id'],
  'After step 08, query dpu_manual_offer by selling_partner_id and set idempotency_key/platform_offer_id.'
);
setVar('platformOfferId', getVar('platformOfferId') || getVar('platform_offer_id'));
""",
        "10": r"""
ensureVars(['platformOfferId'], 'Set platformOfferId from dpu_manual_offer.platform_offer_id.');
""",
        "11": r"""
setVar('platform_offer_id', getVar('platform_offer_id') || getVar('platformOfferId'));
ensureVars(['platform_offer_id'], 'Set platform_offer_id from dpu_manual_offer.platform_offer_id.');
""",
        "14": r"""
setVar('director1_id', getVar('director1_id') || uuidv4());
setVar('director1_front_doc_name', getVar('director1_front_doc_name') || '20251123-190026.jpg');
setVar('director1_back_doc_name', getVar('director1_back_doc_name') || '20251123-190026.jpg');
setVar('director1_front_file_url', getVar('director1_front_file_url') || 'uploads/default/default/default/file_20260402062831_fc58bdd81df3.jpg');
setVar('director1_back_file_url', getVar('director1_back_file_url') || 'uploads/default/default/default/file_20260402063050_c40c747f1286.jpg');
""",
        "16": r"""
setVar('director1_id', getVar('director1_id') || uuidv4());
setVar('director1_front_doc_name', getVar('director1_front_doc_name') || '20251123-190026.jpg');
setVar('director1_back_doc_name', getVar('director1_back_doc_name') || '20251123-190026.jpg');
setVar('director1_front_file_url', getVar('director1_front_file_url') || 'uploads/default/default/default/file_20260402062831_fc58bdd81df3.jpg');
setVar('director1_back_file_url', getVar('director1_back_file_url') || 'uploads/default/default/default/file_20260402063050_c40c747f1286.jpg');
""",
        "24.1": r"""
setVar('poll_count', getVar('poll_count') || '0');
setVar('credit_offer_status', getVar('credit_offer_status') || 'INIT');
""",
        "27": r"""
ensureVars(
  ['merchantId'],
  'Before approved-offer, query dpu_users by phone and set merchantId. Optional: set preferredCurrency from the same row.'
);
setVar('preferredCurrency', getVar('preferredCurrency') || 'USD');
ensureVars(['dpuApplicationId'], 'Set dpuApplicationId from step 12 response data or query dpu_application by merchantId.');
setVar('dpuMerchantAccountId', getVar('dpuMerchantAccountId') || getVar('selling_partner_id'));
setVar('lenderApprovedOfferId', getVar('lenderApprovedOfferId') || ('lender-' + getVar('dpuApplicationId')));
setVar('eventId', uuidv4());
setVar('datetime_utc', nowUtcNoMillis());
setVar('lastUpdatedOn', nowLocalText());
setVar('approvedOriginalRequestId', 'req_' + getVar('eventId').replace(/-/g, ''));
setVar('offerStartDate', dateText(0));
setVar('offerEndDate', dateText(90));
setVar('approvedAmount', getVar('approvedAmount') || '500000');
setVar('chargeBases', getVar('preferredCurrency') === 'CNY' ? 'Fixed' : 'Float');
""",
        "28": r"""
setVar('lenderApprovedOfferId', getVar('lenderApprovedOfferId') || ('lender-' + getVar('dpuApplicationId')));
setVar('dpuMerchantAccountId', getVar('dpuMerchantAccountId') || getVar('selling_partner_id'));
ensureVars(['merchantId', 'dpuMerchantAccountId', 'lenderApprovedOfferId'], 'Set merchant/account/offer IDs before PSP started webhook.');
setVar('eventId', uuidv4());
setVar('datetime_utc', nowUtcNoMillis());
setVar('lastUpdatedOn', nowLocalText());
""",
        "29": r"""
setVar('lenderApprovedOfferId', getVar('lenderApprovedOfferId') || ('lender-' + getVar('dpuApplicationId')));
setVar('dpuMerchantAccountId', getVar('dpuMerchantAccountId') || getVar('selling_partner_id'));
ensureVars(['merchantId', 'dpuMerchantAccountId', 'lenderApprovedOfferId'], 'Set merchant/account/offer IDs before PSP completed webhook.');
setVar('eventId', uuidv4());
setVar('datetime_utc', nowUtcNoMillis());
setVar('lastUpdatedOn', nowLocalText());
""",
        "30": r"""
setVar('lenderApprovedOfferId', getVar('lenderApprovedOfferId') || ('lender-' + getVar('dpuApplicationId')));
ensureVars(['merchantId', 'lenderApprovedOfferId'], 'Set merchantId and lenderApprovedOfferId before eSign webhook.');
setVar('preferredCurrency', getVar('preferredCurrency') || 'USD');
setVar('signedAmount', getVar('signedAmount') || '500000');
setVar('eventId', uuidv4());
setVar('datetime_utc', nowUtcNoMillis());
setVar('lastUpdatedOn', nowLocalText());
""",
    }
    script = scripts.get(str(logical_sort))
    if not script:
        return None
    return {
        "listen": "prerequest",
        "script": {"type": "text/javascript", "exec": js_exec(COMMON_JS + "\n" + script)},
    }


def custom_test_lines(logical_sort):
    scripts = {
        "4": r"""
const phone = getVar('phone') || getVar('phoneNumber');
if (phone) {
  setVar('phone', phone);
  setVar('phoneNumber', phone);
}
console.log('[scenario_1] Step 04 done. If step 05 fails, query SMS code from DB and set verificationCode.');
""",
        "6": r"""
const json = pm.response.json();
if (json && json.data && json.data.token) {
  setVar('token', json.data.token);
}
ensureVars(['token'], 'Signup response did not return data.token.');
""",
        "12": r"""
const json = pm.response.json();
if (json && json.data) {
  setVar('dpuApplicationId', json.data);
}
console.log('[scenario_1] dpuApplicationId=' + getVar('dpuApplicationId'));
""",
        "24.1": r"""
const json = pm.response.json();
const status = json && json.data ? json.data.status : '';
setVar('credit_offer_status', status || '');
const count = parseInt(getVar('poll_count') || '0', 10) + 1;
setVar('poll_count', String(count));
console.log('[scenario_1] poll status=' + status + ', count=' + count);
if (status !== 'SUBMITTED' && count < 30 && typeof postman !== 'undefined' && postman.setNextRequest) {
  postman.setNextRequest(pm.info.requestName);
}
if (status !== 'SUBMITTED' && count >= 30) {
  throw new Error('credit_offer_status did not reach SUBMITTED within 30 polls, current=' + status);
}
""",
        "27": r"""
setVar('lenderApprovedOfferId', getVar('lenderApprovedOfferId') || ('lender-' + getVar('dpuApplicationId')));
""",
    }
    script = scripts.get(str(logical_sort))
    if not script:
        return []
    return ["", *js_exec(COMMON_JS + "\n" + script)]


def assertion_tests(blob, logical_sort):
    child = (blob.get("children") or [{}])[0]
    assertions = (child.get("assertionConfig") or {}).get("assertions") or []
    tests = [
        "pm.test('HTTP status is 200', function () {",
        "  pm.response.to.have.status(200);",
        "});",
    ]
    json_assertions = []
    for assertion in assertions:
        for item in ((assertion.get("jsonPathAssertion") or {}).get("assertions") or []):
            if not item.get("enable"):
                continue
            expression = item.get("expression")
            expected = item.get("expectedValue")
            condition = item.get("condition")
            if expression == "$.code" and str(expected) == "200" and condition == "EQUALS":
                json_assertions.append("  pm.expect(json.code).to.eql(200);")
            elif expression == "$.data" and str(expected) == "{}" and condition == "EQUALS":
                json_assertions.append("  pm.expect(json.data).to.deep.eql({});")
    if json_assertions:
        tests.extend(
            [
                "",
                "pm.test('MeterSphere JSON assertions', function () {",
                "  const json = pm.response.json();",
                *json_assertions,
                "});",
            ]
        )
    tests.extend(custom_test_lines(logical_sort))
    return [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}]


def request_item(step, blob, name_prefix, logical_sort):
    method = (blob.get("method") or "GET").upper()
    path = blob.get("path") or blob.get("url") or ""
    query = postman_query(blob)
    raw_url = "{{baseUrl}}" + path
    if query:
        raw_url += "?" + "&".join(
            f"{item['key']}={item['value']}" for item in query if item.get("key")
        )
    request = {
        "method": method,
        "header": postman_headers(blob),
        "url": {
            "raw": raw_url,
            "host": ["{{baseUrl}}"],
            "path": [segment for segment in path.split("/") if segment],
            "query": query,
        },
        "description": (
            f"Converted from MeterSphere scenario_1.ms step id {step.get('id')}. "
            "MeterSphere SQL/script processors are not executable in Postman/Apifox and "
            "must be recreated as Apifox pre/post scripts if needed."
        ),
    }
    body = body_data(blob)
    if body:
        request["body"] = body
    step_name = step.get("name") or ""
    if step_name == "??SUBMITTED":
        step_name = "\u8f6e\u8be2SUBMITTED"
    events = []
    pre = prerequest_script(logical_sort)
    if pre:
        events.append(pre)
    events.extend(assertion_tests(blob, logical_sort))
    return {
        "name": f"{name_prefix} {step_name}",
        "request": request,
        "event": events,
    }


def collect_http_steps(data):
    steps = data["scenarioStepList"]
    blobs = data["scenarioStepBlobMap"]
    top_level = [step for step in steps if step.get("parentId") is None]
    top_level.sort(key=lambda step: step.get("sort") or 0)
    items = []
    for step in top_level:
        if not step.get("enable"):
            continue
        if step.get("stepType") in {"API", "CUSTOM_REQUEST"}:
            blob = json.loads(blobs[str(step["id"])])
            sort_label = str(int(step.get("sort")))
            items.append(request_item(step, blob, f"{int(step.get('sort')):02d}", sort_label))
        if step.get("stepType") == "LOOP_CONTROLLER":
            children = [
                child
                for child in steps
                if child.get("parentId") == step["id"]
                and child.get("enable")
                and child.get("stepType") in {"API", "CUSTOM_REQUEST"}
            ]
            children.sort(key=lambda child: child.get("sort") or 0)
            for child in children:
                blob = json.loads(blobs[str(child["id"])])
                sort_label = f"{int(step.get('sort'))}.{int(child.get('sort'))}"
                items.append(request_item(child, blob, f"{int(step.get('sort')):02d}.{int(child.get('sort'))}", sort_label))
    return items


def collect_variables(data, items):
    variables = {
        "baseUrl": BASE_URL,
        "token": "",
        "phone": "",
        "phoneNumber": "",
        "email": "",
        "verificationCode": "666666",
        "state": "",
        "selling_partner_id": "",
        "idempotency_key": "",
        "platform_offer_id": "",
        "platformOfferId": "",
        "merchantId": "",
        "preferredCurrency": "USD",
        "dpuLimitApplicationId": "",
        "dpuApplicationId": "",
        "dpuMerchantAccountId": "",
        "lenderApprovedOfferId": "",
        "eventId": "",
        "datetime_utc": "",
        "lastUpdatedOn": "",
        "approvedAmount": "500000",
        "signedAmount": "500000",
        "underwrittenAmount": "500000",
        "director1_front_file_url": "uploads/default/default/default/file_20260402062831_fc58bdd81df3.jpg",
        "director1_back_file_url": "uploads/default/default/default/file_20260402063050_c40c747f1286.jpg",
    }
    common = (
        data["exportScenarioList"][0]
        .get("scenarioConfig", {})
        .get("variable", {})
        .get("commonVariables", [])
    )
    for item in common:
        if item.get("enable") and item.get("key"):
            variables[item["key"]] = item.get("value", "")

    serialized = json.dumps(items, ensure_ascii=False)
    for name in sorted(set(re.findall(r"\{\{([^}]+)\}\}", serialized))):
        variables.setdefault(name, "")
    return [{"key": key, "value": value, "type": "string"} for key, value in variables.items()]


def main():
    data = load_scenario()
    scenario = data["exportScenarioList"][0]
    items = collect_http_steps(data)
    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": f"{scenario.get('name', 'scenario_1')} - Apifox Import",
            "description": (
                "Converted from MeterSphere scenario_1.ms for Apifox/Postman import. "
                "Import this file in Apifox using the Postman format."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": collect_variables(data, items),
    }
    OUTPUT_PATH.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated={OUTPUT_PATH}")
    print(f"requests={len(items)}")


if __name__ == "__main__":
    main()
