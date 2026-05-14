# -*- coding: utf-8 -*-
"""Curated DPU knowledge for the mockapi AI assistant."""

DPU_KNOWLEDGE_SUMMARY = """
You are working inside the DPU mockapi project.

Core project facts:
- The main web entrypoint is mockapi/web/app.py.
- The FastAPI routes are split into system routes, register routes, mock routes, websocket routes, and AI routes.
- The execution layer for DPU business behavior is mockapi/mock_sit.py and mockapi/web/services/mock_adapter.py.
- Session state is maintained by session_id via mockapi/web/services/session_manager.py.

Supported environments:
- sit, uat, dev, preprod, reg, local

Registration facts:
- Journey values are 200K, 500K, 2000K.
- Currency values are USD and CNY.
- Offline means line-offline registration flow.
- Register endpoint is POST /api/register.
- Connect endpoint is POST /api/connect.

Important database facts:
- The user table is dpu_users, not dpu_user.
- Merchant lookup by phone uses:
  SELECT merchant_id FROM dpu_users WHERE phone_number = ? ORDER BY created_at DESC LIMIT 1
- Preferred currency lookup uses:
  SELECT prefer_finance_product_currency FROM dpu_users WHERE merchant_id = ? LIMIT 1
- Do not guess table names when a fixed table is known.

High-value project conventions:
- If the user asks for merchant id by phone, use the fixed merchant lookup tool instead of generating free-form SQL.
- If the user asks to create an account and has not provided journey, currency, funder, or online/offline mode, ask for the missing fields first.
- If the UI provides a selected execution environment, that environment must win over any default or session fallback.

Mock action map:
- underwritten
- approved_offer
- psp_start
- psp_completed
- esign
- drawdown
- repayment_start
- repayment
- multi_shop_binding
- sp_status_update
- multi_shop_3pl_redirect
- system_event
- psp_hsbc_start
- psp_hsbc_completed
"""

