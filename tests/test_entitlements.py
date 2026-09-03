from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.database import Database
from app.entitlements import InsufficientCredits, LocalEntitlementService, ReservationConflict


def service_with_user(tmp_path: Path, balance: int = 0, unlimited: bool = False):
    database = Database(tmp_path / "credits.db")
    database.initialize()
    user = database.create_user("Credits test")
    service = LocalEntitlementService(database)
    service.get_balance(user["id"])
    with database.connection() as db:
        db.execute(
            "UPDATE ai_entitlements SET balance=?, unlimited=? WHERE user_id=?",
            (balance, int(unlimited), user["id"]),
        )
    return database, service, user["id"]


def test_reserve_commit_and_retry_are_idempotent(tmp_path: Path) -> None:
    _, service, user_id = service_with_user(tmp_path, balance=2)
    first = service.reserve_credit(user_id, "request-1")
    retry = service.reserve_credit(user_id, "request-1")
    assert first["request_id"] == retry["request_id"]
    assert service.get_balance(user_id)["balance"] == 1
    assert service.commit_usage("request-1")["status"] == "committed"
    assert service.commit_usage("request-1")["status"] == "committed"
    assert service.get_balance(user_id)["balance"] == 1


def test_release_refunds_once_and_release_after_commit_fails(tmp_path: Path) -> None:
    _, service, user_id = service_with_user(tmp_path, balance=1)
    service.reserve_credit(user_id, "released")
    assert service.release_reservation("released")["status"] == "released"
    assert service.release_reservation("released")["status"] == "released"
    assert service.get_balance(user_id)["balance"] == 1

    service.reserve_credit(user_id, "committed")
    service.commit_usage("committed")
    with pytest.raises(ReservationConflict):
        service.release_reservation("committed")


def test_no_negative_balance_and_request_id_is_user_bound(tmp_path: Path) -> None:
    database, service, first_user = service_with_user(tmp_path, balance=0)
    with pytest.raises(InsufficientCredits):
        service.reserve_credit(first_user, "no-credit")
    assert service.get_balance(first_user)["balance"] == 0

    with database.connection() as db:
        db.execute("UPDATE ai_entitlements SET unlimited=1 WHERE user_id=?", (first_user,))
    service.reserve_credit(first_user, "shared-id")
    second_user = database.create_user("Second")
    with pytest.raises(ReservationConflict):
        service.reserve_credit(second_user["id"], "shared-id")


def test_concurrent_reserve_cannot_double_spend(tmp_path: Path) -> None:
    _, service, user_id = service_with_user(tmp_path, balance=1)

    def reserve(request_id: str) -> str:
        try:
            return service.reserve_credit(user_id, request_id)["status"]
        except InsufficientCredits:
            return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, ["race-a", "race-b"]))

    assert sorted(results) == ["insufficient", "reserved"]
    assert service.get_balance(user_id)["balance"] == 0
