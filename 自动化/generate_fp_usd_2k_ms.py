import copy
import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCENARIO = ROOT / "自动化" / "scenario_1.ms"
API_EXPORT = ROOT / "彦宏接口" / "all_apis_v3_complete.json"
OUTPUT_SCENARIO = ROOT / "自动化" / "scenario_2_fp_usd_2k.ms"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, data):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def deep_find_api_templates(obj, result):
    if isinstance(obj, dict):
        if obj.get("path") and obj.get("request"):
            key = (obj.get("path"), obj.get("method"))
            result[key] = obj
        for value in obj.values():
            deep_find_api_templates(value, result)
    elif isinstance(obj, list):
        for item in obj:
            deep_find_api_templates(item, result)


def build_api_index(api_export):
    result = {}
    deep_find_api_templates(api_export, result)
    return result


def standard_headers(include_auth: bool = True):
    headers = []
    if include_auth:
        headers.append({"key": "Authorization", "value": "Bearer ${token}", "enable": True, "description": "", "notBlankValue": True, "valid": True})
    headers.extend(
        [
            {"key": "content-type", "value": "application/json", "enable": True, "description": "", "notBlankValue": True, "valid": True},
            {"key": "finance-product", "value": "LINE_OF_CREDIT", "enable": True, "description": "", "notBlankValue": True, "valid": True},
            {"key": "funder-resource", "value": "FUNDPARK", "enable": True, "description": "", "notBlankValue": True, "valid": True},
            {"key": "product-currency", "value": "USD", "enable": True, "description": "", "notBlankValue": True, "valid": True},
        ]
    )
    return headers


def code_200_assertion():
    return {
        "assertionType": "RESPONSE_BODY",
        "enable": True,
        "name": "响应体",
        "assertionBodyType": "JSON_PATH",
        "jsonPathAssertion": {
            "assertions": [
                {"enable": True, "expression": "$.code", "condition": "EQUALS", "expectedValue": "200", "valid": True}
            ]
        },
        "xpathAssertion": {"responseFormat": "XML", "assertions": []},
        "documentAssertion": None,
        "regexAssertion": {"assertions": []},
        "bodyAssertionClassByType": "io.metersphere.project.api.assertion.body.MsJSONPathAssertion",
        "bodyAssertionDataByType": {
            "assertions": [
                {"enable": True, "expression": "$.code", "condition": "EQUALS", "expectedValue": "200", "valid": True}
            ]
        },
    }


def common_child(pre=None, post=None, assertions=None):
    return {
        "polymorphicName": "MsCommonElement",
        "assertionConfig": {
            "enableGlobal": False if assertions else True,
            "assertions": assertions or [],
        },
        "postProcessorConfig": {
            "enableGlobal": False if post else True,
            "processors": post or [],
        },
        "preProcessorConfig": {
            "enableGlobal": False if pre else True,
            "processors": pre or [],
        },
    }


def script_processor(script: str, name: str = "脚本名称"):
    return {
        "processorType": "SCRIPT",
        "name": name,
        "enable": True,
        "projectId": None,
        "stepId": None,
        "script": script,
        "scriptLanguage": "PYTHON",
        "enableCommonScript": False,
        "commonScriptInfo": {
            "id": "",
            "deleted": False,
            "name": "",
            "script": "",
            "scriptLanguage": "BEANSHELL_JSR233",
            "params": [],
        },
        "valid": True,
    }


def extract_processor(variable_name: str, expression: str):
    return {
        "processorType": "EXTRACT",
        "name": None,
        "enable": True,
        "projectId": None,
        "stepId": None,
        "extractors": [
            {
                "extractType": "JSON_PATH",
                "variableName": variable_name,
                "variableType": "TEMPORARY",
                "expression": expression,
                "enable": True,
                "resultMatchingRule": "RANDOM",
                "resultMatchingRuleNum": 1,
                "valid": True,
            }
        ],
    }


