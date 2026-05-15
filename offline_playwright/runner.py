# -*- coding: utf-8 -*-
"""Command-line runner for the Playwright REG offline clean flow."""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from offline_playwright.db import DatabaseExecutor, FinalApplyState
from offline_playwright.pages import (
    BasePage,
    CompanyInfoPage,
    DirectorInfoPage,
    FinalApplyPage,
    FinancingChoicePage,
    RegistrationFlow,
)
from offline_playwright.settings import RunnerSettings, build_settings, configure_playwright_browser_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DPU offline Playwright clean runner")
    parser.add_argument("--env", default="reg", help="Environment: reg/sit/uat/dev/preprod/local")
    parser.add_argument("--headed", action="store_true", help="Run browser headed")
    parser.add_argument(
        "--debug-visible",
        action="store_true",
        help="Shortcut for visible step-by-step debugging: headed, slow motion, and pause before closing",
    )
    parser.add_argument("--phone", default="auto", help="Phone number or 'auto'")
    parser.add_argument(
        "--stop-after",
        default="none",
        choices=["financing", "final_apply", "none"],
        help="Stop after a milestone for debugging",
    )
    parser.add_argument("--slow-mo", type=int, default=0, help="Playwright slow_mo in milliseconds")
    parser.add_argument(
        "--pause-on-exit",
        action="store_true",
        help="Keep the browser window open until Enter is pressed before closing",
    )
    return parser.parse_args()


def setup_logging(artifact_dir: Path) -> None:
    log_file = artifact_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    logging.info("[ARTIFACT] log file: %s", log_file)


def generate_phone() -> str:
    return f"182{random.randint(10000000, 99999999)}"


def open_sp_authorization(settings: RunnerSettings, page, state: FinalApplyState) -> str:
    selling_partner_id = f"spshouquanfs{state.phone}"
    sp_auth_url = f"{settings.base_url}/dpu-auth/amazon-sp/auth"
    params = {
        "state": state.authorization_state,
        "selling_partner_id": selling_partner_id,
        "mws_auth_token": "1235",
        "spapi_oauth_code": "123123",
    }
    auth_url = f"{sp_auth_url}?{urlencode(params)}"
    logging.info("[AUTH] opening SP authorization URL: %s", auth_url)
    with page.context.expect_page() as new_page_info:
        page.evaluate("url => window.open(url, '_blank')", auth_url)
    auth_page = new_page_info.value
    auth_page.wait_for_load_state("domcontentloaded")
    page.bring_to_front()
    page.wait_for_timeout(1_000)
    return selling_partner_id


def simulate_sp_authorization_from_state(
    settings: RunnerSettings,
    page,
    phone: str,
    state_value: str,
) -> str:
    selling_partner_id = f"spshouquanfs{phone}"
    sp_auth_url = f"{settings.base_url}/dpu-auth/amazon-sp/auth"
    params = {
        "state": state_value,
        "selling_partner_id": selling_partner_id,
        "mws_auth_token": "1235",
        "spapi_oauth_code": "123123",
    }
    auth_url = f"{sp_auth_url}?{urlencode(params)}"
    logging.info("[AUTH] simulating SP authorization URL from captured state: %s", auth_url)
    with page.context.expect_page() as new_page_info:
        page.evaluate("url => window.open(url, '_blank')", auth_url)
    auth_page = new_page_info.value
    auth_page.wait_for_load_state("domcontentloaded")
    page.bring_to_front()
    page.wait_for_timeout(2_000)
    return selling_partner_id


def send_update_offer(
    settings: RunnerSettings,
    idempotency_key: str,
    platform_offer_id: str,
) -> bool:
    url = f"{settings.base_url}/dpu-auth/amazon-sp/updateOffer"
    payload = {
        "idempotencyKey": idempotency_key,
        "sendStatus": "SUCCESS",
        "offerId": platform_offer_id,
        "reason": "",
    }
    logging.info("[API] POST %s payload=%s", url, payload)
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        logging.info("[API] updateOffer success: %s", response.text[:200])
        return True
    logging.warning("[API] updateOffer failed status=%s body=%s", response.status_code, response.text[:500])
    return False


