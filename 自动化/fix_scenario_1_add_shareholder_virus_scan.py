#!/usr/bin/env python
"""
Add missing steps after 邓白氏提交企业信息 (step 10):
- Step 10.5: 提交股东信息 (POST)
- Step 10.6: 病毒扫描1 (GET)
- Step 10.7: 病毒扫描2 (GET)

Then renumber all subsequent steps.
"""
import json
import sys

def main():
    with open('scenario_1.ms', 'r', encoding='utf-8') as f:
        data = json.load(f)

    steps = data['scenarioStepList']
    blobs = data['scenarioStepBlobMap']

    # Find step 10 (邓白氏提交企业信息)
    step_10_idx = next(i for i, s in enumerate(steps) if s['sort'] == 10)
    step_10 = steps[step_10_idx]

    print(f"Found step 10: {step_10['name']} at index {step_10_idx}")

    # Get the blob for step 10 to understand the structure
    step_10_blob_key = step_10['id']
    if step_10_blob_key in blobs:
        step_10_blob = blobs[step_10_blob_key]
        if isinstance(step_10_blob, dict):
            print(f"Step 10 blob keys: {list(step_10_blob.keys())}")
        else:
            print(f"Step 10 blob is a string (length: {len(step_10_blob)})")

    # Create new step IDs (use timestamp-based unique IDs)
    import time
    timestamp = int(time.time() * 1000)
    shareholder_id = str(timestamp)
    virus_scan_1_id = str(timestamp + 1)
    virus_scan_2_id = str(timestamp + 2)

    # Create shareholder submission step (POST)
    shareholder_step = {
        "id": shareholder_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": "CUSTOM_REQUEST",
        "refType": "DIRECT",
        "config": {
            "id": "",
            "name": "",
            "enable": True,
            "protocol": "HTTP",
            "method": "POST"
        },
        "csvIds": None,
        "projectId": step_10['projectId'],
        "name": "提交股东信息",
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": step_10['scenarioId'],
        "sort": 11,
        "parentId": None
    }

    # Create virus scan step 1 (GET)
    virus_scan_1_step = {
        "id": virus_scan_1_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": "CUSTOM_REQUEST",
        "refType": "DIRECT",
        "config": {
            "id": "",
            "name": "",
            "enable": True,
            "protocol": "HTTP",
            "method": "GET"
        },
        "csvIds": None,
        "projectId": step_10['projectId'],
        "name": "病毒扫描-股东信息1",
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": step_10['scenarioId'],
        "sort": 12,
        "parentId": None
    }

    # Create virus scan step 2 (GET)
    virus_scan_2_step = {
        "id": virus_scan_2_id,
        "enable": True,
        "resourceId": None,
        "originProjectId": None,
        "stepType": "CUSTOM_REQUEST",
        "refType": "DIRECT",
        "config": {
            "id": "",
            "name": "",
            "enable": True,
            "protocol": "HTTP",
            "method": "GET"
        },
        "csvIds": None,
        "projectId": step_10['projectId'],
        "name": "病毒扫描-股东信息2",
        "resourceNum": None,
        "versionId": None,
        "children": None,
        "uniqueId": None,
        "scenarioId": step_10['scenarioId'],
        "sort": 13,
        "parentId": None
    }

    # Insert new steps after step 10
    steps.insert(step_10_idx + 1, shareholder_step)
    steps.insert(step_10_idx + 2, virus_scan_1_step)
    steps.insert(step_10_idx + 3, virus_scan_2_step)

    # Renumber all steps after the new ones
    for i in range(step_10_idx + 4, len(steps)):
        steps[i]['sort'] += 3

    # Create blob entries for new steps (minimal structure)
    blobs[shareholder_id] = {
        "request": {
            "url": {
                "protocol": "HTTP",
                "host": "{{BASE_URL}}",
                "path": "/dpu-merchant/fp/shareholder/submit",
                "query": []
            },
            "method": "POST",
            "headers": [
                {"key": "Authorization", "value": "Bearer {{access_token}}"},
                {"key": "Content-Type", "value": "application/json"}
            ],
            "body": {
                "type": "JSON",
                "jsonBody": {
                    "jsonValue": json.dumps({
                        "shareholderList": [
                            {
                                "shareholderName": "{{faker_en_name}}",
                                "shareholderIdType": "PASSPORT",
                                "shareholderIdNumber": "{{faker_passport}}",
                                "shareholderIdFrontUrl": "{{director1_front_file_url}}",
                                "shareholderIdBackUrl": "{{director1_back_file_url}}",
                                "shareholderPercentage": 100
                            }
                        ]
                    }, ensure_ascii=False)
                }
            }
        },
        "assertions": [
            {
                "type": "RESPONSE_CODE",
                "operator": "EQUALS",
                "target": "200"
            },
            {
                "type": "JSON_PATH",
                "expression": "$.code",
                "operator": "EQUALS",
                "target": "0"
            }
        ]
    }

    blobs[virus_scan_1_id] = {
        "request": {
            "url": {
                "protocol": "HTTP",
                "host": "{{BASE_URL}}",
                "path": "/dpu-merchant/fp/file/scan-result",
                "query": [
                    {"key": "fileUrl", "value": "{{director1_front_file_url}}"}
                ]
            },
            "method": "GET",
            "headers": [
                {"key": "Authorization", "value": "Bearer {{access_token}}"}
            ]
        },
        "assertions": [
            {
                "type": "RESPONSE_CODE",
                "operator": "EQUALS",
                "target": "200"
            },
            {
                "type": "JSON_PATH",
                "expression": "$.code",
                "operator": "EQUALS",
                "target": "0"
            }
        ]
    }

    blobs[virus_scan_2_id] = {
        "request": {
            "url": {
                "protocol": "HTTP",
                "host": "{{BASE_URL}}",
                "path": "/dpu-merchant/fp/file/scan-result",
                "query": [
                    {"key": "fileUrl", "value": "{{director1_back_file_url}}"}
                ]
            },
            "method": "GET",
            "headers": [
                {"key": "Authorization", "value": "Bearer {{access_token}}"}
            ]
        },
        "assertions": [
            {
                "type": "RESPONSE_CODE",
                "operator": "EQUALS",
                "target": "200"
            },
            {
                "type": "JSON_PATH",
                "expression": "$.code",
                "operator": "EQUALS",
                "target": "0"
            }
        ]
    }

    # Save updated scenario
    with open('scenario_1.ms', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Added 3 new steps after step 10:")
    print(f"  - Step 11: 提交股东信息 (POST)")
    print(f"  - Step 12: 病毒扫描-股东信息1 (GET)")
    print(f"  - Step 13: 病毒扫描-股东信息2 (GET)")
    print(f"\n[OK] Renumbered all subsequent steps (+3)")
    print(f"\nNew step sequence:")
    for step in steps[step_10_idx:step_10_idx+8]:
        print(f"  Sort {step['sort']}: {step['name']}")

if __name__ == '__main__':
    main()
