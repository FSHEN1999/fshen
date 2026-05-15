# -*- coding: utf-8 -*-
"""Database helpers for Playwright offline automation."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pymysql
from pymysql.err import OperationalError


@dataclass(frozen=True)
class FinalApplyState:
    phone: str
    merchant_id: str
    authorization_state: str
    authorization_id: Optional[str]
    preferred_currency: str


class DatabaseExecutor:
    """Small pymysql wrapper with parameterized query helpers and reconnects."""

    RETRY_ERROR_CODES = {2006, 2013, 10054}

    def __init__(self, config: Dict[str, Any]):
        self.config = {
            **config,
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": config.get("connect_timeout", 15),
            "read_timeout": config.get("read_timeout", 15),
            "write_timeout": config.get("write_timeout", 15),
            "autocommit": True,
        }
        self._connection: Optional[pymysql.connections.Connection] = None

    def __enter__(self) -> "DatabaseExecutor":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        if self._connection and self._connection.open:
            return
        self._connection = pymysql.connect(**self.config)

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None

    def _execute_once(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self.connect()
        assert self._connection is not None
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            return self._execute_once(sql, params)
        except OperationalError as exc:
            if exc.args and exc.args[0] in self.RETRY_ERROR_CODES:
                logging.warning("[DB] Connection stale, reconnecting once: %s", exc)
                self.close()
                return self._execute_once(sql, params)
            raise

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    def get_merchant_id(self, phone: str) -> Optional[str]:
        return self.scalar(
            "SELECT merchant_id FROM dpu_users WHERE phone_number = %s ORDER BY created_at DESC LIMIT 1",
            (phone,),
        )

    def get_preferred_currency(self, merchant_id: str) -> str:
        value = self.scalar(
            "SELECT prefer_finance_product_currency FROM dpu_users WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        return str(value or "USD").upper()

    def get_sms_code(self, phone: str, fallback: str = "666666") -> str:
        placeholders = self.scalar(
            """
            SELECT placeholders
            FROM dpu_sms_record
            WHERE phone_number = %s
            ORDER BY COALESCE(send_time, create_time) DESC
            LIMIT 1
            """,
            (phone,),
        )
        if not placeholders:
            return fallback
        match = re.search(r"\d{6}", str(placeholders))
        return match.group(0) if match else fallback

    def wait_for_sms_code(
        self,
        phone: str,
        fallback: str = "666666",
        attempts: int = 10,
        interval: float = 2.0,
    ) -> str:
        for attempt in range(1, attempts + 1):
            code = self.get_sms_code(phone, fallback="")
            if code:
                logging.info("[DB] SMS code fetched on attempt %s: %s", attempt, code)
                return code
            if attempt < attempts:
                time.sleep(interval)
        logging.warning("[DB] SMS code not found; fallback to default code: %s", fallback)
        return fallback

    def wait_for_sp_auth_state(
        self,
        phone: str,
        attempts: int = 20,
        interval: float = 1.0,
    ) -> Optional[FinalApplyState]:
        sql = """
            SELECT state, authorization_id, merchant_id
            FROM dpu_auth_token
            WHERE merchant_id IN (
                SELECT merchant_id
                FROM dpu_users
                WHERE phone_number = %s
            )
              AND authorization_party = 'SP'
            ORDER BY created_at DESC
            LIMIT 1
        """
        for attempt in range(1, attempts + 1):
            rows = self.query(sql, (phone,))
            if rows and rows[0].get("state"):
                row = rows[0]
                merchant_id = str(row["merchant_id"])
                state = FinalApplyState(
                    phone=phone,
                    merchant_id=merchant_id,
                    authorization_state=str(row["state"]),
                    authorization_id=row.get("authorization_id"),
                    preferred_currency=self.get_preferred_currency(merchant_id),
                )
                logging.info("[DB] SP auth state found on attempt %s: %s", attempt, state)
                return state
            if attempt < attempts:
                time.sleep(interval)
        return None

    def wait_for_send_status(
        self,
        selling_partner_id: str,
        attempts: int = 30,
        interval: float = 2.0,
    ) -> Optional[str]:
        sql = """
            SELECT send_status
            FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        last_status = None
        for attempt in range(1, attempts + 1):
            last_status = self.scalar(sql, (selling_partner_id,))
            if last_status == "SUCCESS":
                logging.info("[DB] send_status SUCCESS on attempt %s", attempt)
                return str(last_status)
            logging.info("[DB] send_status attempt %s/%s: %s", attempt, attempts, last_status)
            if attempt < attempts:
                time.sleep(interval)
        return str(last_status) if last_status is not None else None

    def get_platform_offer_id(self, selling_partner_id: str) -> Optional[str]:
        return self.scalar(
            """
            SELECT platform_offer_id
            FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (selling_partner_id,),
        )

    def wait_for_application(
        self,
        merchant_id: str,
        attempts: int = 60,
        interval: float = 2.0,
    ) -> Optional[str]:
        sql = """
            SELECT application_unique_id
            FROM dpu_application
            WHERE merchant_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        for attempt in range(1, attempts + 1):
            application_id = self.scalar(sql, (merchant_id,))
            if application_id:
                logging.info("[DB] application found on attempt %s: %s", attempt, application_id)
                return str(application_id)
            if attempt < attempts:
                time.sleep(interval)
        return None

    def get_idempotency_key(self, selling_partner_id: str) -> Optional[str]:
        return self.scalar(
            """
            SELECT idempotency_key
            FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (selling_partner_id,),
        )