def open_3pl_redirect(settings: RunnerSettings, page, platform_offer_id: str) -> str:
    redirect_url = f"{settings.base_url}/dpu-merchant/amazon/redirect?offerId={platform_offer_id}"
    logging.info("[REDIRECT] opening 3PL redirect URL: %s", redirect_url)
    with page.context.expect_page() as new_page_info:
        page.evaluate("url => window.open(url, '_blank')", redirect_url)
    redirect_page = new_page_info.value
    redirect_page.wait_for_load_state("domcontentloaded")
    redirect_page.close()
    return redirect_url


def complete_3pl_authorization(settings: RunnerSettings, platform_offer_id: str) -> bool:
    url = f"{settings.base_url}/dpu-merchant/amazon/redirect"
    payload = {
        "authToken": "mock",
        "expireOn": "null",
        "keyId": "null",
        "offerId": platform_offer_id,
        "relayPage": 1,
        "returnUrl": "null",
        "signature": "null",
    }
    logging.info("[API] POST %s payload=%s", url, payload)
    response = requests.post(url, json=payload, timeout=60)
    if response.status_code == 200:
        logging.info("[API] 3PL auth success: %s", response.text[:200])
        return True
    logging.warning("[API] 3PL auth failed status=%s body=%s", response.status_code, response.text[:500])
    return False


def submit_fundpark_business_info(
    settings: RunnerSettings,
    token: str,
    preferred_currency: str,
) -> bool:
    url = f"{settings.base_url}/dpu-merchant/fundpark-application/business-info"
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": preferred_currency,
        "origin": "https://expressfinance-dpu-reg.dowsure.com",
        "referer": "https://expressfinance-dpu-reg.dowsure.com/",
        "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        "x-hsbc-request-correlation-id": "",
        "x-hsbc-request-idempotency-key": "",
    }
    payload = {
        "step": "2",
        "isDraft": False,
        "data": {
            "bizDetail": {
                "id": None,
                "applicationId": None,
                "enName": "",
                "cnName": "测试有限公司",
                "regNo": "91330201MA2AFFT07Q",
                "companyDate": None,
                "country": None,
                "countryCode": None,
                "area": None,
                "areaCode": None,
                "address": None,
                "mailAddressFlag": None,
                "mailArea": None,
                "mailAreaCode": None,
                "mailCountry": None,
                "mailCountryCode": None,
                "mailOfficeAddress1": None,
                "relationshipHsbcGroupFlag": None,
                "relationshipHsbcGroupCountry": None,
                "relationshipHsbcGroupCountryCode": None,
                "companyType": None,
                "registeredCountryCode": None,
            },
            "bizInfo": {
                "topBuyers": ["China", "Hong Kong", "Macao"],
                "topSuppliers": ["China"],
                "fundingCountry": "China",
                "industry": "Furniture",
                "mainProducts": "Home Improvement",
                "initWealth": ["savings"],
                "fundSources": ["bizOperations"],
                "ongoingWealth": ["operationProfit"],
            },
        },
        "clear": True,
    }
    logging.info("[API] POST %s payload=%s", url, payload)
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    logging.info("[API] business-info status=%s body=%s", response.status_code, response.text[:300])
    return response.status_code == 200


def submit_fundpark_director_info(
    settings: RunnerSettings,
    token: str,
    phone: str,
    preferred_currency: str,
) -> bool:
    url = f"{settings.base_url}/dpu-merchant/fundpark-application/director-info"
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": preferred_currency,
        "origin": "https://expressfinance-dpu-reg.dowsure.com",
        "referer": "https://expressfinance-dpu-reg.dowsure.com/",
        "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        "x-hsbc-request-correlation-id": "",
        "x-hsbc-request-idempotency-key": "",
    }
    payload = {
        "step": "2",
        "isDraft": False,
        "data": {
            "persons": [
                {
                    "id": "3007b39fd76244a3be835fb843abad49",
                    "businessKey": None,
                    "equityRatio": 0,
                    "position": "DIRECTOR_AND_LEGAL_REPRESENTATIVE",
                    "roles": [],
                    "nameCn": "季剑明",
                    "nameEn": "Jianming Ji",
                    "firstChiName": None,
                    "lastChiName": None,
                    "frontDocName": "身份证正面.png",
                    "backDocName": "身份证反面.png",
                    "idDocumentType": "PRC_RESIDENT_ID_CARD",
                    "idDocumentFrontUrl": "uploads/default/default/default/file_20260507113138_0c321ca9078d.png",
                    "idDocumentBackUrl": "uploads/default/default/default/file_20260507113141_b75aed787968.png",
                    "idDocumentFrontFile": None,
                    "idDocumentBackFile": None,
                    "dateOfBirth": "30/12/2025",
                    "nationality": "中国",
                    "mobileNumber": {"countryCode": "+86", "number": phone},
                    "emailAddress": f"{phone}@qq.com",
                    "countryAndRegion": "",
                    "adressLine": "",
                    "secAdressLine": "",
                    "city": "",
                    "postalCode": "",
                    "percentageOfShares": 0,
                    "idFrontFlag": True,
                    "idBackFlag": True,
                    "addStatus": "API",
                    "hsbcPersonInfoExtend": None,
                    "guarantorList": None,
                    "mobileNumber.number": phone,
                }
            ]
        },
    }
    logging.info("[API] POST %s payload=%s", url, payload)
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    logging.info("[API] director-info status=%s body=%s", response.status_code, response.text[:300])
    return response.status_code == 200


