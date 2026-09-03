from __future__ import annotations

from typing import Protocol

from app.database import Database


class InsufficientCredits(ValueError):
    pass


class ReservationConflict(ValueError):
    pass


class StudentAIEntitlementService(Protocol):
    def get_balance(self, user_id: str) -> dict: ...
    def reserve_credit(self, user_id: str, request_id: str) -> dict: ...
    def commit_usage(self, request_id: str) -> dict: ...
    def release_reservation(self, request_id: str) -> dict: ...


class LocalEntitlementService:
    """Auditable bridge boundary; not connected to the live Telegram ledger."""

    def __init__(self, database: Database, source: str = "unconnected") -> None:
        self.database = database
        self.source = "local" if source == "local" else "local-unconnected"

    def _ensure_account(self, db, user_id: str) -> None:
        db.execute(
            """INSERT OR IGNORE INTO ai_entitlements
            (user_id, balance, unlimited, source, updated_at)
            VALUES (?, 0, 0, ?, ?)""",
            (user_id, self.source, self.database._now()),
        )
        db.execute(
            """UPDATE ai_entitlements SET source=?
            WHERE user_id=? AND source IN ('local', 'local-unconnected')""",
            (self.source, user_id),
        )

    def get_balance(self, user_id: str) -> dict:
        with self.database.connection() as db:
            self._ensure_account(db, user_id)
            row = db.execute(
                "SELECT balance, unlimited, source, updated_at FROM ai_entitlements WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return {
            "balance": int(row["balance"]), "unlimited": bool(row["unlimited"]),
            "source": str(row["source"]), "connected": row["source"] != "local-unconnected",
            "updated_at": str(row["updated_at"]),
        }

    def reserve_credit(self, user_id: str, request_id: str) -> dict:
        if not request_id or len(request_id) > 128:
            raise ValueError("invalid request_id")
        with self.database.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                if existing["user_id"] != user_id:
                    raise ReservationConflict("request_id belongs to another user")
                return dict(existing)
            self._ensure_account(db, user_id)
            account = db.execute(
                "SELECT balance, unlimited FROM ai_entitlements WHERE user_id=?", (user_id,)
            ).fetchone()
            charged = 0
            if not account["unlimited"]:
                if int(account["balance"]) <= 0:
                    raise InsufficientCredits("Student AI credits exhausted")
                db.execute(
                    "UPDATE ai_entitlements SET balance=balance-1, updated_at=? WHERE user_id=?",
                    (self.database._now(), user_id),
                )
                charged = 1
            now = self.database._now()
            db.execute(
                """INSERT INTO ai_credit_reservations
                (request_id, user_id, status, charged, created_at, updated_at)
                VALUES (?, ?, 'reserved', ?, ?, ?)""",
                (request_id, user_id, charged, now, now),
            )
            row = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
        return dict(row)

    def commit_usage(self, request_id: str) -> dict:
        return self._transition(request_id, "committed")

    def release_reservation(self, request_id: str) -> dict:
        return self._transition(request_id, "released")

    def _transition(self, request_id: str, target: str) -> dict:
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
            if target == "released" and row["charged"]:
                db.execute(
                    "UPDATE ai_entitlements SET balance=balance+1, updated_at=? WHERE user_id=?",
                    (self.database._now(), row["user_id"]),
                )
            db.execute(
                "UPDATE ai_credit_reservations SET status=?, updated_at=? WHERE request_id=?",
                (target, self.database._now(), request_id),
            )
            updated = db.execute(
                "SELECT * FROM ai_credit_reservations WHERE request_id=?", (request_id,)
            ).fetchone()
        return dict(updated)
