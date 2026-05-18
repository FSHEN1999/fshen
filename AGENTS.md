# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based testing toolkit for the HSBC DPU (Digital Platform Unit) financing system. The project provides utilities for:

- **Account Registration**: Automated user registration with test data generation
- **Status Simulation**: Mock DPU workflow states (underwriting, approval, PSP, e-signature, drawdown, repayment)
- **Database Operations**: Direct MySQL database access for state verification and manipulation
- **UI Automation**: Selenium-based browser automation for end-to-end testing

## Design Guidance

When changing any DPU-facing UI, generated HTML report, dashboard, or user-visible tool surface, read [`DESIGN.md`](DESIGN.md) first.

For the Mock API Vue frontend, also read [`mockapi/frontend/DESIGN.md`](mockapi/frontend/DESIGN.md) before editing `mockapi/frontend/src/App.vue`, `mockapi/frontend/src/style.css`, or related frontend assets.

These design files adapt the useful `awesome-design-md` pattern into local DPU rules: dense operational screens, explicit environment/session/status context, readable logs and payloads, and restrained financial-tool styling. Do not copy public brand identities directly into DPU tools.

## Environment Setup

### Python Environment

This project uses Python 3.12 with a virtual environment at `.venv/`. Activate it:

```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

Core dependencies:
- `PyMySQL` - MySQL database connectivity
- `requests` - HTTP client for API calls
- `Faker` - Test data generation
- `selenium` - Browser automation (for UI automation scripts)

## Supported Environments

The codebase supports multiple environments, configured via the `ENV` variable in each script:

- **sit** - System Integration Testing
- **uat** - User Acceptance Testing
- **dev** - Development
- **preprod** - Pre-production
- **local** - Local development

Database configurations are defined in `DatabaseConfig._DATABASE_CONFIG` within each mock script.

## Core Scripts

### Mock Services (Status Simulation)

- **[`mock_sit.py`](mock_sit.py)** - Unified mock service for all supported environments, including SIT and UAT

This script provides a CLI interface for triggering DPU state transitions. Key operations:

1. **Account Registration** - Generates phone numbers, emails, offer IDs
2. **SP API Authorization** - Mocks Selling Partner API callbacks
3. **Underwriting** - Simulates credit assessment (APPROVED/REJECTED)
4. **Approval** - Offer approval with amount and status
5. **PSP Verification** - Payment service provider verification (start/completed)
6. **E-signature** - Electronic contract signing
7. **Drawdown** - Loan disbursement (APPROVED/REJECTED with failure reasons)
8. **Repayment** - Repayment processing (Start/Success/Failure)

**Run command:**
```bash
python mock_sit.py
```

### GUI Application

- **[`1.py`](1.py)** - Tkinter-based GUI wrapper around the unified `mock_sit.py` flow

Provides a graphical interface for all mock operations with environment switching and connection management.

**Run command:**
```bash
python 1.py
```

### Registration Scripts

- **[`2.py`](2.py)** - Standalone registration utility
- **[`ui自动化到3PL.py`](ui自动化到3PL.py)** - Selenium-based UI automation for full registration flow through 3PL linking

**Run command:**
```bash
python 2.py
python uat uat ui自动化到3PL.py
```

## Architecture

### Database Layer

All database operations go through `DatabaseExecutor` class:

- **Connection Management**: Automatic reconnection on timeout (errors 2006, 2013, 10054)
- **Query Methods**: `execute_sql()` for single values, `execute_query()` for dictionaries
- **Context Manager**: Supports `with` statements for automatic cleanup

```python
with DatabaseExecutor(env="uat") as db:
    merchant_id = db.execute_sql("SELECT merchant_id FROM dpu_users WHERE phone_number='...'")
```

### Service Layer

`DPUMockService` class encapsulates business logic:

- **Properties**: Auto-fetch frequently used IDs (`merchant_account_id`, `application_unique_id`, etc.)
- **Webhook Sender**: `_send_webhook_request()` handles all webhook notifications
- **Input Validation**: Uses `input_with_validation()` for robust user input

### API Configuration

`ApiConfig` dataclass centralizes endpoint URLs. Base URLs differ by environment:

- UAT/Preprod: `https://uat.api.expressfinance.business.hsbc.com`
- SIT/Dev: `https://dpu-gateway-{env}.dowsure.com`