def link_sp_3pl(settings: RunnerSettings, phone: str) -> None:
    url = f"{settings.base_url}/dpu-merchant/mock/link-sp-3pl-shops?phone={phone}"
    logging.info("[API] POST %s", url)
    response = requests.post(url, headers={"Content-Type": "application/json"}, timeout=30)
    if response.status_code == 200:
        logging.info("[API] link-sp-3pl-shops success: %s", response.text[:200])
    else:
        logging.warning("[API] link-sp-3pl-shops failed status=%s body=%s", response.status_code, response.text[:500])


def wait_before_browser_close(enabled: bool) -> None:
    if not enabled:
        return
    logging.info("[DEBUG] Browser is still open. Press Enter in this console to close it.")
    try:
        input("Browser is still open. Press Enter to close it...")
    except EOFError:
        logging.info("[DEBUG] stdin is not interactive; closing browser now.")


def run_flow(
    settings: RunnerSettings,
    phone: str,
    headed: bool,
    stop_after: str,
    slow_mo: int,
    pause_on_exit: bool,
) -> int:
    configure_playwright_browser_path()
    from playwright.sync_api import sync_playwright

    with DatabaseExecutor(settings.database) as db:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not headed, slow_mo=slow_mo)
            context = browser.new_context(
                viewport={"width": 1440, "height": 960},
                record_video_dir=str(settings.artifact_dir / "videos"),
            )
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            page.set_default_timeout(settings.wait_timeout_ms)

            try:
                logging.info(
                    "[RUN] env=%s phone=%s headed=%s slow_mo=%sms pause_on_exit=%s",
                    settings.env,
                    phone,
                    headed,
                    slow_mo,
                    pause_on_exit,
                )
                registration = RegistrationFlow(page, settings)
                registration.open()
                registration.start_application()
                registration.fill_registration(
                    phone,
                    lambda: db.wait_for_sms_code(phone, settings.default_sms_code),
                )
                registration.fill_password_setup(phone)
                auth_token = registration.read_browser_token()
                logging.info("[RUN] browser token captured=%s", bool(auth_token))

                final_apply = FinalApplyPage(page, settings)
                final_apply.click_final_apply()
                state = db.wait_for_sp_auth_state(phone, attempts=22, interval=1.0)
                if not state:
                    raise RuntimeError(f"Final apply did not create SP authorization state for phone={phone}")

                logging.info("[ASSERT] final apply DB state confirmed: %s", state)
                if stop_after == "final_apply":
                    return 0

                open_sp_authorization(settings, page, state)
                final_apply_page = FinalApplyPage(page, settings)
                post_auth_result = final_apply_page.click_offer_apply_if_visible()
                captured_state = post_auth_result.get("state", "")
                if captured_state:
                    simulate_sp_authorization_from_state(settings, page, phone, captured_state)
                    final_apply_page.dismiss_sp_api_modal_if_visible()

                selling_partner_id = f"spshouquanfs{phone}"
                idempotency_key = db.get_idempotency_key(selling_partner_id)
                platform_offer_id = db.get_platform_offer_id(selling_partner_id)
                if not idempotency_key or not platform_offer_id:
                    raise RuntimeError(
                        f"Missing updateOffer prerequisites after SP authorization: idempotency_key={bool(idempotency_key)} "
                        f"platform_offer_id={bool(platform_offer_id)}"
                    )

                if not send_update_offer(settings, idempotency_key, platform_offer_id):
                    raise RuntimeError("updateOffer request failed after simulated SP authorization")
                send_status = db.wait_for_send_status(selling_partner_id, attempts=20, interval=2.0)
                if send_status != "SUCCESS":
                    raise RuntimeError(f"send_status did not become SUCCESS: {send_status}")

                open_3pl_redirect(settings, page, platform_offer_id)
                if not complete_3pl_authorization(settings, platform_offer_id):
                    raise RuntimeError("3PL authorization POST failed after redirect")

                browser_api = BasePage(page, settings)
                api_token = browser_api.read_browser_auth_token()
                if not api_token:
                    raise RuntimeError("Missing browser auth token before fundpark-application/create")

                create_headers = {
                    "Authorization": f"Bearer {api_token}",
                    "content-type": "application/json",
                    "finance-product": "LINE_OF_CREDIT",
                    "funder-resource": "FUNDPARK",
                    "product-currency": state.preferred_currency,
                    "origin": "https://expressfinance-dpu-reg.dowsure.com",
                    "referer": "https://expressfinance-dpu-reg.dowsure.com/",
                }
                create_payload = {"tierCode": "2", "tierSnapshotValue": 0}
                create_url = f"{settings.base_url}/dpu-merchant/fundpark-application/create"
                logging.info("[API] POST %s payload=%s", create_url, create_payload)
                create_response = requests.post(create_url, json=create_payload, headers=create_headers, timeout=30)
                logging.info("[API] fundpark-application/create status=%s body=%s", create_response.status_code, create_response.text[:300])
                if create_response.status_code != 200:
                    raise RuntimeError(f"fundpark-application/create failed: {create_response.status_code} {create_response.text[:300]}")

                application_id = db.wait_for_application(state.merchant_id, attempts=30, interval=2.0)
                if not application_id:
                    raise RuntimeError("fundpark-application/create did not produce dpu_application row")

                retry_after_application = final_apply_page.click_offer_apply_if_visible(timeout_ms=10_000)
                logging.info("[UI] retry after application creation: %s", retry_after_application)

                company_page = CompanyInfoPage(page, settings)
                company_page.wait_until_visible(reload_between_checks=True)
                company_page.fill(state.preferred_currency)
                if not auth_token:
                    raise RuntimeError("Missing browser token before business-info/director-info API submission")
                submit_fundpark_business_info(settings, auth_token, state.preferred_currency)
                submit_fundpark_director_info(settings, auth_token, phone, state.preferred_currency)
                DirectorInfoPage(page, settings).click_any("director next", DirectorInfoPage(page, settings).NEXT_BUTTONS)
                FinancingChoicePage(page, settings).choose_unlock_path()
                logging.info("[ASSERT] financing milestone reached")
                if stop_after == "financing":
                    return 0

                link_sp_3pl(settings, phone)
                logging.info("[RUN] REG ordinary offline Playwright clean flow finished")
                return 0

            except Exception:
                screenshot = settings.artifact_dir / "failure.png"
                try:
                    page.screenshot(path=str(screenshot), full_page=True)
                    logging.error("[ARTIFACT] failure screenshot: %s", screenshot)
                except Exception as screenshot_error:
                    logging.error("[ARTIFACT] failure screenshot failed: %s", screenshot_error)
                logging.exception("[RUN] flow failed")
                return 1
            finally:
                trace = settings.artifact_dir / "trace.zip"
                try:
                    context.tracing.stop(path=str(trace))
                    logging.info("[ARTIFACT] trace: %s", trace)
                finally:
                    wait_before_browser_close(pause_on_exit and headed)
                    context.close()
                    browser.close()


def main() -> int:
    args = parse_args()
    if args.debug_visible:
        args.headed = True
        args.pause_on_exit = True
        if args.slow_mo <= 0:
            args.slow_mo = 500

    settings = build_settings(args.env)
    object.__setattr__(settings, "slow_mo_ms", args.slow_mo)
    setup_logging(settings.artifact_dir)
    configure_playwright_browser_path()

    phone = generate_phone() if args.phone.lower() == "auto" else args.phone.strip()
    if not phone.isdigit() or len(phone) not in {8, 11}:
        raise ValueError("Phone must be 8 or 11 digits, or 'auto'")

    logging.info("[ARTIFACT] artifact dir: %s", settings.artifact_dir)
    return run_flow(settings, phone, args.headed, args.stop_after, args.slow_mo, args.pause_on_exit)


if __name__ == "__main__":
    raise SystemExit(main())
