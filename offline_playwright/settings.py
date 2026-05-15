# -*- coding: utf-8 -*-
"""Configuration for the Playwright offline automation runner."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Literal


EnvName = Literal["sit", "uat", "dev", "preprod", "reg", "local"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "output" / "playwright" / "offline"
BROWSER_CACHE = PROJECT_ROOT / ".playwright-browsers"


BASE_URLS: Dict[str, str] = {
    "sit": "https://sit.api.expressfinance.business.hsbc.com",
    "dev": "https://dpu-gateway-dev.dowsure.com",
    "uat": "https://uat.api.expressfinance.business.hsbc.com",
    "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
    "reg": "https://dpu-gateway-reg.dowsure.com",
    "local": "http://192.168.11.3:8080",
}

OFFLINE_SIGNUP_URLS: Dict[str, str] = {
    "sit": "https://expressfinance-dpu-sit.dowsure.com/en/",
    "dev": "https://expressfinance-dpu-dev.dowsure.com/en/sign-up-step1",
    "uat": "https://expressfinance-uat.business.hsbc.com/zh-Hans/",
    "preprod": "https://expressfinance-preprod.business.hsbc.com/zh-Hans/sign-up",
    "reg": "https://expressfinance-dpu-reg.dowsure.com/en/",
    "local": "http://192.168.11.3:8080/en/",
}

DATABASE_CONFIGS: Dict[str, Dict[str, object]] = {
    "sit": {
        "host": "18.162.145.173",
        "user": "dpu_sit",
        "password": "20250818dpu_sit",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
    },
    "dev": {
        "host": "aurora-dpu-dev.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_dev",
        "password": "J9IUmPpD@Hon8Y#v",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
    },
    "uat": {
        "host": "aurora-dpu-uat.cluster-cv2aqqmyo5k9.ap-east-1.rds.amazonaws.com",
        "user": "dpu_uat",
        "password": "6S[a=u.*Z;Zt~b&-A4|Ma&q^w8r_3vz[",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
    },
    "preprod": {
        "host": "43.199.241.190",
        "user": "dpu_preprod",
        "password": "OWBSNfx8cC5c#Or0",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
    },
    "reg": {
        "host": "aurora-dpu-reg.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_reg",
        "password": "r4asUYBX3R6LNdp",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
    },
    "local": {
        "host": "localhost",
        "user": "root",
        "password": "root",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4",
    },
}


@dataclass(frozen=True)
class AmountConfig:
    underwritten_amount: str
    approved_amount: float
    esign_amount: float
    direct_flow_amount: float
    brn: str


AMOUNT_CONFIGS: Dict[str, AmountConfig] = {
    "USD": AmountConfig(
        underwritten_amount="500000",
        approved_amount=500000.00,
        esign_amount=500000.00,
        direct_flow_amount=2000.00,
        brn="00000001",
    ),
    "CNY": AmountConfig(
        underwritten_amount="1500000",
        approved_amount=1500000.00,
        esign_amount=1500000.00,
        direct_flow_amount=70000.00,
        brn="91330201MA2AFFT07Q",
    ),
}


@dataclass(frozen=True)
class RunnerSettings:
    env: str
    base_url: str
    offline_signup_url: str
    database: Dict[str, object]
    artifact_dir: Path
    password: str = "Aa11111111.."
    default_sms_code: str = "666666"
    wait_timeout_ms: int = 30_000
    action_timeout_ms: int = 15_000
    slow_mo_ms: int = 0
    browser_name: str = "chromium"
    id_image_dir: Path = Path(r"C:\Users\PC\Desktop\截图")


def configure_playwright_browser_path() -> Path:
    """Keep Playwright browser downloads out of restricted Windows directories."""
    BROWSER_CACHE.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSER_CACHE))
    return BROWSER_CACHE


def build_settings(env: str, run_id: str | None = None) -> RunnerSettings:
    normalized_env = env.lower()
    if normalized_env not in BASE_URLS:
        raise ValueError(f"Unsupported env: {env}. Expected one of: {', '.join(BASE_URLS)}")

    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = OUTPUT_ROOT / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    return RunnerSettings(
        env=normalized_env,
        base_url=BASE_URLS[normalized_env],
        offline_signup_url=OFFLINE_SIGNUP_URLS[normalized_env],
        database=DATABASE_CONFIGS[normalized_env],
        artifact_dir=artifact_dir,
    )


def amount_for_currency(currency: str | None) -> AmountConfig:
    return AMOUNT_CONFIGS.get((currency or "USD").upper(), AMOUNT_CONFIGS["USD"])
