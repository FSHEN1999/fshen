# -*- coding: utf-8 -*-
import requests, time, uuid, pymysql, json, sys
from datetime import datetime, timedelta, timezone

BASE_URL = 'https://dpu-gateway-reg.dowsure.com'
DB_CONFIG = {'host': '18.162.145.173', 'user': 'dpu_reg', 'password': 'r4asUYBX3R6LNdp', 'database': 'dpu_seller_center', 'port': 3307, 'charset': 'utf8mb4'}

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def wait_db(sql, desc, timeout=30):
    for _ in range(timeout // 2):
        result = query_db(sql)
        if result:
            return result
        time.sleep(2)
    raise Exception(f'Timeout: {desc}')

merchant_id = '93fcbae71c8b4ac1997c23a26fd434c9'
phone = '18464251967'

print('[Get new token]')
resp = requests.post(f'{BASE_URL}/dpu-user/auth/validateSmsCode-sign',
                    json={'areaCode': '+86', 'code': '666666', 'phone': phone},
                    headers={'content-type': 'application/json'}, timeout=30)
resp = requests.post(f'{BASE_URL}/dpu-user/auth/login',
                    json={'phone': phone, 'password': 'Aa11111111..', 'areaCode': '+86'},
                    headers={'content-type': 'application/json'}, timeout=30)
token = resp.json()['data']['token']
print(f'  Token: {token[:20]}...')

headers_auth = {
    'Authorization': f'Bearer {token}',
    'content-type': 'application/json',
    'finance-product': 'LINE_OF_CREDIT',
    'funder-resource': 'FUNDPARK',
    'product-currency': 'USD'
}

print('\n[Step 6] Create application')
requests.post(f'{BASE_URL}/dpu-merchant/fundpark-application/create',
             json={'tierCode': '2', 'tierSnapshotValue': 0},
             headers=headers_auth, timeout=30)
time.sleep(2)

result = wait_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1", 'application_id')
app_id = result['application_unique_id']
print(f'  Application ID: {app_id}')

result = wait_db(f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id='{merchant_id}' AND authorization_party='SP' LIMIT 1", 'authorization_id')
account_id = result['authorization_id']
print(f'  Account ID: {account_id}')

print('\n[Step 7] Create credit offer')
requests.post(f'{BASE_URL}/dpu-merchant/credit-offer/create', headers=headers_auth, timeout=30)
time.sleep(2)

print('\n[Step 8] Link SP-3PL shops')
requests.post(f'{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops', params={'phone': phone}, timeout=30)
time.sleep(2)

print('\n[Step 9] Wait for limit_application')
result = wait_db(f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id='{merchant_id}' LIMIT 1", 'limit_application_id', timeout=60)
limit_app_id = result['limit_application_unique_id']
print(f'  Limit Application ID: {limit_app_id}')

print('\n[Step 10] Send approved-offer webhook')
event_id = str(uuid.uuid4())
resp = requests.post(f'{BASE_URL}/dpu-openapi/webhook-notifications', json={
    'data': {
        'eventType': 'approvedoffer.completed',
        'eventId': event_id,
        'dateTime': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'details': {
            'merchantId': merchant_id,
            'dpuApplicationId': app_id,
            'lenderApprovedOfferId': f'lender-{app_id}',
            'originalRequestId': 'req_' + event_id.replace('-', ''),
            'offer': {
                'approvedLimit': {'amount': '500000', 'currency': 'USD'},
                'offerStartDate': datetime.now().strftime('%Y-%m-%d'),
                'offerEndDate': (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            }
        }
    }
}, timeout=30)
print(f'  Response: {resp.status_code}')
time.sleep(3)

result = wait_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' LIMIT 1", 'lender_approved_offer_id')
lender_offer_id = result['lender_approved_offer_id']
print(f'  Lender Approved Offer ID: {lender_offer_id}')

print('\n[Step 11] Send psp.verification.started webhook')
event_id = str(uuid.uuid4())
resp = requests.post(f'{BASE_URL}/dpu-openapi/webhook-notifications', json={
    'data': {
        'eventType': 'psp.verification.started',
        'eventId': event_id,
        'dateTime': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'details': {
            'merchantId': merchant_id,
            'merchantAccountId': account_id,
            'lenderApprovedOfferId': lender_offer_id,
            'result': 'PROCESSING'
        }
    }
}, timeout=30)
print(f'  Response: {resp.status_code}')
time.sleep(3)

print('\n[Step 12] Send psp.verification.completed webhook')
event_id = str(uuid.uuid4())
resp = requests.post(f'{BASE_URL}/dpu-openapi/webhook-notifications', json={
    'data': {
        'eventType': 'psp.verification.completed',
        'eventId': event_id,
        'dateTime': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'details': {
            'merchantId': merchant_id,
            'merchantAccountId': account_id,
            'lenderApprovedOfferId': lender_offer_id,
            'result': 'SUCCESS'
        }
    }
}, timeout=30)
print(f'  Response: {resp.status_code}')
time.sleep(3)

print('\n[Step 13] Send esign.completed webhook')
event_id = str(uuid.uuid4())
resp = requests.post(f'{BASE_URL}/dpu-openapi/webhook-notifications', json={
    'data': {
        'eventType': 'esign.completed',
        'eventId': event_id,
        'dateTime': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'details': {
            'merchantId': merchant_id,
            'lenderApprovedOfferId': lender_offer_id,
            'signedLimit': {'amount': '500000', 'currency': 'USD'},
            'result': 'SUCCESS'
        }
    }
}, timeout=30)
print(f'  Response: {resp.status_code}')
time.sleep(3)

print('\n[Verify final status]')
result = query_db(f"SELECT status, e_sign_status, approved_limit_amount, signed_limit_amount FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1")
print(f'  Status: {result["status"]}')
print(f'  E-sign Status: {result["e_sign_status"]}')
print(f'  Approved Amount: {result["approved_limit_amount"]}')
print(f'  Signed Amount: {result["signed_limit_amount"]}')

if result['e_sign_status'] == 'SUCCESS':
    print('\n=== SUCCESS! FP-USD E-SIGNATURE COMPLETED! ===')
    print(json.dumps({
        'phone': phone,
        'merchant_id': merchant_id,
        'application_id': app_id,
        'lender_approved_offer_id': lender_offer_id,
        'currency': 'USD',
        'amount': '500000',
        'status': result['e_sign_status']
    }, indent=2))
    sys.exit(0)
else:
    print(f'\nFailed: {result["e_sign_status"]}')
    sys.exit(1)
