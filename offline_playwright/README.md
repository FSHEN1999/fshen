# DPU Offline Playwright Runner

This directory is a clean Playwright implementation for the REG ordinary offline flow. It intentionally does not import or modify the legacy Selenium scripts.

## Install

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-playwright.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Browser downloads are redirected to `.playwright-browsers/` by the runner so they do not land in restricted Windows directories.

## Run

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed
```

Useful debug stops:

```powershell
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed --stop-after final_apply
.\.venv\Scripts\python.exe -m offline_playwright.runner --env reg --headed --stop-after financing
```

Artifacts are written to `output/playwright/offline/<timestamp>/`:

- `run.log`
- `trace.zip`
- `failure.png` on error
- browser videos

## Selenium vs Playwright

Selenium drives a browser through WebDriver and usually requires explicit waits, fallback clicks, and custom JavaScript for dynamic pages. Playwright has auto-waiting actionability checks, built-in tracing, screenshots, videos, and better request/page-state observability. That makes it easier to prove whether a DPU run truly advanced in the UI and DB, instead of trusting a log line that says a click happened.