### State Enums

Critical enums for workflow states:

- `DPUStatus` - APPROVED, REJECTED, SUCCESS, FAIL, PROCESSING, INITIAL
- `RepaymentStatus` - Success, Failure, Start
- `DrawdownFailureReason` - ER001-ER005 for different failure scenarios
- `ReturnedFailureReason` - Approval return reasons

## Key Data Flow

### Registration Flow

1. **Create Offer ID**: POST to `/dpu-merchant/mock/generate-shop-performance` with `yearlyRepaymentAmount`
2. **Validate SMS**: POST to `/dpu-user/auth/validateSmsCode-sign` (code="666666")
3. **Signup**: POST to `/dpu-user/auth/signup` with phone, email, offerId, password
4. **Access Redirect**: GET the redirect URL to activate the offer

### Mock Operation Flow

1. User enters phone number (or registers new account)
2. Service fetches `merchant_id` from `dpu_users` table
3. User selects operation from menu
4. Service builds webhook payload with event type and details
5. POST to `/dpu-openapi/webhook-notifications`
6. System processes state change

## Important Notes

### Repayment ID Caching

The repayment system uses a cached `lender_repayment_id` to ensure continuity between `repayment_start` and `repayment` operations. The cache is automatically cleared after successful repayment completion.

### Multi-Shop Workflow

For multi-shop scenarios:
1. **SP Shop Binding** (`mock_multi_shop_binding`): Generates `selling_partner_id` and outputs auth URL
2. **3PL Redirect** (`mock_multi_shop_3pl_redirect`): Fetches `platform_offer_id` and outputs redirect URL

### Phone Number Validation

The system validates phone numbers as 8 or 11 digits only. Test phone numbers are generated using Faker.

### Verification Code

All test environments use the fixed verification code: `666666`

### Password

Default test password: `Aa11111111..`

## File Output

Registration operations append to environment-specific log files:
- `register_sit.txt` - SIT registrations
- `register_uat.txt` - UAT registrations
- `register_dev.txt` - Dev registrations

Format: journey type, phone number, redirect URL

## Daily Task Loop

For day-to-day execution tracking in this repository, use [`daily_tasks.md`](daily_tasks.md) instead of `dpu模拟需求文档.docx`.

- Treat `dpu模拟需求文档.docx` as a requirement/design source document, not as the daily checklist file.
- When the user asks to "继续任务", "继续完成我的任务", or otherwise continue the queued work, read `daily_tasks.md` first.
- Under the newest date section, execute the first unchecked item in order.
- After a task is completed, change `- [ ]` to `- [x]`.
- If a task is blocked, do not tick it. Add a short blocker note directly below that item and stop there.
- Only move on to the next unchecked item when the current one is actually finished.
- Keep task items short and action-oriented so they can be executed and checked off cleanly.

## Run Repair Loop

When running real automation in this repository:

- If logs show `ERROR`, `致命错误`, `Stacktrace`, or a screenshot-save message, stop waiting immediately.
- Read the latest run log and inspect the newest error screenshot before doing anything else.
- Treat the first concrete runtime failure as the active task: record it, patch the smallest reliable fix, rerun, and only then continue the flow.
- Do not leave a long-running process idle once a real failure is already visible in the logs.



prod注意事项：bacth1，3 替换migration_data为生成真实客户json内容，配置migration_test_FP_json batch1的生存环境数据库，执行完毕migration脚本执行export_migration_json脚本（同样需要配置生产数据库），控制台输入手机号，得到需要回传FP的json。   
             batch 2 替换migration_data为生成真实客户json内容（只配置用户的第一家店铺），配置migration_test_FP_json batch1.py的生存环境数据库，执行完毕migration脚本执行export_migration_json脚本（同样需要配置生产数据库），控制台输入手机号，得到需要回传FP的json。用户完成剩余店铺SP/3P通知我们后，替换migration_data多店铺为生成真实客户json内容，配置migration_test_FP_json 多店铺绑定psp.py的生存环境数据库，执行migration_test_FP_json 多店铺绑定psp.py
