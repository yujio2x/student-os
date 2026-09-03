from __future__ import annotations

import sqlite3
from typing import Protocol

from app.database import Database


PRODUCTS = {
    "task_help_1_v1": {
        "id": "task_help_1_v1", "title": "1 разбор", "stars": 25, "credits": 1,
    },
    "task_help_5_v1": {
        "id": "task_help_5_v1", "title": "5 разборов", "stars": 100, "credits": 5,
    },
}


class InsufficientCredits(ValueError):
    pass


class ReservationConflict(ValueError):
    pass


class PaymentConflict(ValueError):
    pass


class InvalidProduct(ValueError):
    pass


class StudentAIEntitlementService(Protocol):
    def get_balance(self, user_id: str) -> dict: ...
    def reserve_credit(self, user_id: str, request_id: str, amount: int = 1) -> dict: ...
    def commit_usage(
        self, request_id: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> dict: ...
    def release_reservation(self, request_id: str) -> dict: ...


class UnifiedEntitlementService:
    """Single transactional ledger for web, Telegram, payments, trial and admin."""

    def __init__(self, database: Database, source: str = "core") -> None:
        self.database = database
        self.source = "core" if source in {"core", "local"} else "core-unconnected"

    def _ensure_account(self, db, user_id: str) -> None:
        now = self.database._now()
        db.execute(
            """INSERT OR IGNORE INTO ai_entitlements
            (user_id, balance, unlimited, free_trial_available, source, created_at, updated_at)
            VALUES (?, 0, 0, 1, ?, ?, ?)""",
            (user_id, self.source, now, now),
        )
        db.execute(
            """UPDATE ai_entitlements SET source=?
            WHERE user_id=? AND source IN
            ('local', 'local-unconnected', 'core', 'core-unconnected')""",
            (self.source, user_id),
        )

    @staticmethod
    def _account(row) -> dict:
        return {
            "balance": int(row["balance"]),
            "unlimited": bool(row["unlimited"]),
            "free_trial_available": bool(row["free_trial_available"]),
            "source": str(row["source"]),
            "connected": row["source"] == "core",
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def get_balance(self, user_id: str) -> dict:
        with self.database.connection() as db:
            self._ensure_account(db, user_id)
            row = db.execute(
                """SELECT balance, unlimited, free_trial_available, source,
                created_at, updated_at FROM ai_entitlements WHERE user_id=?""",
                (user_id,),
            ).fetchone()
        return self._account(row)

    def reserve_credit(self, user_id: str, request_id: str, amount: int = 1,
                       expected_source: str | None = None) -> dict:
        if not request_id or len(request_id) > 128:
            raise ValueError("invalid request_id")
        if not 1 <= int(amount) <= 100:
            raise ValueError("invalid amount")
        amount = int(amount)
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                if existing["user_id"] != user_id or int(existing["amount"]) != amount:
                    raise ReservationConflict("request_id belongs to another operation")
                return {**dict(existing), "reused": True}
            self._ensure_account(db, user_id)
            account = db.execute(
                """SELECT balance, unlimited, free_trial_available
                FROM ai_entitlements WHERE user_id=?""",
                (user_id,),
            ).fetchone()
            charged = 0
            current_source = "unlimited" if account["unlimited"] else (
                "trial" if amount == 1 and account["free_trial_available"] else "paid"
            )
            if expected_source is not None and current_source != expected_source:
                raise ReservationConflict("Entitlement changed; confirm a new quote")
            if account["unlimited"]:
                access_source = "unlimited"
            elif amount == 1 and account["free_trial_available"]:
                db.execute(
                    """UPDATE ai_entitlements SET free_trial_available=0, updated_at=?
                    WHERE user_id=? AND free_trial_available=1""",
                    (self.database._now(), user_id),
                )
                access_source = "trial"
            else:
                cursor = db.execute(
                    """UPDATE ai_entitlements SET balance=balance-?, updated_at=?
                    WHERE user_id=? AND balance>=?""",
                    (amount, self.database._now(), user_id, amount),
                )
                if cursor.rowcount != 1:
                    raise InsufficientCredits("Student AI credits exhausted")
                charged = 1
                access_source = "paid"
            now = self.database._now()
            db.execute(
                """INSERT INTO ai_credit_reservations
                (request_id, user_id, status, charged, amount, entitlement_source,
                created_at, updated_at)
                VALUES (?, ?, 'reserved', ?, ?, ?, ?, ?)""",
                (request_id, user_id, charged, amount, access_source, now, now),
            )
            row = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
        return {**dict(row), "reused": False}

    def commit_usage(
        self, request_id: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> dict:
        return self._transition(request_id, "committed", input_tokens, output_tokens)

    def release_reservation(self, request_id: str) -> dict:
        return self._transition(request_id, "released")

    def _transition(
        self, request_id: str, target: str,
        input_tokens: int = 0, output_tokens: int = 0,
    ) -> dict:
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None:
                raise ReservationConflict("reservation not found")
            if row["status"] == target:
                return dict(row)
            if row["status"] != "reserved":
                raise ReservationConflict(f"cannot {target} a {row['status']} reservation")
            now = self.database._now()
            if target == "released":
                if row["entitlement_source"] == "paid":
                    db.execute(
                        """UPDATE ai_entitlements SET balance=balance+?, updated_at=?
                        WHERE user_id=?""",
                        (int(row["amount"]), now, row["user_id"]),
                    )
                elif row["entitlement_source"] == "trial":
                    db.execute(
                        """UPDATE ai_entitlements SET free_trial_available=1, updated_at=?
                        WHERE user_id=?""",
                        (now, row["user_id"]),
                    )
                db.execute(
                    """UPDATE ai_credit_reservations
                    SET status='released', released_at=?, updated_at=? WHERE request_id=?""",
                    (now, now, request_id),
                )
            else:
                safe_input = min(max(0, int(input_tokens)), 10_000_000)
                safe_output = min(max(0, int(output_tokens)), 10_000_000)
                db.execute(
                    """UPDATE ai_credit_reservations SET status='committed',
                    input_tokens=?, output_tokens=?, committed_at=?, updated_at=?
                    WHERE request_id=?""",
                    (safe_input, safe_output, now, now, request_id),
                )
            updated = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
        return dict(updated)

    def record_telegram_payment(
        self, user_id: str, telegram_user_id: str, charge_id: str,
        product_id: str, stars_paid: int,
    ) -> dict:
        product = PRODUCTS.get(product_id)
        if product is None:
            raise InvalidProduct("unknown product")
        if int(stars_paid) != product["stars"]:
            raise InvalidProduct("unexpected Stars amount")
        if not charge_id or len(charge_id) > 180:
            raise ValueError("invalid charge id")
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                """SELECT * FROM telegram_star_payments
                WHERE telegram_payment_charge_id=?""",
                (charge_id,),
            ).fetchone()
            if prior:
                if (
                    prior["user_id"] != user_id
                    or prior["telegram_user_id"] != telegram_user_id
                    or prior["product_id"] != product_id
                    or int(prior["stars_paid"]) != int(stars_paid)
                ):
                    raise PaymentConflict("charge id already belongs to another payment")
                return {**dict(prior), "duplicate": True}
            self._ensure_account(db, user_id)
            now = self.database._now()
            try:
                cursor = db.execute(
                    """INSERT INTO telegram_star_payments
                    (telegram_payment_charge_id, telegram_user_id, user_id, product_id,
                    stars_paid, credits_granted, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        charge_id, telegram_user_id, user_id, product_id,
                        int(stars_paid), product["credits"], now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise PaymentConflict("duplicate payment conflict") from exc
            db.execute(
                """UPDATE ai_entitlements SET balance=balance+?, updated_at=?
                WHERE user_id=?""",
                (product["credits"], now, user_id),
            )
            row = db.execute(
                "SELECT * FROM telegram_star_payments WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
        return {**dict(row), "duplicate": False}


# Backward-compatible import name while callers move to the unified core name.
LocalEntitlementService = UnifiedEntitlementService
