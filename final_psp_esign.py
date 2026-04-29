# -*- coding: utf-8 -*-
import requests, time, uuid, pymysql, json, sys
from datetime import datetime, timezone

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

merchant_id = '81704c8252974fc180443865bff2f9d4'
app_id = 'EFA17773874393456472'
account_id = '6CFC3187B944436129B3EB96260CFA59'
lender_offer_id = f'lender-{app_id}'

print('[Step 17] PSP Start Webhook')
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
time.sleep(2)

print('\n[Step 18] PSP Completed Webhook')
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
time.sleep(2)

print('\n[Step 19] E-signature Webhook')
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

print('\n[Verify Final Status]')
result = query_db(f"SELECT status, e_sign_status, approved_limit_amount, signed_limit_amount FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1")
print(f'  Status: {result["status"]}')
print(f'  E-sign Status: {result["e_sign_status"]}')
print(f'  Approved Amount: {result["approved_limit_amount"]}')
print(f'  Signed Amount: {result["signed_limit_amount"]}')

if result['e_sign_status'] == 'SUCCESS':
    print('\n=== SUCCESS! FP-USD-500k E-SIGNATURE COMPLETED! ===')
    print(json.dumps({
        'phone': '18518954244',
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