def sql_processor(script: str, result_variable: str, data_source_id: str, data_source_name: str):
    return {
        "processorType": "SQL",
        "name": "前置 SQL 查询",
        "enable": True,
        "projectId": None,
        "stepId": None,
        "script": script,
        "queryTimeout": 10000,
        "resultVariable": result_variable,
        "variableNames": "",
        "dataSourceId": data_source_id,
        "dataSourceName": data_source_name,
        "extractParams": [],
    }


def make_http_blob(name: str, path: str, method: str, body_type: str = "JSON", json_value: str = "", query=None, include_auth: bool = True, pre=None, post=None, assertions=None):
    body = {
        "bodyType": body_type,
        "noneBody": {},
        "formDataBody": {"formValues": []},
        "wwwFormBody": {"formValues": []},
        "jsonBody": {"enableJsonSchema": False, "jsonValue": json_value, "jsonSchemaTableData": []},
        "xmlBody": {"value": ""},
        "rawBody": {"value": ""},
        "binaryBody": {"description": "", "file": None},
        "bodyClassByType": "io.metersphere.api.dto.request.http.body.JsonBody" if body_type == "JSON" else "io.metersphere.api.dto.request.http.body.NoneBody",
        "bodyDataByType": {"enableJsonSchema": False, "jsonValue": json_value, "jsonSchema": None} if body_type == "JSON" else {},
    }
    if body_type == "NONE":
        body["bodyClassByType"] = "io.metersphere.api.dto.request.http.body.NoneBody"
        body["bodyDataByType"] = {}
    blob = {
        "authConfig": {
            "authType": "NONE",
            "basicAuth": {"userName": "", "password": "", "valid": False},
            "digestAuth": {"userName": "", "password": "", "valid": False},
            "httpauthValid": False,
        },
        "body": body,
        "headers": standard_headers(include_auth=include_auth),
        "otherConfig": {
            "connectTimeout": 60000,
            "responseTimeout": 60000,
            "certificateAlias": "",
            "followRedirects": True,
            "autoRedirects": False,
        },
        "path": path,
        "query": query or [],
        "rest": [],
        "url": path,
        "polymorphicName": "MsHTTPElement",
        "resourceId": None,
        "stepId": None,
        "uniqueId": None,
        "activeTab": "HEADER",
        "responseActiveTab": "BODY",
        "protocol": "HTTP",
        "method": method,
        "name": name,
        "unSaved": True,
        "customizeRequest": False,
        "customizeRequestEnvEnable": True,
        "children": [common_child(pre=pre, post=post, assertions=assertions)],
        "executeLoading": False,
        "uploadFileIds": [],
        "linkFileIds": [],
        "deleteFileIds": [],
        "unLinkFileIds": [],
        "isNew": False,
    }
    return blob


def make_script_blob(script: str):
    return {
        "processorType": "SCRIPT",
        "enableCommonScript": False,
        "script": script,
        "scriptLanguage": "PYTHON",
        "commonScriptInfo": {},
        "polymorphicName": "MsScriptElement",
        "children": [{"polymorphicName": "MsCommonElement", "assertionConfig": {"assertions": []}}],
    }


def make_timer_step(step_id: str, scenario_id: str, parent_id: str, sort: int):
    return {
        "id": step_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": "CONSTANT_TIMER",
        "refType": "DIRECT",
        "config": {"id": "", "name": "", "enable": True, "delay": 5000},
        "csvIds": None,
        "projectId": "771977421840384",
        "name": "等待时间",
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": scenario_id,
        "sort": sort,
        "parentId": parent_id,
    }


def step_meta(step_id: str, scenario_id: str, sort: int, name: str, step_type: str = "CUSTOM_REQUEST", parent_id=None, method="POST"):
    return {
        "id": step_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": step_type,
        "refType": "DIRECT",
        "config": {"id": "", "name": "", "enable": True, "protocol": "HTTP", "method": method} if step_type == "CUSTOM_REQUEST" else {"id": "", "name": "", "enable": True},
        "csvIds": None,
        "projectId": "771977421840384",
        "name": name,
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": scenario_id,
        "sort": sort,
        "parentId": parent_id,
    }


