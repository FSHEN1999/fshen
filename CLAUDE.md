# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based testing toolkit for the HSBC DPU (Digital Platform Unit) financing system. The project provides utilities for:

- **Account Registration**: Automated user registration with test data generation
- **Status Simulation**: Mock DPU workflow states (underwriting, approval, PSP, e-signature, drawdown, repayment)
- **Database Operations**: Direct MySQL database access for state verification and manipulation
- **UI Automation**: Selenium-based browser automation for end-to-end testing

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

- **[`mock_sit.py`](mock_sit.py)** - SIT environment mock service (ENV="sit")
- **[`mock_uat.py`](mock_uat.py)** - UAT environment mock service (ENV="uat")

Both scripts provide a CLI interface for triggering DPU state transitions. Key operations:

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
python mock_uat.py  # or mock_sit.py
```

### GUI Application

- **[`1.py`](1.py)** - Tkinter-based GUI wrapper around `mock_uat.py`

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
