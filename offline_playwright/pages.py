# -*- coding: utf-8 -*-
"""Playwright page objects for the REG offline flow."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from offline_playwright.settings import RunnerSettings, amount_for_currency


def _xpath(value: str) -> str:
    return f"xpath={value}"


class BasePage:
    def __init__(self, page: Page, settings: RunnerSettings):
        self.page = page
        self.settings = settings

    def wait_ready(self) -> None:
        self.page.wait_for_load_state("domcontentloaded", timeout=self.settings.wait_timeout_ms)
        try:
            self.page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeoutError:
            logging.debug("[UI] networkidle timeout; continuing after domcontentloaded")
        self.page.wait_for_function(
            """
            () => {
              const masks = Array.from(document.querySelectorAll(
                '.el-loading-mask, .loading-mask, [aria-busy="true"]'
              ));
              return !masks.some((el) => {
                const style = window.getComputedStyle(el);
                return style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  style.opacity !== '0';
              });
            }
            """,
            timeout=8_000,
        )

    def locator_candidates(self, candidates: Iterable[str]) -> Optional[Locator]:
        last_error: Optional[Exception] = None
        for selector in candidates:
            locator = self.page.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=3_000)
                return locator
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            logging.debug("[UI] Last locator candidate error: %s", last_error)
        return None

    def click_any(self, description: str, candidates: Iterable[str]) -> None:
        self.wait_ready()
        locator = self.locator_candidates(candidates)
        if not locator:
            raise RuntimeError(f"Could not find clickable element: {description}")
        locator.scroll_into_view_if_needed(timeout=self.settings.action_timeout_ms)
        locator.click(timeout=self.settings.action_timeout_ms)
        logging.info("[UI] clicked: %s", description)

    def fill_any(
        self,
        description: str,
        value: str,
        candidates: Iterable[str],
        *,
        allow_js_fallback: bool = True,
    ) -> None:
        self.wait_ready()
        locator = self.locator_candidates(candidates)
        if locator:
            locator.scroll_into_view_if_needed(timeout=self.settings.action_timeout_ms)
            locator.fill(value, timeout=self.settings.action_timeout_ms)
            logging.info("[UI] filled %s", description)
            return

        if not allow_js_fallback:
            raise RuntimeError(f"Could not fill element: {description}")

        result = self.page.evaluate(
            """
            ({ value, candidates }) => {
              const isUsable = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return el.offsetParent !== null &&
                  style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  !el.disabled &&
                  !el.readOnly;
              };
              for (const selector of candidates) {
                for (const el of Array.from(document.querySelectorAll(selector))) {
                  if (!isUsable(el)) continue;
                  const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype,
                    'value'
                  )?.set;
                  el.focus();
                  el.select?.();
                  setter ? setter.call(el, value) : el.value = value;
                  ['input', 'change', 'keyup', 'blur'].forEach((name) =>
                    el.dispatchEvent(new Event(name, { bubbles: true }))
                  );
                  return { success: true, selector, actual: el.value };
                }
              }
              return { success: false };
            }
            """,
            {"value": value, "candidates": [self._css_from_selector(item) for item in candidates]},
        )
        if not result or not result.get("success"):
            raise RuntimeError(f"Could not fill element: {description}; js_result={result}")
        logging.info("[UI] filled %s via JS fallback: %s", description, result)

    @staticmethod
    def _css_from_selector(selector: str) -> str:
        # JS fallback cannot query Playwright's xpath= engine. Keep broad CSS fallbacks useful.
        if selector.startswith("xpath="):
            return "input.el-input__inner, input, textarea"
        return selector

    def read_browser_auth_token(self) -> Optional[str]:
        token = self.page.evaluate(
            """
            () => {
              const keys = ['token','Token','accessToken','access_token','authToken','authorization','jwt'];
              const stores = [window.localStorage, window.sessionStorage];
              for (const store of stores) {
                for (const key of keys) {
                  const raw = store.getItem(key);
                  if (!raw) continue;
                  try {
                    const parsed = JSON.parse(raw);
                    if (parsed.token) return parsed.token;
                  } catch (_) {}
                  return raw;
                }
              }
              return null;
            }
            """
        )
        return token

    def browser_post_json(self, url: str, payload: dict, headers: Optional[dict[str, str]] = None) -> dict:
        headers = headers or {}
        result = self.page.evaluate(
            """
            async ({ url, payload, headers }) => {
              const tokenKeys = ['token','Token','accessToken','access_token','authToken','authorization','jwt'];
              const stores = [window.localStorage, window.sessionStorage];
              let token = null;
              for (const store of stores) {
                for (const key of tokenKeys) {
                  const raw = store.getItem(key);
                  if (!raw) continue;
                  try {
                    const parsed = JSON.parse(raw);
                    if (parsed.token) {
                      token = parsed.token;
                      break;
                    }
                  } catch (_) {}
                  token = raw;
                  break;
                }
                if (token) break;
              }
              const finalHeaders = {
                'content-type': 'application/json',
                ...headers,
              };
              if (token && !finalHeaders.Authorization) {
                finalHeaders.Authorization = `Bearer ${token}`;
              }
              const response = await fetch(url, {
                method: 'POST',
                headers: finalHeaders,
                body: JSON.stringify(payload),
                credentials: 'include',
              });
              const text = await response.text();
              return {
                ok: response.ok,
                status: response.status,
                text,
                tokenFound: !!token,
                url: response.url,
              };
            }
            """,
            {"url": url, "payload": payload, "headers": headers},
        )
        logging.info("[BROWSER API] POST %s -> %s tokenFound=%s body=%s", url, result.get("status"), result.get("tokenFound"), str(result.get("text", ""))[:300])
        return result


class RegistrationFlow(BasePage):
    INITIAL_APPLY_BUTTONS = [
        _xpath("(//*[contains(normalize-space(), 'FundPark')]/ancestor::*[.//button[contains(., 'Apply now') or contains(., '立即申请') or contains(., '立即申請')]][1]//button[contains(., 'Apply now') or contains(., '立即申请') or contains(., '立即申請')])[last()]"),
        _xpath("(//button[contains(., 'Apply now') or contains(., '立即申请') or contains(., '立即申請')])[last()]"),
    ]
    PHONE_INPUTS = [
        _xpath("//fieldset[1]//input[@maxlength='15']"),
        "input.el-input__inner[maxlength='15']",
        "input[type='tel']",
        _xpath("//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    ]
    SEND_CODE_BUTTONS = [
        "button.get-code-btn",
        _xpath("//button[contains(., '验证码') or contains(., 'Code')]"),
    ]
    CODE_INPUTS = _xpath("//input[contains(@class, 'el-input__inner') and @maxlength='1']")
    NEXT_BUTTONS = [
        _xpath("//button[contains(., '下一步') or contains(., 'Next')]"),
        "button[type='submit']",
        "button.el-button",
    ]
    PASSWORD_INPUTS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[2]/div/div[1]/div/input"),
        _xpath("(//input[@type='password' and contains(@class, 'el-input__inner')])[1]"),
    ]
    CONFIRM_PASSWORD_INPUTS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[5]/div/div[1]/div/input"),
        _xpath("(//input[@type='password' and contains(@class, 'el-input__inner')])[2]"),
    ]
    SECURITY_DROPDOWNS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div/div[1]/div[1]/div[2]"),
        _xpath("//div[contains(@class, 'section-container')][.//h2[contains(., 'Security') or contains(., '安全')]]//div[contains(@class, 'el-select__wrapper') or contains(@class, 'el-select')]"),
    ]
    SECURITY_ANSWER_INPUTS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[4]/div/div[1]/div/input"),
        _xpath("//div[contains(@class, 'section-container')][.//h2[contains(., 'Security') or contains(., '安全')]]//input[contains(@class, 'el-input__inner') and @type='text']"),
    ]
    EMAIL_INPUTS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[3]/div[2]/div/div[1]/div/input"),
        _xpath("//div[contains(@class, 'section-container')][.//h2[contains(., 'Contact') or contains(., '联系')]]//input[contains(@class, 'el-input__inner')]"),
        "input[type='email']",
    ]
    CONSENT_CHECKBOXES = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[1]/div/label/span[1]/span"),
        _xpath("(//span[contains(@class, 'el-checkbox__inner')])[1]"),
    ]
    AUTH_CHECKBOXES = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[2]/div/label/span[1]/span"),
        _xpath("(//span[contains(@class, 'el-checkbox__inner')])[2]"),
    ]
    REGISTER_BUTTONS = [
        _xpath("//button[.//span[normalize-space()='Sign up' or normalize-space()='注册' or normalize-space()='立即注册'] or normalize-space()='Sign up' or normalize-space()='注册' or normalize-space()='立即注册']"),
        _xpath("//button[contains(., 'Sign up') or contains(., '注册')]"),
    ]

    def open(self) -> None:
        logging.info("[UI] opening offline signup URL: %s", self.settings.offline_signup_url)
        self.page.goto(self.settings.offline_signup_url, wait_until="domcontentloaded")
        self.wait_ready()

    def start_application(self) -> None:
        """Click the FundPark landing-page Apply now button before registration."""
        if self.locator_candidates(self.PHONE_INPUTS):
            logging.info("[UI] phone input already visible; skip landing apply")
            return
        self.click_any("FundPark landing apply now", self.INITIAL_APPLY_BUTTONS)
        self.locator_candidates(self.PHONE_INPUTS)

    def fill_registration(self, phone: str, sms_code_provider) -> None:
        self.fill_any("phone number", phone, self.PHONE_INPUTS)
        try:
            self.click_any("send verification code", self.SEND_CODE_BUTTONS)
        except Exception as exc:
            logging.warning("[UI] send verification code button was not clicked: %s", exc)

        sms_code = sms_code_provider()
        code = sms_code[:6].ljust(6, "6")
        code_inputs = self.page.locator(self.CODE_INPUTS)
        count = code_inputs.count()
        if count < 6:
            raise RuntimeError(f"Expected at least 6 SMS code inputs, found {count}")
        for index, digit in enumerate(code):
            code_inputs.nth(index).fill(digit, timeout=self.settings.action_timeout_ms)
        logging.info("[UI] filled SMS verification code")

        self.click_any("registration next", self.NEXT_BUTTONS)
        if not self.locator_candidates(self.PASSWORD_INPUTS):
            raise RuntimeError("Registration next did not reach password setup page")

    def fill_password_setup(self, phone: str) -> None:
        self.fill_any("password", self.settings.password, self.PASSWORD_INPUTS, allow_js_fallback=False)
        self.fill_any(
            "confirm password",
            self.settings.password,
            self.CONFIRM_PASSWORD_INPUTS,
            allow_js_fallback=False,
        )
        self.click_any("security question dropdown", self.SECURITY_DROPDOWNS)
        self.click_any("first security question option", [_xpath("//li[contains(@class, 'el-select-dropdown__item')][1]")])
        self.fill_any("security answer", "Test123", self.SECURITY_ANSWER_INPUTS)
        self.fill_any("email address", f"{phone}@163.com", self.EMAIL_INPUTS)
        self.click_any("consent checkbox", self.CONSENT_CHECKBOXES)
        self.click_any("authorization checkbox", self.AUTH_CHECKBOXES)
        self.click_any("register button", self.REGISTER_BUTTONS)
        logging.info("[UI] submitted registration")

    def read_browser_token(self) -> Optional[str]:
        token = self.read_browser_auth_token()
        if token:
            logging.info("[UI] browser token captured")
        return token


class FinalApplyPage(BasePage):
    FINAL_APPLY_BUTTONS = [
        _xpath("//button[normalize-space()='Apply now']"),
        _xpath("//button[normalize-space()='立即申请']"),
        _xpath("//button[normalize-space()='立即申請']"),
        _xpath("//button[.//span[normalize-space()='Apply now']]"),
        _xpath("//button[.//span[normalize-space()='立即申请']]"),
        _xpath("//button[.//span[normalize-space()='立即申請']]"),
        _xpath("//span[normalize-space()='Apply now']/ancestor::button[1]"),
        _xpath("//span[normalize-space()='立即申请']/ancestor::button[1]"),
        _xpath("//span[normalize-space()='立即申請']/ancestor::button[1]"),
        "button.application-btn",
    ]
    CONTINUE_APPLICATION_BUTTONS = [
        _xpath("//button[contains(., 'Continue application')]"),
        _xpath("//button[contains(., '继续申请')]"),
        _xpath("//span[contains(., 'Continue application')]/ancestor::button[1]"),
        _xpath("//span[contains(., '继续申请')]/ancestor::button[1]"),
    ]

    def click_final_apply(self) -> None:
        self.click_any("final apply", self.FINAL_APPLY_BUTTONS)

    def click_continue_application(self) -> None:
        self.click_any("continue application", self.CONTINUE_APPLICATION_BUTTONS)

    def click_offer_apply_if_visible(self, timeout_ms: int = 20_000) -> dict[str, str]:
        """Click the post-authorization offer Apply now button when it is present."""
        self.wait_for_transient_dialogs()
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            for selector in self.FINAL_APPLY_BUTTONS:
                locator = self.page.locator(selector).first
                try:
                    locator.wait_for(state="visible", timeout=1_000)
                    locator.scroll_into_view_if_needed(timeout=self.settings.action_timeout_ms)
                    locator.click(timeout=self.settings.action_timeout_ms, force=True)
                    self.page.wait_for_timeout(3_000)
                    logging.info(
                        "[UI] force-clicked post-authorization offer apply; url=%s title=%s",
                        self.page.url,
                        self.page.title(),
                    )
                    return self.click_sp_api_continue_if_visible()
                except Exception as exc:
                    logging.debug("[UI] force apply candidate not ready: %s", exc)
            if self._click_visible_apply_now_with_js():
                self.page.wait_for_timeout(3_000)
                return self.click_sp_api_continue_if_visible()
            for selector in self.FINAL_APPLY_BUTTONS:
                locator = self.page.locator(selector).first
                try:
                    locator.wait_for(state="visible", timeout=1_000)
                    locator.scroll_into_view_if_needed(timeout=self.settings.action_timeout_ms)
                    locator.click(timeout=self.settings.action_timeout_ms)
                    logging.info("[UI] clicked post-authorization offer apply")
                    return {"status": "clicked"}
                except Exception as exc:
                    logging.debug("[UI] post-authorization apply candidate not ready: %s", exc)
            self.wait_for_transient_dialogs()
            self.page.reload(wait_until="domcontentloaded", timeout=15_000)
            self.wait_ready()
        logging.warning("[UI] post-authorization offer Apply now not visible")
        return {"status": "not_visible"}

    def click_sp_api_continue_if_visible(self) -> dict[str, str]:
        """Confirm the SP-API guide modal that appears before the application form."""
        locator = self.page.locator(
            _xpath(
                "//div[contains(@class, 'el-overlay') or contains(@class, 'el-dialog')]//button[contains(., 'Continue') or contains(., '继续')]"
            )
        ).first
        try:
            locator.wait_for(state="visible", timeout=5_000)
        except Exception:
            logging.info("[UI] SP-API Continue modal not visible")
            return {"status": "no_modal"}

        capture: dict[str, str] = {}

        def handle_request(request) -> None:
            if capture.get("state"):
                return
            state = self._extract_state_from_request(request)
            if state:
                capture["state"] = state
                capture["url"] = request.url
                logging.info("[UI] captured SP-API request state=%s url=%s", state, request.url)

        self.page.context.on("request", handle_request)
        try:
            with self.page.context.expect_page(timeout=8_000) as popup_info:
                locator.scroll_into_view_if_needed(timeout=self.settings.action_timeout_ms)
                locator.click(timeout=self.settings.action_timeout_ms, force=True)
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded", timeout=15_000)
            logging.info("[UI] clicked SP-API modal Continue; popup=%s", popup.url)
            if "sellercentral.amazon.com" in popup.url and not capture.get("state"):
                popup_state = self._extract_state_from_url(popup.url)
                if popup_state:
                    capture["state"] = popup_state
                    capture["url"] = popup.url
        except Exception as exc:
            logging.info("[UI] SP-API Continue did not open popup via Playwright click: %s", exc)
            result = self.page.evaluate(
                """
                () => {
                  const buttons = Array.from(document.querySelectorAll('button'))
                    .filter((button) => /Continue|继续/i.test(button.textContent || ''));
                  const button = buttons.find((candidate) => {
                    const rect = candidate.getBoundingClientRect();
                    const style = window.getComputedStyle(candidate);
                    return rect.width > 0 && rect.height > 0 &&
                      style.display !== 'none' &&
                      style.visibility !== 'hidden' &&
                      !candidate.disabled;
                  });
                  if (!button) return { success: false };
                  button.scrollIntoView({ block: 'center', inline: 'center' });
                  button.focus();
                  button.click();
                  ['mousedown', 'mouseup', 'click'].forEach((name) => {
                    button.dispatchEvent(new MouseEvent(name, {
                      bubbles: true,
                      cancelable: true,
                      view: window,
                      buttons: 1
                    }));
                  });
                  return { success: true, text: button.textContent };
                }
                """
            )
            logging.info("[UI] SP-API modal Continue JS result: %s", result)
            self.page.wait_for_timeout(3_000)
        finally:
            try:
                self.page.context.remove_listener("request", handle_request)
            except Exception:
                pass

        self.page.bring_to_front()
        try:
            self.page.locator(".el-overlay-dialog, .el-overlay").wait_for(state="hidden", timeout=10_000)
            modal_hidden = True
        except Exception:
            logging.info("[UI] SP-API modal still visible after Continue")
            modal_hidden = False
        return {
            "status": "external_amazon_login" if capture.get("state") else ("continued" if modal_hidden else "modal_still_visible"),
            "state": capture.get("state", ""),
            "url": capture.get("url", ""),
        }

    def dismiss_sp_api_modal_if_visible(self) -> bool:
        close_targets = [
            _xpath("//div[contains(@class, 'el-dialog')]//*[contains(@class, 'el-dialog__close')]"),
            _xpath("//div[contains(@class, 'el-dialog')]//button[contains(., 'Close') or contains(., '关闭')]"),
        ]
        for selector in close_targets:
            locator = self.page.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=2_000)
                locator.click(timeout=self.settings.action_timeout_ms, force=True)
                self.page.wait_for_timeout(1_500)
                logging.info("[UI] dismissed SP-API modal")
                return True
            except Exception:
                continue
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(1_500)
            if self.page.locator(".el-overlay-dialog, .el-overlay").count() == 0:
                logging.info("[UI] dismissed SP-API modal with Escape")
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _extract_state_from_request(request) -> Optional[str]:
        post_data = ""
        try:
            post_data = request.post_data or ""
        except Exception:
            post_data = ""
        if post_data:
            parsed_body = parse_qs(post_data)
            if parsed_body.get("state"):
                return parsed_body["state"][0]
        return FinalApplyPage._extract_state_from_url(request.url)

    @staticmethod
    def _extract_state_from_url(url: str) -> Optional[str]:
        query = parse_qs(urlparse(url).query)
        values = query.get("state")
        return values[0] if values else None

    def _click_visible_apply_now_with_js(self) -> bool:
        result = self.page.evaluate(
            """
            () => {
              const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 &&
                  style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  style.opacity !== '0' &&
                  !el.disabled &&
                  el.getAttribute('aria-disabled') !== 'true';
              };
              const buttons = Array.from(document.querySelectorAll('button'))
                .filter((button) => /Apply now|立即申请|立即申請/i.test(button.textContent || '') && isVisible(button));
              if (!buttons.length) return { success: false, reason: 'not-found' };
              const button = buttons[buttons.length - 1];
              button.scrollIntoView({ block: 'center', inline: 'center' });
              button.focus();
              button.click();
              ['mouseover', 'mousemove', 'mousedown', 'mouseup', 'click'].forEach((name) => {
                button.dispatchEvent(new MouseEvent(name, {
                  bubbles: true,
                  cancelable: true,
                  view: window,
                  buttons: 1
                }));
              });
              return { success: true, text: button.textContent, count: buttons.length };
            }
            """
        )
        if result and result.get("success"):
            logging.info("[UI] clicked visible post-authorization Apply now via JS: %s", result)
            return True
        logging.debug("[UI] visible post-authorization Apply now JS click not ready: %s", result)
        return False

    def wait_for_transient_dialogs(self) -> None:
        try:
            self.page.locator(".el-overlay-dialog.is-closing").wait_for(state="detached", timeout=5_000)
        except Exception:
            pass
        try:
            self.page.locator(".el-overlay, .el-overlay-dialog").wait_for(state="hidden", timeout=5_000)
        except Exception:
            pass


class CompanyInfoPage(BasePage):
    COMPANY_CN_NAME_INPUTS = [
        _xpath("//label[contains(., 'Company name in Chinese')]/following::input[1]"),
        _xpath("(//input[contains(@class, 'el-input__inner')])[1]"),
    ]
    COMPANY_EN_NAME_INPUTS = [
        _xpath("//label[contains(., 'Company name in English')]/following::input[1]"),
        _xpath("(//input[contains(@class, 'el-input__inner')])[2]"),
    ]
    USCID_INPUTS = [
        _xpath("//label[contains(., 'Unified Social Credit Identifier')]/following::input[1]"),
        _xpath("(//input[contains(@class, 'el-input__inner')])[3]"),
    ]
    TOP_BUYERS_INPUTS = [
        _xpath("//*[contains(., 'Top 3 customer countries/regions')]/following::input[1]"),
    ]
    TOP_SUPPLIERS_INPUTS = [
        _xpath("//*[contains(., 'Top 3 supplier countries/regions')]/following::input[1]"),
    ]
    FUNDING_COUNTRY_DROPDOWNS = [
        _xpath("//*[contains(., 'Country/Region of funding sources')]/following::div[contains(@class, 'el-select')][1]"),
    ]
    INDUSTRY_DROPDOWNS = [
        _xpath("//*[contains(., 'Industry')]/following::div[contains(@class, 'el-select')][1]"),
    ]
    MAIN_PRODUCTS_INPUTS = [
        _xpath("//*[contains(., 'Main products sold')]/following::textarea[1]"),
        _xpath("//*[contains(., 'Main products sold')]/following::input[1]"),
    ]
    INITIAL_SOURCE_CHECKBOXES = [
        _xpath("//label[contains(., 'Personal savings of the business owner')]//span[contains(@class, 'el-checkbox__inner')]"),
    ]
    ONGOING_WEALTH_CHECKBOXES = [
        _xpath("//label[contains(., 'Operating revenue and profit')]//span[contains(@class, 'el-checkbox__inner')]"),
    ]
    SOURCES_OF_FUNDS_CHECKBOXES = [
        _xpath("//label[contains(., 'Funds from business operations')]//span[contains(@class, 'el-checkbox__inner')]"),
    ]
    NEXT_BUTTONS = [
        _xpath("//button[contains(., 'Next')]"),
        _xpath("//button[contains(., '下一步') or contains(., 'Next')]"),
    ]

    def wait_until_visible(self, timeout_ms: int = 60_000, reload_between_checks: bool = False) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        last_error: Optional[Exception] = None
        while time.monotonic() < deadline:
            try:
                if self.locator_candidates(self.COMPANY_CN_NAME_INPUTS):
                    return
            except Exception as exc:
                last_error = exc
            if reload_between_checks:
                try:
                    self.page.reload(wait_until="domcontentloaded", timeout=15_000)
                    self.wait_ready()
                except Exception as exc:
                    last_error = exc
            self.page.wait_for_timeout(2_000)
        raise RuntimeError(f"Company information page did not become visible; last_error={last_error}")

    def fill(self, preferred_currency: str) -> None:
        amount = amount_for_currency(preferred_currency)
        self.fill_any("company Chinese name", "测试有限公司", self.COMPANY_CN_NAME_INPUTS)
        self.fill_any("company English name", "", self.COMPANY_EN_NAME_INPUTS)
        self.fill_any("unified social credit identifier", amount.brn, self.USCID_INPUTS)
        self.ensure_checkbox_checked("initial source of wealth", self.INITIAL_SOURCE_CHECKBOXES)
        self.ensure_checkbox_checked("ongoing wealth and income", self.ONGOING_WEALTH_CHECKBOXES)
        self.ensure_checkbox_checked("sources of funds", self.SOURCES_OF_FUNDS_CHECKBOXES)
        self.click_any("company next", self.NEXT_BUTTONS)

    def ensure_checkbox_checked(self, description: str, candidates: Iterable[str]) -> None:
        locator = self.locator_candidates(candidates)
        if not locator:
            raise RuntimeError(f"Could not find checkbox: {description}")
        checked = locator.evaluate(
            """
            (el) => {
              const box = el.closest('label') || el.parentElement;
              return box?.classList.contains('is-checked') || !!el.querySelector('.is-checked');
            }
            """
        )
        if not checked:
            locator.click(timeout=self.settings.action_timeout_ms, force=True)
        logging.info("[UI] ensured checkbox checked: %s", description)


class DirectorInfoPage(BasePage):
    FRONT_UPLOAD_AREAS = [
        _xpath("//*[contains(., 'ID document front side')]/following::*[contains(., 'browse to select')][1]/ancestor::div[1]"),
        _xpath("(//*[contains(., 'browse to select')])[1]/ancestor::div[1]"),
    ]
    BACK_UPLOAD_AREAS = [
        _xpath("//*[contains(., 'ID document back side')]/following::*[contains(., 'browse to select')][1]/ancestor::div[1]"),
        _xpath("(//*[contains(., 'browse to select')])[2]/ancestor::div[1]"),
    ]
    BIRTH_DATE_INPUTS = [
        _xpath("//*[contains(., 'Date of birth')]/following::input[1]"),
        _xpath("//input[@placeholder='DD/MM/YYYY' or @placeholder='YYYY/MM/DD']"),
    ]
    REFERENCE_PHONE_INPUTS = [
        _xpath("//*[contains(., 'Mobile number')]/following::input[not(@readonly)][1]"),
        _xpath("//*[contains(., 'Mobile number')]/following::div[contains(@class, 'el-input')][last()]//input[contains(@class, 'el-input__inner') and not(@readonly)][1]"),
    ]
    REFERENCE_EMAIL_INPUTS = [
        _xpath("//*[contains(., 'Email address')]/following::input[1]"),
        "input[type='email']",
    ]
    NEXT_BUTTONS = [
        _xpath("//button[contains(., 'Next')]"),
        _xpath("//button[contains(., '下一步') or contains(., 'Next')]"),
    ]

    def fill(self, phone: str) -> None:
        self._upload_id_images_if_available()
        self.fill_birth_date()
        self.fill_any("reference phone", phone, self.REFERENCE_PHONE_INPUTS)
        self.fill_any("reference email", f"{phone}@qq.com", self.REFERENCE_EMAIL_INPUTS)
        self.click_any("director next", self.NEXT_BUTTONS)

    def _upload_id_images_if_available(self) -> None:
        front = self.settings.id_image_dir / "身份证正面.png"
        back = self.settings.id_image_dir / "身份证反面.png"
        if not front.exists() or not back.exists():
            logging.warning("[UI] ID images not found in %s; skipping upload", self.settings.id_image_dir)
            return
        self._set_upload_area_file("ID front", front, self.FRONT_UPLOAD_AREAS)
        self._set_upload_area_file("ID back", back, self.BACK_UPLOAD_AREAS)

    def _set_upload_area_file(self, description: str, path: Path, candidates: Iterable[str]) -> None:
        area = self.locator_candidates(candidates)
        if area:
            try:
                input_locator = area.locator("input[type='file']").first
                input_locator.set_input_files(str(path), timeout=self.settings.action_timeout_ms)
                self.page.wait_for_timeout(2_000)
                logging.info("[UI] uploaded %s via nested input: %s", description, path)
                return
            except Exception as exc:
                logging.warning("[UI] nested input upload failed for %s: %s", description, exc)

        result = self.page.evaluate(
            """
            ({ labelText, filePath }) => {
              const sections = Array.from(document.querySelectorAll('body *')).filter((el) =>
                (el.textContent || '').includes(labelText)
              );
              for (const section of sections) {
                const container = section.parentElement;
                if (!container) continue;
                const input = container.querySelector('input[type=\"file\"]') ||
                  container.parentElement?.querySelector('input[type=\"file\"]');
                if (!input) continue;
                return { success: true };
              }
              return { success: false };
            }
            """,
            {"labelText": "ID document front side" if "front" in description.lower() else "ID document back side", "filePath": str(path)},
        )
        input_locator = self.page.locator("input[type='file']").nth(0 if "front" in description.lower() else 1)
        try:
            input_locator.set_input_files(str(path), timeout=self.settings.action_timeout_ms)
            self.page.wait_for_timeout(2_000)
            logging.info("[UI] uploaded %s via global fallback: %s", description, path)
            return
        except Exception as exc:
            raise RuntimeError(f"Could not find file input for {description}; js_probe={result}; error={exc}")

    def fill_birth_date(self) -> None:
        locator = self.locator_candidates(self.BIRTH_DATE_INPUTS)
        if not locator:
            raise RuntimeError("Could not find birth date input")
        locator.click(timeout=self.settings.action_timeout_ms)
        locator.fill("30/12/2025", timeout=self.settings.action_timeout_ms)
        self.page.wait_for_timeout(500)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(500)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        logging.info("[UI] filled birth date")


class FinancingChoicePage(BasePage):
    ACTIVATE_NOW_BUTTONS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div/div[2]/div[1]/div/div/button"),
        _xpath("//button[contains(., 'Activate') or contains(., '去激活')]"),
    ]
    APPLY_HIGHER_AMOUNT_BUTTONS = [
        _xpath("/html/body/div[1]/div[1]/div[3]/div/div/div[2]/div[2]/div/div[2]/button"),
        _xpath("//button[contains(., 'higher') or contains(., '更高')]"),
    ]

    def choose_unlock_path(self) -> bool:
        """Choose the no-bank-info path used by the first clean runner.

        Returns False to indicate bank account information is not required.
        """
        self.wait_ready()
        self.click_any("apply higher amount / unlock path", self.APPLY_HIGHER_AMOUNT_BUTTONS)
        return False
