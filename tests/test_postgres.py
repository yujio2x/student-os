"""Real PostgreSQL regressions; isolated schemas, never delete public data."""
import importlib
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from app.postgres import PostgresDatabase, translate


def test_sql_translation_keeps_literals_and_parameters_separate():
    assert translate("SELECT '?' AS literal, ? AS bound")[0] == "SELECT '?' AS literal, %s AS bound"
    assert "ON CONFLICT DO NOTHING RETURNING id" in translate("INSERT OR IGNORE INTO lessons(subject) VALUES (?)")[0]
    with pytest.raises(ValueError):
        translate("PRAGMA foreign_keys=OFF")


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_cloud_config_requires_postgres(monkeypatch, environment):
    from app.config import load_settings
    monkeypatch.setattr("app.config.load_dotenv", lambda: None)
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        load_settings()


@pytest.fixture
def pg_factory(monkeypatch):
    url = os.getenv("STUDENT_OS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL test database not configured")
    created = {}
    def factory(path):
        key = str(path)
        if key not in created:
            schema = "test_" + uuid4().hex
            try:
                with psycopg.connect(url, autocommit=True, connect_timeout=10) as connection:
                    connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            except psycopg.Error:
                raise RuntimeError("PostgreSQL test setup unavailable") from None
            created[key] = PostgresDatabase(url, schema=schema)
        return created[key]
    monkeypatch.setattr("app.main.Database", factory)
    yield factory
    for database in created.values():
        # Only this fixture's generated, disposable test schema may be removed.
        assert database.schema.startswith("test_") and len(database.schema) == 37
        with psycopg.connect(url, autocommit=True, connect_timeout=10) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(database.schema)))


CASES = [
    ("test_entitlements", name) for name in [
        "test_reserve_commit_and_retry_are_idempotent",
        "test_release_refunds_once_and_release_after_commit_fails",
        "test_no_negative_balance_and_request_id_is_user_bound",
        "test_concurrent_reserve_cannot_double_spend",
        "test_shared_trial_is_atomic_and_failure_restores_it",
        "test_unlimited_never_decrements_paid_balance",
        "test_concurrent_trial_is_shared_exactly_once",
    ]
] + [
    ("test_auth", "test_missing_invalid_and_expired_sessions_are_rejected"),
    ("test_auth", "test_login_rotates_session_and_logout_prevents_reuse"),
    ("test_auth", "test_mutations_require_csrf_and_production_has_no_dev_login"),
    ("test_auth", "test_dev_admin_is_explicit_and_impossible_in_production"),
    ("test_admin_feedback", "test_admin_routes_deny_normal_user_on_page_and_api"),
    ("test_admin_feedback", "test_feedback_is_minimal_idempotent_and_aggregated"),
    ("test_export_pwa", "test_export_is_authenticated_owned_versioned_and_secret_free"),
    ("test_admin_feedback", "test_admin_credit_mutations_are_bounded_idempotent_and_audited"),
    ("test_bridge_api", "test_same_telegram_identity_resolves_to_one_internal_user"),
    ("test_bridge_api", "test_products_and_telegram_star_payments_are_core_validated"),
    ("test_bridge_api", "test_bridge_rejects_bad_hmac_stale_replay_and_tampering"),
    ("test_telegram_oidc", "test_pkce_cookie_binding_replay_owner_and_logout"),
    ("test_deadline_management", "test_missing_and_foreign_deadlines_cannot_be_changed"),
]


@pytest.mark.parametrize("module_name,test_name", CASES)
def test_existing_domain_on_postgres(pg_factory, monkeypatch, tmp_path, module_name, test_name):
    module = importlib.import_module(module_name)
    if hasattr(module, "Database"):
        monkeypatch.setattr(module, "Database", pg_factory)
    getattr(module, test_name)(tmp_path)


def test_migration_restart_replay_and_rollback(pg_factory, tmp_path):
    database = pg_factory(tmp_path / "migration")
    database.initialize()
    user = database.create_user("Қазақша 😀")
    database.initialize()
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
    assert database.consume_bridge_nonce("nonce-one")
    assert not database.consume_bridge_nonce("nonce-one")
    assert database.consume_telegram_auth("auth-one")
    assert not database.consume_telegram_auth("auth-one")
    with pytest.raises(RuntimeError):
        with database.connection() as connection:
            connection.execute("UPDATE users SET display_name=? WHERE id=?", ("rollback", user["id"]))
            raise RuntimeError("synthetic rollback")
    with database.connection() as connection:
        assert connection.execute("SELECT display_name FROM users WHERE id=?", (user["id"],)).fetchone()[0] == "Қазақша 😀"


def test_photo_sessions_on_postgres(pg_factory, monkeypatch, tmp_path):
    module = importlib.import_module("test_photo_service")
    monkeypatch.setattr(module, "Database", pg_factory)
    photo = module.photo.__wrapped__(tmp_path)
    original = photo[2].recognize_photo
    def recognize_without_transaction(data, mime):
        assert photo[0].database._slots._value == 4
        return original(data, mime)
    photo[2].recognize_photo = recognize_without_transaction
    module.test_validation_before_any_ai_and_trial_setup(photo)


def test_migration_failure_is_atomic(pg_factory, monkeypatch, tmp_path):
    import app.postgres as module
    database = pg_factory(tmp_path / "failed-migration")
    database.initialize()
    directory = tmp_path / "migrations"
    directory.mkdir()
    for path in module.MIGRATIONS.glob("*.sql"):
        (directory / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    (directory / "002_failure.sql").write_text("CREATE TABLE must_rollback(id INTEGER); SELECT 1/0;", encoding="utf-8")
    monkeypatch.setattr(module, "MIGRATIONS", directory)
    with pytest.raises(psycopg.Error):
        database.initialize()
    with database.raw_connection() as connection:
        assert connection.execute("SELECT to_regclass('must_rollback') AS name").fetchone()[0] is None
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_restore_on_postgres(pg_factory, tmp_path):
    module = importlib.import_module("test_restore")
    setup = module.setup.__wrapped__(tmp_path)
    state = next(setup)
    try:
        module.test_owned_atomic_roundtrip_and_no_implicit_write(state)
    finally:
        setup.close()