def script_step_meta(step_id: str, scenario_id: str, sort: int, name: str):
    return {
        "id": step_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": "SCRIPT",
        "refType": "DIRECT",
        "config": {"id": "", "name": "", "enable": True},
        "csvIds": None,
        "projectId": "771977421840384",
        "name": name,
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": scenario_id,
        "sort": sort,
        "parentId": None,
    }


def loop_step_meta(step_id: str, scenario_id: str, sort: int, name: str, status_var: str, count_var: str):
    return {
        "id": step_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": "LOOP_CONTROLLER",
        "refType": "DIRECT",
        "config": {
            "id": "",
            "name": "",
            "enable": True,
            "loopType": "WHILE",
            "forEachController": {"loopTime": 0, "value": "", "variable": ""},
            "msCountController": {"loops": "1", "loopTime": 0},
            "whileController": {
                "conditionType": "SCRIPT",
                "timeout": 310000,
                "msWhileScript": {
                    "scriptValue": (
                        "${__groovy(!'SUBMITTED'.equals(vars.get('"
                        + status_var
                        + "')) && Integer.parseInt(vars.get('"
                        + count_var
                        + "') == null ? '0' : vars.get('"
                        + count_var
                        + "')) < 60)}"
                    )
                },
                "msWhileVariable": {"condition": "EQUALS", "value": "", "variable": ""},
            },
        },
        "csvIds": None,
        "projectId": "771977421840384",
        "name": name,
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": scenario_id,
        "sort": sort,
        "parentId": None,
    }


def clone_scenario1_step(source_data, source_sort):
    step = next(s for s in source_data["scenarioStepList"] if s.get("sort") == source_sort and s.get("parentId") is None)
    blob = json.loads(source_data["scenarioStepBlobMap"][str(step["id"])])
    return copy.deepcopy(step), copy.deepcopy(blob)


def prepare_cloned_step(step, blob, step_id: str, scenario_id: str, sort: int, name: str = None):
    step["id"] = step_id
    step["scenarioId"] = scenario_id
    step["sort"] = sort
    step["parentId"] = None
    step["resourceId"] = None
    step["originProjectId"] = None
    step["projectId"] = "771977421840384"
    step["refType"] = "DIRECT"
    step["resourceNum"] = None
    step["versionId"] = None
    step["uniqueId"] = None
    if name:
        step["name"] = name
        blob["name"] = name
    blob["resourceId"] = None
    blob["stepId"] = None
    blob["uniqueId"] = None
    return step, blob


def set_blob_json_value(blob, json_value: str):
    blob["body"]["bodyType"] = "JSON"
    blob["body"]["bodyClassByType"] = "io.metersphere.api.dto.request.http.body.JsonBody"
    blob["body"]["bodyDataByType"] = {"enableJsonSchema": False, "jsonValue": json_value, "jsonSchema": None}
    blob["body"]["jsonBody"]["enableJsonSchema"] = False
    blob["body"]["jsonBody"]["jsonValue"] = json_value


def ensure_http_defaults(blob, include_auth=True):
    blob["headers"] = standard_headers(include_auth=include_auth)
    blob["otherConfig"] = {
        "connectTimeout": 60000,
        "responseTimeout": 60000,
        "certificateAlias": "",
        "followRedirects": True,
        "autoRedirects": False,
    }
    blob["customizeRequest"] = False
    blob["customizeRequestEnvEnable"] = True


def main():
    source_data = load_json(SOURCE_SCENARIO)
    api_index = build_api_index(load_json(API_EXPORT))
    scenario_id = "fpusd2k" + str(int(time.time() * 1000))
    id_seed = int(time.time() * 1000)
    next_id = iter(range(id_seed, id_seed + 500))

    def new_id():
        return str(next(next_id))

    steps = []
    blob_map = {}

    # 1. send sms
    step, blob = clone_scenario1_step(source_data, 1)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 1)
    pre_processors = blob["children"][0]["preProcessorConfig"]["processors"]
    pre_processors[0]["script"] = (
        "import random\n\n"
        "prefixes = [\n"
        '    "130","131","132","133","135","136","137","138","139",\n'
        '    "150","151","152","155","156","157","158","159",\n'
        '    "166","171","172","173","175","176","177","178",\n'
        '    "180","181","182","183","184","185","186","187","188","189",\n'
        '    "191","193","195","196","198","199"\n'
        "]\n\n"
        "prefix = random.choice(prefixes)\n"
        "suffix = str(random.randint(0, 99999999)).zfill(8)\n"
        "phone_number = prefix + suffix\n"
        'email = phone_number + "@163.com"\n'
        'vars.put("phoneNumber", phone_number)\n'
        'vars.put("phone", phone_number)\n'
        'vars.put("email", email)\n'
        'log.info("===== 生成固定手机号: " + phone_number + " =====")\n'
        'log.info("===== 生成邮箱: " + email + " =====")'
    )
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 2. validate sms with DB query
    step, blob = clone_scenario1_step(source_data, 2)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 2)
    ensure_http_defaults(blob, include_auth=False)
    blob["children"][0]["assertionConfig"] = {"enableGlobal": False, "assertions": [code_200_assertion()]}
    sql_ds_id = blob["children"][0]["preProcessorConfig"]["processors"][0]["dataSourceId"]
    sql_ds_name = blob["children"][0]["preProcessorConfig"]["processors"][0]["dataSourceName"]
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 3. signup
    step, blob = clone_scenario1_step(source_data, 3)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 3)
    signup_body = json.loads(blob["body"]["bodyDataByType"]["jsonValue"])
    signup_body["code"] = "${verificationCode}"
    signup_body["email"] = "${email}"
    set_blob_json_value(blob, json.dumps(signup_body, ensure_ascii=False))
    ensure_http_defaults(blob, include_auth=False)
    blob["children"][0]["assertionConfig"] = {"enableGlobal": False, "assertions": [code_200_assertion()]}
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 4. choose FUNDPARK flow
    step, blob = clone_scenario1_step(source_data, 4)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 4)
    set_blob_json_value(blob, '{"funderCode":"FUNDPARK","currency":"USD"}')
    ensure_http_defaults(blob, include_auth=True)
    blob["children"][0]["assertionConfig"] = {"enableGlobal": False, "assertions": [code_200_assertion()]}
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 5. generate state
    step, blob = clone_scenario1_step(source_data, 6)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 5)
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 6. SP auth
    step, blob = clone_scenario1_step(source_data, 7)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 6)
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 7. generate 3PL offer id
    step_id = new_id()
    step = step_meta(step_id, scenario_id, 7, "生成3PL offerId", method="POST")
    blob = make_http_blob(
        name="生成3PL offerId",
        path="/dpu-merchant/mock/generate-shop-performance",
        method="POST",
        json_value='{"yearlyRepaymentAmount": 100000}',
        include_auth=False,
        post=[
            extract_processor("amazon3plOfferId", "$.data.amazon3plOfferId"),
            script_processor(
                'offer_id = vars.get("amazon3plOfferId")\n'
                'if offer_id is None or str(offer_id) == "":\n'
                '    raise Exception("未提取到 amazon3plOfferId")\n'
                'vars.put("offerId", str(offer_id))\n'
                'log.info("amazon3plOfferId=" + str(offer_id))',
                "提取3PL offerId",
            ),
        ],
        assertions=[code_200_assertion()],
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 8. GET redirect
    step_id = new_id()
    step = step_meta(step_id, scenario_id, 8, "3PL跳转授权-GET", method="GET")
    blob = make_http_blob(
        name="3PL跳转授权-GET",
        path="/dpu-merchant/amazon/redirect",
        method="GET",
        body_type="NONE",
        query=[{"key": "offerId", "value": "${amazon3plOfferId}", "enable": True, "description": "", "paramType": "string", "required": False, "encode": False, "notBlankValue": True, "valid": True}],
        include_auth=True,
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 9. POST redirect
    step_id = new_id()
    step = step_meta(step_id, scenario_id, 9, "3PL跳转授权-POST", method="POST")
    blob = make_http_blob(
        name="3PL跳转授权-POST",
        path="/dpu-merchant/amazon/redirect",
        method="POST",
        json_value='{"authToken":"mock","expireOn":"null","keyId":"null","offerId":"${amazon3plOfferId}","relayPage":1,"returnUrl":"null","signature":"null"}',
        include_auth=True,
        assertions=[code_200_assertion()],
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 10 create application
    step, blob = clone_scenario1_step(source_data, 10)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 10)
    ensure_http_defaults(blob, include_auth=True)
    blob["children"][0]["postProcessorConfig"] = {
        "enableGlobal": False,
        "processors": [
            extract_processor("dpuApplicationId", "$.data"),
            script_processor(
                'application_id = vars.get("dpuApplicationId")\n'
                'if application_id is None or str(application_id) == "":\n'
                '    raise Exception("未提取到 dpuApplicationId")\n'
                'log.info("dpuApplicationId=" + str(application_id))',
                "提取申请单ID",
            ),
        ],
    }
    blob["children"][0]["assertionConfig"] = {"enableGlobal": False, "assertions": [code_200_assertion()]}
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 11 business info
    step, blob = clone_scenario1_step(source_data, 11)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 11)
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 12 director info
    step, blob = clone_scenario1_step(source_data, 12)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 12)
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 13 select 2k amount
    step, blob = clone_scenario1_step(source_data, 13)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 13, "选择2k额度")
    set_blob_json_value(blob, '{"limitSelection": 2000}')
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 14 query final offer
    step, blob = clone_scenario1_step(source_data, 14)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 14)
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 15 activate offer
    step, blob = clone_scenario1_step(source_data, 15)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 15)
    blob["body"]["bodyType"] = "NONE"
    blob["body"]["bodyClassByType"] = "io.metersphere.api.dto.request.http.body.NoneBody"
    blob["body"]["bodyDataByType"] = {}
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 16 link shops
    step, blob = clone_scenario1_step(source_data, 16)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 16)
    ensure_http_defaults(blob, include_auth=True)
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 17-19 trigger tasks
    for source_sort, new_sort in [(17, 17), (18, 18), (19, 19)]:
        step, blob = clone_scenario1_step(source_data, source_sort)
        step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, new_sort)
        ensure_http_defaults(blob, include_auth=True)
        steps.append(step)
        blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 20 init credit-offer status
    step_id = new_id()
    step = script_step_meta(step_id, scenario_id, 20, "初始化credit offer状态")
    blob = make_script_blob(
        'vars.put("credit_offer_status", "INIT")\n'
        'vars.put("poll_count", "0")\n'
        'print("init credit_offer_status=INIT")\n'
        'print("init poll_count=0")'
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 21 credit-offer polling loop
    loop_id = new_id()
    steps.append(loop_step_meta(loop_id, scenario_id, 21, "轮询credit offer状态", "credit_offer_status", "poll_count"))

    poll_id = new_id()
    poll_step = step_meta(poll_id, scenario_id, 1, "轮询credit-offer-status", parent_id=loop_id, method="GET")
    poll_blob = make_http_blob(
        name="轮询credit-offer-status",
        path="/dpu-merchant/credit-offer/status",
        method="GET",
        body_type="NONE",
        include_auth=True,
        post=[
            script_processor(
                "import json\n\n"
                'body = prev.getResponseDataAsString()\n'
                "resp = json.loads(body)\n"
                'status = str(resp.get("data", {}).get("status", "")).strip()\n'
                'current_count = vars.get("poll_count")\n'
                'if current_count is None or current_count == "":\n'
                '    current_count = "0"\n'
                'poll_count = int(current_count) + 1\n'
                'vars.put("credit_offer_status", status)\n'
                'vars.put("poll_count", str(poll_count))\n'
                'print("credit_offer_status=" + status)\n'
                'print("poll_count=" + str(poll_count))',
                "更新credit-offer状态",
            )
        ],
        assertions=[code_200_assertion()],
    )
    steps.append(poll_step)
    blob_map[poll_id] = json.dumps(poll_blob, ensure_ascii=False)

    timer_id = new_id()
    steps.append(make_timer_step(timer_id, scenario_id, loop_id, 2))

    # 22 final credit-offer check
    step_id = new_id()
    step = script_step_meta(step_id, scenario_id, 22, "校验credit offer状态")
    blob = make_script_blob(
        'final_status = vars.get("credit_offer_status") or ""\n'
        'poll_count = vars.get("poll_count") or "0"\n'
        'print("final_status=" + final_status)\n'
        'print("poll_count=" + poll_count)\n'
        'if final_status != "SUBMITTED":\n'
        '    raise Exception("轮询结束，credit offer状态不是 SUBMITTED，当前值=" + final_status + "，共轮询 " + poll_count + " 次")'
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 23 approved-offer
    step, blob = clone_scenario1_step(source_data, 24)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 23)
    pre_processors = blob["children"][0]["preProcessorConfig"]["processors"]
    pre_processors[1]["script"] = pre_processors[1]["script"].replace('approved_amount = "500000"', 'approved_amount = "2000"')
    body_json = json.loads(blob["body"]["bodyDataByType"]["jsonValue"])
    body_json["data"]["details"]["offer"]["term"] = 12
    body_json["data"]["details"]["offer"]["termUnit"] = "Months"
    set_blob_json_value(blob, json.dumps(body_json, ensure_ascii=False))
    ensure_http_defaults(blob, include_auth=True)
    blob["children"][0]["assertionConfig"] = {"enableGlobal": False, "assertions": [code_200_assertion()]}
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 24 esign
    step, blob = clone_scenario1_step(source_data, 27)
    step, blob = prepare_cloned_step(step, blob, new_id(), scenario_id, 24)
    pre_processors = blob["children"][0]["preProcessorConfig"]["processors"]
    pre_processors[1]["script"] = pre_processors[1]["script"].replace('signed_amount = "500000"', 'signed_amount = "2000"')
    ensure_http_defaults(blob, include_auth=True)
    blob["children"][0]["assertionConfig"] = {"enableGlobal": False, "assertions": [code_200_assertion()]}
    steps.append(step)
    blob_map[step["id"]] = json.dumps(blob, ensure_ascii=False)

    # 25 init drawdown status
    step_id = new_id()
    step = script_step_meta(step_id, scenario_id, 25, "初始化drawdown状态")
    blob = make_script_blob(
        'vars.put("drawdown_status", "INIT")\n'
        'vars.put("drawdown_poll_count", "0")\n'
        'print("init drawdown_status=INIT")\n'
        'print("init drawdown_poll_count=0")'
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 26 drawdown polling loop
    loop_id = new_id()
    steps.append(loop_step_meta(loop_id, scenario_id, 26, "轮询drawdown状态", "drawdown_status", "drawdown_poll_count"))

    poll_id = new_id()
    poll_step = step_meta(poll_id, scenario_id, 1, "轮询drawdown-status", parent_id=loop_id, method="GET")
    poll_blob = make_http_blob(
        name="轮询drawdown-status",
        path="/dpu-merchant/drawdown/status",
        method="GET",
        body_type="NONE",
        include_auth=True,
        post=[
            script_processor(
                "import json\n\n"
                'body = prev.getResponseDataAsString()\n'
                "resp = json.loads(body)\n"
                'status = str(resp.get("data", {}).get("status", "")).strip()\n'
                'current_count = vars.get("drawdown_poll_count")\n'
                'if current_count is None or current_count == "":\n'
                '    current_count = "0"\n'
                'poll_count = int(current_count) + 1\n'
                'vars.put("drawdown_status", status)\n'
                'vars.put("drawdown_poll_count", str(poll_count))\n'
                'print("drawdown_status=" + status)\n'
                'print("drawdown_poll_count=" + str(poll_count))',
                "更新drawdown状态",
            )
        ],
        assertions=[code_200_assertion()],
    )
    steps.append(poll_step)
    blob_map[poll_id] = json.dumps(poll_blob, ensure_ascii=False)

    timer_id = new_id()
    steps.append(make_timer_step(timer_id, scenario_id, loop_id, 2))

    # 27 final drawdown check
    step_id = new_id()
    step = script_step_meta(step_id, scenario_id, 27, "校验drawdown状态")
    blob = make_script_blob(
        'final_status = vars.get("drawdown_status") or ""\n'
        'poll_count = vars.get("drawdown_poll_count") or "0"\n'
        'print("drawdown_final_status=" + final_status)\n'
        'print("drawdown_poll_count=" + poll_count)\n'
        'if final_status != "SUBMITTED":\n'
        '    raise Exception("轮询结束，drawdown状态不是 SUBMITTED，当前值=" + final_status + "，共轮询 " + poll_count + " 次")'
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(blob, ensure_ascii=False)

    # 28 disbursement.completed
    step_id = new_id()
    step = step_meta(step_id, scenario_id, 28, "disbursement-completed", method="POST")
    disbursement_blob = make_http_blob(
        name="disbursement-completed",
        path="/dpu-openapi/webhook-notifications",
        method="POST",
        json_value=json.dumps(
            {
                "data": {
                    "eventType": "disbursement.completed",
                    "eventId": "${eventId}",
                    "eventMessage": "Disbursement completed",
                    "enquiryUrl": "/loans?merchantId=${merchantId}&loanId=LEND1",
                    "datetime": "${datetime_utc}",
                    "details": {
                        "merchantId": "${merchantId}",
                        "lenderApprovedOfferId": "${lenderApprovedOfferId}",
                        "dpuLoanId": "${dpuLoanId}",
                        "lenderLoanId": "${lenderLoanId}",
                        "originalRequestId": "e37b91d056114e48a466b433934e2068",
                        "lenderCreditId": "CR1",
                        "lenderCompanyId": "LEND1",
                        "lenderDrawdownId": "DRA1",
                        "drawdownStatus": "APPROVED",
                        "lastUpdatedOn": "${lastUpdatedOn}",
                        "lastUpdatedBy": "system",
                        "disbursement": {
                            "loanAmount": {"currency": "${preferredCurrency}", "amount": "${disbursementAmount}"},
                            "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "6.00", "marginRate": "0.00"},
                            "term": "120",
                            "termUnit": "Days",
                            "drawdownSuccessDate": "${drawdownSuccessDate}",
                            "actualDrawdownDate": "${actualDrawdownDate}",
                        },
                        "repayment": {
                            "expectedRepaymentDate": "2026-06-21",
                            "expectedRepaymentAmount": {"currency": "${preferredCurrency}", "amount": "${disbursementAmount}"},
                            "repaymentTerm": "90",
                        },
                    },
                }
            },
            ensure_ascii=False,
        ),
        include_auth=True,
        pre=[
            sql_processor(
                "SELECT merchant_id FROM dpu_seller_center.dpu_users WHERE phone_number = '${phone}' ORDER BY created_at DESC LIMIT 1;",
                "merchantId",
                sql_ds_id,
                sql_ds_name,
            ),
            sql_processor(
                "SELECT COALESCE(prefer_finance_product_currency, 'USD') FROM dpu_seller_center.dpu_users WHERE phone_number = '${phone}' ORDER BY created_at DESC LIMIT 1;",
                "preferredCurrency",
                sql_ds_id,
                sql_ds_name,
            ),
            sql_processor(
                "SELECT application_unique_id FROM dpu_seller_center.dpu_application WHERE merchant_id = '${merchantId}' ORDER BY created_at DESC LIMIT 1;",
                "dpuApplicationId",
                sql_ds_id,
                sql_ds_name,
            ),
            sql_processor(
                "SELECT loan_id FROM dpu_seller_center.dpu_drawdown WHERE merchant_id = '${merchantId}' ORDER BY created_at DESC LIMIT 1;",
                "dpuLoanId",
                sql_ds_id,
                sql_ds_name,
            ),
            script_processor(
                "import re\n"
                "import uuid\n"
                "from datetime import datetime, timezone\n\n"
                "def clean(raw):\n"
                "    s = str(raw).strip()\n"
                "    if s in ('', 'None', '[]'):\n"
                "        return ''\n"
                "    m = re.search(r'=\\s*([^}\\]]+)', s)\n"
                "    return m.group(1).strip() if m else s\n\n"
                "merchant_id = clean(vars.get('merchantId'))\n"
                "preferred_currency = clean(vars.get('preferredCurrency')) or 'USD'\n"
                "application_id = clean(vars.get('dpuApplicationId'))\n"
                "loan_id = clean(vars.get('dpuLoanId'))\n"
                "if not merchant_id or not application_id or not loan_id:\n"
                "    raise Exception('disbursement 前置 SQL 结果不完整')\n"
                "vars.put('merchantId', merchant_id)\n"
                "vars.put('preferredCurrency', preferred_currency)\n"
                "vars.put('dpuApplicationId', application_id)\n"
                "vars.put('dpuLoanId', loan_id)\n"
                "vars.put('lenderApprovedOfferId', 'lender-' + application_id)\n"
                "vars.put('lenderLoanId', 'lender-' + loan_id)\n"
                "vars.put('disbursementAmount', '2000')\n"
                "vars.put('eventId', str(uuid.uuid4()))\n"
                "vars.put('datetime_utc', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))\n"
                "vars.put('lastUpdatedOn', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))\n"
                "vars.put('drawdownSuccessDate', datetime.now().strftime('%Y-%m-%d'))\n"
                "vars.put('actualDrawdownDate', datetime.now().strftime('%Y-%m-%d'))\n",
                "准备disbursement变量",
            ),
        ],
        assertions=[code_200_assertion()],
    )
    steps.append(step)
    blob_map[step_id] = json.dumps(disbursement_blob, ensure_ascii=False)

    scenario = {
        "id": scenario_id,
        "name": "线下FP-USD-2k",
        "priority": "P0",
        "status": "UNDERWAY",
        "stepTotal": 28,
        "requestPassRate": "0.00",
        "lastReportStatus": None,
        "lastReportId": None,
        "num": 100022,
        "deleted": False,
        "pos": 53249,
        "versionId": source_data["exportScenarioList"][0].get("versionId"),
        "refId": scenario_id,
        "latest": True,
        "projectId": source_data["projectId"],
        "moduleId": source_data["exportScenarioList"][0].get("moduleId"),
        "description": "线下 FP-USD 2k 完整链路场景：注册 -> 数据库取验证码 -> FUNDPARK -> SP/3PL -> 建单 -> 2k额度 -> credit-offer轮询 -> approved -> esign -> drawdown轮询 -> disbursement",
        "tags": ["offline", "fp", "usd", "2k"],
        "grouped": False,
        "environmentId": source_data["exportScenarioList"][0].get("environmentId"),
        "createUser": source_data["exportScenarioList"][0].get("createUser"),
        "createTime": int(time.time() * 1000),
        "deleteTime": None,
        "deleteUser": None,
        "updateUser": source_data["exportScenarioList"][0].get("updateUser"),
        "updateTime": int(time.time() * 1000),
        "modulePath": "/DPU产品流程",
        "scenarioConfig": {
            "variable": {"commonVariables": [], "csvVariables": []},
            "preProcessorConfig": {"enableGlobal": True, "processors": []},
            "postProcessorConfig": {"enableGlobal": True, "processors": []},
            "assertionConfig": {"assertions": []},
            "otherConfig": {
                "enableGlobalCookie": False,
                "enableCookieShare": False,
                "enableStepWait": False,
                "failureStrategy": "CONTINUE",
            },
        },
        "steps": [],
    }

    output = {
        "organizationId": source_data["organizationId"],
        "projectId": source_data["projectId"],
        "hasRelatedResource": False,
        "exportScenarioList": [scenario],
        "apiScenarioCsvList": [],
        "scenarioStepList": steps,
        "scenarioStepBlobMap": blob_map,
        "relatedApiDefinitions": [],
        "relatedApiTestCaseList": [],
        "relatedScenarioList": [],
    }
    dump_json(OUTPUT_SCENARIO, output)
    print(f"generated: {OUTPUT_SCENARIO}")


if __name__ == "__main__":
    main()
