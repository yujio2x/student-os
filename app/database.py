from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator
from uuid import uuid4


class LessonConflictError(ValueError):
    pass


class DeadlineConflictError(ValueError):
    pass


class ExternalIdentityConflict(ValueError):
    pass


class AdminActionConflict(ValueError):
    pass


class Database:
    """Small local-first store. All user-owned rows carry a user_id for future auth."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def initialize(self) -> None:
        with self.connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
                    subject TEXT NOT NULL CHECK(length(subject) BETWEEN 1 AND 120),
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    room TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    teacher TEXT NOT NULL DEFAULT '',
                    lesson_type TEXT NOT NULL DEFAULT '',
                    group_name TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    CHECK(starts_at < ends_at)
                );

                CREATE TABLE IF NOT EXISTS deadlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 160),
                    subject TEXT NOT NULL DEFAULT '',
                    due_at TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    user_id TEXT PRIMARY KEY,
                    theme TEXT NOT NULL DEFAULT 'light' CHECK(theme IN ('light', 'dark')),
                    schedule_view TEXT NOT NULL DEFAULT 'week' CHECK(schedule_view IN ('week', 'day')),
                    mobile_schedule_view TEXT NOT NULL DEFAULT 'day'
                        CHECK(mobile_schedule_view IN ('week', 'day')),
                    visible_fields TEXT NOT NULL DEFAULT 'room,teacher,lesson_type'
                );

                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS external_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    provider_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    username TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL DEFAULT '',
                    linked_at TEXT NOT NULL,
                    UNIQUE(provider, provider_user_id),
                    UNIQUE(provider, user_id)
                );

                CREATE TABLE IF NOT EXISTS telegram_auth_replays (
                    replay_key TEXT PRIMARY KEY,
                    used_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ai_entitlements (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
                    unlimited INTEGER NOT NULL DEFAULT 0 CHECK(unlimited IN (0, 1)),
                    free_trial_available INTEGER NOT NULL DEFAULT 1
                        CHECK(free_trial_available IN (0, 1)),
                    source TEXT NOT NULL DEFAULT 'core',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ai_credit_reservations (
                    request_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    status TEXT NOT NULL CHECK(status IN ('reserved', 'committed', 'released')),
                    charged INTEGER NOT NULL CHECK(charged IN (0, 1)),
                    amount INTEGER NOT NULL DEFAULT 1 CHECK(amount >= 0),
                    entitlement_source TEXT NOT NULL DEFAULT 'paid',
                    input_tokens INTEGER NOT NULL DEFAULT 0 CHECK(input_tokens >= 0),
                    output_tokens INTEGER NOT NULL DEFAULT 0 CHECK(output_tokens >= 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    committed_at TEXT,
                    released_at TEXT
                );

                CREATE TABLE IF NOT EXISTS telegram_star_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL DEFAULT 'telegram_stars'
                        CHECK(provider='telegram_stars'),
                    telegram_payment_charge_id TEXT NOT NULL UNIQUE,
                    telegram_user_id TEXT NOT NULL,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    product_id TEXT NOT NULL,
                    stars_paid INTEGER NOT NULL CHECK(stars_paid > 0),
                    credits_granted INTEGER NOT NULL CHECK(credits_granted > 0),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bridge_replays (
                    nonce TEXT PRIMARY KEY,
                    used_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS product_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_name TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK(kind IN ('product', 'student-ai')),
                    rating TEXT NOT NULL DEFAULT '' CHECK(rating IN ('', 'positive', 'negative')),
                    message TEXT NOT NULL DEFAULT '',
                    request_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, kind, request_id)
                );

                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    actor_user_id TEXT NOT NULL REFERENCES users(id),
                    action TEXT NOT NULL,
                    target_user_id TEXT REFERENCES users(id),
                    details TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_lessons_user_day
                    ON lessons(user_id, weekday, starts_at);
                CREATE INDEX IF NOT EXISTS idx_deadlines_user_due
                    ON deadlines(user_id, due_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_deadlines_deduplicate
                    ON deadlines(user_id, title, due_at, source);
                CREATE INDEX IF NOT EXISTS idx_sessions_user
                    ON sessions(user_id, expires_at);
                CREATE INDEX IF NOT EXISTS idx_product_events_name_created
                    ON product_events(event_name, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_product_events_deadline_once
                    ON product_events(user_id, event_name, source)
                    WHERE event_name='deadline_created';
                CREATE INDEX IF NOT EXISTS idx_feedback_created
                    ON feedback(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_admin_actions_created
                    ON admin_actions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_star_payments_user_created
                    ON telegram_star_payments(user_id, created_at DESC);
                """
            )
            columns = {
                str(row["name"]) for row in db.execute("PRAGMA table_info(preferences)").fetchall()
            }
            if "mobile_schedule_view" not in columns:
                db.execute(
                    "ALTER TABLE preferences ADD COLUMN mobile_schedule_view TEXT NOT NULL DEFAULT 'day'"
                )
            lesson_columns = {
                str(row["name"]) for row in db.execute("PRAGMA table_info(lessons)").fetchall()
            }
            if "location" not in lesson_columns:
                db.execute(
                    "ALTER TABLE lessons ADD COLUMN location TEXT NOT NULL DEFAULT ''"
                )
            reservation_columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(ai_credit_reservations)").fetchall()
            }
            if "input_tokens" not in reservation_columns:
                db.execute(
                    "ALTER TABLE ai_credit_reservations ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0"
                )
            if "output_tokens" not in reservation_columns:
                db.execute(
                    "ALTER TABLE ai_credit_reservations ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0"
                )
            if "amount" not in reservation_columns:
                db.execute(
                    "ALTER TABLE ai_credit_reservations ADD COLUMN amount INTEGER NOT NULL DEFAULT 1"
                )
            if "entitlement_source" not in reservation_columns:
                db.execute(
                    "ALTER TABLE ai_credit_reservations ADD COLUMN entitlement_source TEXT NOT NULL DEFAULT 'paid'"
                )
            if "committed_at" not in reservation_columns:
                db.execute("ALTER TABLE ai_credit_reservations ADD COLUMN committed_at TEXT")
            if "released_at" not in reservation_columns:
                db.execute("ALTER TABLE ai_credit_reservations ADD COLUMN released_at TEXT")
            entitlement_columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(ai_entitlements)").fetchall()
            }
            if "free_trial_available" not in entitlement_columns:
                db.execute(
                    "ALTER TABLE ai_entitlements ADD COLUMN free_trial_available INTEGER NOT NULL DEFAULT 1"
                )
            if "created_at" not in entitlement_columns:
                db.execute(
                    "ALTER TABLE ai_entitlements ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
                )
                db.execute(
                    "UPDATE ai_entitlements SET created_at=updated_at WHERE created_at=''"
                )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def create_user(self, display_name: str = "", role: str = "user") -> dict:
        user_id = str(uuid4())
        now = self._now()
        with self.connection() as db:
            db.execute(
                "INSERT INTO users(id, display_name, role, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, display_name, role, now, now),
            )
            db.execute("INSERT INTO preferences(user_id) VALUES (?)", (user_id,))
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row)

    def ensure_local_user(self) -> dict:
        """Create one stable development identity and migrate legacy local rows once."""
        with self.connection() as db:
            stored = db.execute(
                "SELECT value FROM app_meta WHERE key='development_user_id'"
            ).fetchone()
            user_id = str(stored["value"]) if stored else str(uuid4())
            now = self._now()
            db.execute(
                """INSERT OR IGNORE INTO users(id, display_name, role, created_at, last_seen_at)
                VALUES (?, 'Локальный студент', 'user', ?, ?)""",
                (user_id, now, now),
            )
            db.execute(
                "INSERT OR IGNORE INTO app_meta(key, value) VALUES ('development_user_id', ?)",
                (user_id,),
            )
            db.execute("UPDATE lessons SET user_id=? WHERE user_id='local-demo-user'", (user_id,))
            db.execute("UPDATE deadlines SET user_id=? WHERE user_id='local-demo-user'", (user_id,))
            legacy_preferences = db.execute(
                "SELECT * FROM preferences WHERE user_id='local-demo-user'"
            ).fetchone()
            if legacy_preferences:
                db.execute(
                    """INSERT OR IGNORE INTO preferences
                    (user_id, theme, schedule_view, mobile_schedule_view, visible_fields)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        user_id, legacy_preferences["theme"], legacy_preferences["schedule_view"],
                        legacy_preferences["mobile_schedule_view"], legacy_preferences["visible_fields"],
                    ),
                )
                db.execute("DELETE FROM preferences WHERE user_id='local-demo-user'")
            else:
                db.execute("INSERT OR IGNORE INTO preferences(user_id) VALUES (?)", (user_id,))
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row)

    def create_session(
        self, token_hash: str, user_id: str, csrf_token: str, expires_at: str
    ) -> None:
        with self.connection() as db:
            db.execute(
                """INSERT INTO sessions
                (token_hash, user_id, csrf_token, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)""",
                (token_hash, user_id, csrf_token, self._now(), expires_at),
            )

    def session(self, token_hash: str) -> dict | None:
        now = self._now()
        with self.connection() as db:
            row = db.execute(
                """SELECT s.token_hash, s.user_id, s.csrf_token, s.expires_at,
                u.display_name, u.role
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?""",
                (token_hash, now),
            ).fetchone()
            if row:
                db.execute("UPDATE users SET last_seen_at=? WHERE id=?", (now, row["user_id"]))
        return dict(row) if row else None

    def revoke_session(self, token_hash: str) -> bool:
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (self._now(), token_hash),
            )
            return cursor.rowcount == 1

    def consume_telegram_auth(self, replay_key: str) -> bool:
        with self.connection() as db:
            try:
                db.execute(
                    "INSERT INTO telegram_auth_replays(replay_key, used_at) VALUES (?, ?)",
                    (replay_key, self._now()),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def consume_bridge_nonce(self, nonce: str) -> bool:
        with self.connection() as db:
            try:
                db.execute(
                    "INSERT INTO bridge_replays(nonce, used_at) VALUES (?, ?)",
                    (nonce, self._now()),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def telegram_login_user(
        self, telegram_id: str, username: str, display_name: str
    ) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT u.* FROM external_identities e
                JOIN users u ON u.id=e.user_id
                WHERE e.provider='telegram' AND e.provider_user_id=?""",
                (telegram_id,),
            ).fetchone()
            if row:
                db.execute(
                    """UPDATE external_identities SET username=?, display_name=?
                    WHERE provider='telegram' AND provider_user_id=?""",
                    (username, display_name, telegram_id),
                )
                return dict(row)
            user_id = str(uuid4())
            now = self._now()
            db.execute(
                "INSERT INTO users(id, display_name, role, created_at, last_seen_at) VALUES (?, ?, 'user', ?, ?)",
                (user_id, display_name, now, now),
            )
            db.execute("INSERT INTO preferences(user_id) VALUES (?)", (user_id,))
            db.execute(
                """INSERT INTO external_identities
                (provider, provider_user_id, user_id, username, display_name, linked_at)
                VALUES ('telegram', ?, ?, ?, ?, ?)""",
                (telegram_id, user_id, username, display_name, now),
            )
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row)

    def merge_guest_with_telegram(
        self, guest_user_id: str, telegram_id: str, username: str, display_name: str
    ) -> dict:
        """Atomically attach a new identity or merge guest-owned core data.

        Lessons have independent IDs and are moved as-is. Exact duplicate deadlines
        keep the authenticated account's copy. Singleton preferences and all
        entitlement/payment state stay with the authenticated account, so a guest
        can never duplicate trials or credits during linking.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            guest = db.execute("SELECT * FROM users WHERE id=?", (guest_user_id,)).fetchone()
            if guest is None:
                raise ExternalIdentityConflict("Гостевая сессия больше не существует")
            guest_identity = db.execute(
                "SELECT provider_user_id FROM external_identities WHERE provider='telegram' AND user_id=?",
                (guest_user_id,),
            ).fetchone()
            if guest_identity and guest_identity["provider_user_id"] != telegram_id:
                raise ExternalIdentityConflict("У пользователя уже связан другой Telegram-аккаунт")

            existing = db.execute(
                """SELECT u.* FROM external_identities e JOIN users u ON u.id=e.user_id
                WHERE e.provider='telegram' AND e.provider_user_id=?""",
                (telegram_id,),
            ).fetchone()
            now = self._now()
            if existing is None:
                db.execute(
                    """INSERT INTO external_identities
                    (provider, provider_user_id, user_id, username, display_name, linked_at)
                    VALUES ('telegram', ?, ?, ?, ?, ?)
                    ON CONFLICT(provider, provider_user_id) DO UPDATE SET
                    username=excluded.username, display_name=excluded.display_name""",
                    (telegram_id, guest_user_id, username, display_name, now),
                )
                db.execute(
                    "UPDATE users SET display_name=?, last_seen_at=? WHERE id=?",
                    (display_name, now, guest_user_id),
                )
                row = db.execute("SELECT * FROM users WHERE id=?", (guest_user_id,)).fetchone()
                return dict(row)

            target_user_id = str(existing["id"])
            db.execute(
                """UPDATE external_identities SET username=?, display_name=?
                WHERE provider='telegram' AND provider_user_id=?""",
                (username, display_name, telegram_id),
            )
            if target_user_id != guest_user_id:
                guest_deadlines = db.execute(
                    "SELECT id, title, due_at, source FROM deadlines WHERE user_id=?",
                    (guest_user_id,),
                ).fetchall()
                for deadline in guest_deadlines:
                    duplicate = db.execute(
                        """SELECT 1 FROM deadlines
                        WHERE user_id=? AND title=? AND due_at=? AND source=?""",
                        (target_user_id, deadline["title"], deadline["due_at"], deadline["source"]),
                    ).fetchone()
                    if duplicate:
                        db.execute(
                            "DELETE FROM deadlines WHERE id=? AND user_id=?",
                            (deadline["id"], guest_user_id),
                        )
                db.execute("UPDATE lessons SET user_id=? WHERE user_id=?", (target_user_id, guest_user_id))
                db.execute("UPDATE deadlines SET user_id=? WHERE user_id=?", (target_user_id, guest_user_id))
                db.execute(
                    "UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                    (now, guest_user_id),
                )
            db.execute(
                "UPDATE users SET display_name=?, last_seen_at=? WHERE id=?",
                (display_name, now, target_user_id),
            )
            row = db.execute("SELECT * FROM users WHERE id=?", (target_user_id,)).fetchone()
        return dict(row)

    def link_telegram_identity(
        self, user_id: str, telegram_id: str, username: str, display_name: str
    ) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            by_telegram = db.execute(
                """SELECT * FROM external_identities
                WHERE provider='telegram' AND provider_user_id=?""",
                (telegram_id,),
            ).fetchone()
            if by_telegram and by_telegram["user_id"] != user_id:
                raise ExternalIdentityConflict("Telegram-аккаунт уже связан с другим пользователем")
            by_user = db.execute(
                """SELECT * FROM external_identities
                WHERE provider='telegram' AND user_id=?""",
                (user_id,),
            ).fetchone()
            if by_user and by_user["provider_user_id"] != telegram_id:
                raise ExternalIdentityConflict("У пользователя уже связан другой Telegram-аккаунт")
            now = self._now()
            db.execute(
                """INSERT INTO external_identities
                (provider, provider_user_id, user_id, username, display_name, linked_at)
                VALUES ('telegram', ?, ?, ?, ?, ?)
                ON CONFLICT(provider, provider_user_id) DO UPDATE SET
                username=excluded.username, display_name=excluded.display_name""",
                (telegram_id, user_id, username, display_name, now),
            )
            row = db.execute(
                "SELECT * FROM external_identities WHERE provider='telegram' AND user_id=?",
                (user_id,),
            ).fetchone()
        return dict(row)

    def telegram_identity(self, user_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                """SELECT provider_user_id, username, display_name, linked_at
                FROM external_identities WHERE provider='telegram' AND user_id=?""",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_user_role(self, user_id: str, role: str) -> bool:
        if role not in {"user", "admin"}:
            raise ValueError("invalid role")
        with self.connection() as db:
            cursor = db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
            return cursor.rowcount == 1

    def record_event(self, user_id: str, event_name: str, source: str = "") -> None:
        try:
            with self.connection() as db:
                db.execute(
                    """INSERT OR IGNORE INTO product_events
                    (user_id, event_name, source, created_at) VALUES (?, ?, ?, ?)""",
                    (user_id, event_name, source[:80], self._now()),
                )
        except sqlite3.Error:
            # Minimal analytics must never break a completed user operation.
            return

    def record_feedback(
        self, user_id: str, kind: str, rating: str, message: str, request_id: str
    ) -> dict:
        with self.connection() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO feedback
                (user_id, kind, rating, message, request_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, kind, rating, message, request_id, self._now()),
            )
            row = db.execute(
                "SELECT * FROM feedback WHERE user_id=? AND kind=? AND request_id=?",
                (user_id, kind, request_id),
            ).fetchone()
        result = dict(row)
        result["created"] = cursor.rowcount == 1
        return result

    def admin_overview(self) -> dict:
        with self.connection() as db:
            users = db.execute(
                """SELECT COUNT(*) total,
                SUM(CASE WHEN last_seen_at >= ? THEN 1 ELSE 0 END) recent
                FROM users""",
                ((datetime.now(UTC) - timedelta(days=7)).isoformat(timespec="seconds"),),
            ).fetchone()
            events = {
                str(row["event_name"]): int(row["count"])
                for row in db.execute(
                    "SELECT event_name, COUNT(*) count FROM product_events GROUP BY event_name"
                ).fetchall()
            }
            feedback = db.execute(
                """SELECT COUNT(*) total,
                SUM(CASE WHEN rating='positive' THEN 1 ELSE 0 END) positive,
                SUM(CASE WHEN rating='negative' THEN 1 ELSE 0 END) negative
                FROM feedback"""
            ).fetchone()
            reservations = db.execute(
                """SELECT COUNT(*) total,
                SUM(CASE WHEN status='committed' THEN 1 ELSE 0 END) successful,
                SUM(CASE WHEN status='released' THEN 1 ELSE 0 END) failed
                FROM ai_credit_reservations"""
            ).fetchone()
            payments = db.execute(
                """SELECT COUNT(*) total, COALESCE(SUM(stars_paid), 0) stars
                FROM telegram_star_payments"""
            ).fetchone()
            ledger = db.execute(
                """SELECT COALESCE(SUM(balance), 0) credits,
                COALESCE(SUM(unlimited), 0) unlimited_users FROM ai_entitlements"""
            ).fetchone()
            photo_counts = (0, 0, 0)
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='photo_requests'").fetchone():
                photo_counts = db.execute("SELECT COUNT(*) requests, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) successful, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed FROM photo_requests").fetchone()
        return {
            "total_users": int(users["total"] or 0),
            "recent_users_7d": int(users["recent"] or 0),
            "student_ai_uses": events.get("student_ai_used", 0),
            "student_ai_requests": int(reservations["total"] or 0) + int(photo_counts[0] or 0),
            "student_ai_successful": int(reservations["successful"] or 0) + int(photo_counts[1] or 0),
            "student_ai_failed": int(reservations["failed"] or 0) + int(photo_counts[2] or 0),
            "stars_payments": int(payments["total"] or 0),
            "stars_received": int(payments["stars"] or 0),
            "credits_outstanding": int(ledger["credits"] or 0),
            "unlimited_users": int(ledger["unlimited_users"] or 0),
            "schedule_imports": events.get("schedule_imported", 0),
            "deadlines_created": events.get("deadline_created", 0),
            "feedback_total": int(feedback["total"] or 0),
            "feedback_positive": int(feedback["positive"] or 0),
            "feedback_negative": int(feedback["negative"] or 0),
        }

    def admin_users(self, query: str, limit: int, offset: int) -> dict:
        normalized = query.strip().casefold()
        where = ""
        params: list[object] = []
        if normalized:
            where = """WHERE lower(u.id) LIKE ? OR lower(u.display_name) LIKE ?
            OR lower(COALESCE(e.username, '')) LIKE ? OR e.provider_user_id=?"""
            like = f"%{normalized}%"
            params = [like, like, like, normalized]
        with self.connection() as db:
            total = int(db.execute(
                f"""SELECT COUNT(*) FROM users u LEFT JOIN external_identities e
                ON e.user_id=u.id AND e.provider='telegram' {where}""", params,
            ).fetchone()[0])
            rows = db.execute(
                f"""SELECT u.id, u.display_name, u.role, u.created_at, u.last_seen_at,
                e.provider_user_id telegram_id, e.username telegram_username,
                COALESCE(a.balance, 0) balance, COALESCE(a.unlimited, 0) unlimited,
                COALESCE(a.free_trial_available, 1) free_trial_available,
                COALESCE(a.source, 'core') entitlement_source
                FROM users u
                LEFT JOIN external_identities e ON e.user_id=u.id AND e.provider='telegram'
                LEFT JOIN ai_entitlements a ON a.user_id=u.id
                {where} ORDER BY u.created_at DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return {"users": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def admin_user(self, user_id: str) -> dict | None:
        result = self.admin_users(user_id, 2, 0)
        exact = next((row for row in result["users"] if row["id"] == user_id), None)
        if exact is None:
            return None
        with self.connection() as db:
            exact["usage"] = {
                str(row["event_name"]): int(row["count"])
                for row in db.execute(
                    """SELECT event_name, COUNT(*) count FROM product_events
                    WHERE user_id=? GROUP BY event_name""", (user_id,),
                ).fetchall()
            }
            exact["payments"] = [dict(row) for row in db.execute(
                """SELECT product_id, stars_paid, credits_granted, created_at
                FROM telegram_star_payments WHERE user_id=? ORDER BY id DESC LIMIT 20""",
                (user_id,),
            ).fetchall()]
            totals = db.execute(
                """SELECT COUNT(*) requests,
                COALESCE(SUM(CASE WHEN status='committed' THEN 1 ELSE 0 END), 0) successful,
                COALESCE(SUM(input_tokens), 0) input_tokens,
                COALESCE(SUM(output_tokens), 0) output_tokens
                FROM ai_credit_reservations WHERE user_id=?""",
                (user_id,),
            ).fetchone()
            exact["ai_totals"] = dict(totals)
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='photo_requests'").fetchone():
                photo_totals = db.execute("""SELECT COUNT(*) requests, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) successful,
                    SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens
                    FROM photo_requests WHERE user_id=?""", (user_id,)).fetchone()
                for key in exact["ai_totals"]:
                    exact["ai_totals"][key] += int(photo_totals[key] or 0)
        return exact

    def admin_feedback(self, limit: int, offset: int) -> dict:
        with self.connection() as db:
            total = int(db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0])
            rows = db.execute(
                """SELECT id, user_id, kind, rating, message, created_at
                FROM feedback ORDER BY id DESC LIMIT ? OFFSET ?""", (limit, offset),
            ).fetchall()
        return {"feedback": [dict(row) for row in rows], "total": total}

    def admin_actions(self, target_user_id: str | None, limit: int, offset: int) -> dict:
        where = "WHERE target_user_id=?" if target_user_id else ""
        params: tuple[object, ...] = (target_user_id,) if target_user_id else ()
        with self.connection() as db:
            total = int(db.execute(
                f"SELECT COUNT(*) FROM admin_actions {where}", params
            ).fetchone()[0])
            rows = db.execute(
                f"""SELECT id, actor_user_id, action, target_user_id, details, reason, result, created_at
                FROM admin_actions {where} ORDER BY id DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return {"actions": [dict(row) for row in rows], "total": total}

    def admin_adjust_credits(
        self, actor_user_id: str, target_user_id: str, delta: int,
        reason: str, request_id: str,
    ) -> int | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT actor_user_id, action, target_user_id, details, reason, result FROM admin_actions WHERE request_id=?", (request_id,)
            ).fetchone()
            if prior:
                if (
                    prior["actor_user_id"] != actor_user_id
                    or prior["action"] != "credits_adjusted"
                    or prior["target_user_id"] != target_user_id
                    or prior["details"] != f"delta={delta}"
                    or prior["reason"] != reason
                ):
                    raise AdminActionConflict("request_id already used for another action")
                return int(prior["result"])
            cursor = db.execute(
                """UPDATE ai_entitlements SET balance=balance+?, updated_at=?
                WHERE user_id=? AND balance+?>=0""",
                (delta, self._now(), target_user_id, delta),
            )
            if cursor.rowcount != 1:
                return None
            balance = int(db.execute(
                "SELECT balance FROM ai_entitlements WHERE user_id=?", (target_user_id,)
            ).fetchone()[0])
            db.execute(
                """INSERT INTO admin_actions
                (request_id, actor_user_id, action, target_user_id, details, reason, result, created_at)
                VALUES (?, ?, 'credits_adjusted', ?, ?, ?, ?, ?)""",
                (request_id, actor_user_id, target_user_id, f"delta={delta}", reason, str(balance), self._now()),
            )
        return balance

    def admin_set_unlimited(
        self, actor_user_id: str, target_user_id: str, enabled: bool,
        reason: str, request_id: str,
    ) -> bool | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT actor_user_id, action, target_user_id, details, reason, result FROM admin_actions WHERE request_id=?", (request_id,)
            ).fetchone()
            if prior:
                if (
                    prior["actor_user_id"] != actor_user_id
                    or prior["action"] != "unlimited_changed"
                    or prior["target_user_id"] != target_user_id
                    or prior["details"] != f"enabled={int(enabled)}"
                    or prior["reason"] != reason
                ):
                    raise AdminActionConflict("request_id already used for another action")
                return prior["result"] == "1"
            cursor = db.execute(
                "UPDATE ai_entitlements SET unlimited=?, updated_at=? WHERE user_id=?",
                (int(enabled), self._now(), target_user_id),
            )
            if cursor.rowcount != 1:
                return None
            db.execute(
                """INSERT INTO admin_actions
                (request_id, actor_user_id, action, target_user_id, details, reason, result, created_at)
                VALUES (?, ?, 'unlimited_changed', ?, ?, ?, ?, ?)""",
                (request_id, actor_user_id, target_user_id, f"enabled={int(enabled)}", reason, str(int(enabled)), self._now()),
            )
        return enabled

    def admin_restore_trial(
        self, actor_user_id: str, target_user_id: str,
        reason: str, request_id: str,
    ) -> bool | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                """SELECT actor_user_id, action, target_user_id, details, reason, result
                FROM admin_actions WHERE request_id=?""",
                (request_id,),
            ).fetchone()
            if prior:
                if (
                    prior["actor_user_id"] != actor_user_id
                    or prior["action"] != "trial_restored"
                    or prior["target_user_id"] != target_user_id
                    or prior["reason"] != reason
                ):
                    raise AdminActionConflict("request_id already used for another action")
                return prior["result"] == "1"
            cursor = db.execute(
                """UPDATE ai_entitlements SET free_trial_available=1, updated_at=?
                WHERE user_id=?""",
                (self._now(), target_user_id),
            )
            if cursor.rowcount != 1:
                return None
            db.execute(
                """INSERT INTO admin_actions
                (request_id, actor_user_id, action, target_user_id, details, reason, result, created_at)
                VALUES (?, ?, 'trial_restored', ?, 'available=1', ?, '1', ?)""",
                (request_id, actor_user_id, target_user_id, reason, self._now()),
            )
        return True

    def seed_demo(self, user_id: str) -> None:
        with self.connection() as db:
            existing = db.execute(
                "SELECT 1 FROM lessons WHERE user_id=? LIMIT 1", (user_id,)
            ).fetchone()
            if existing:
                return
            lessons = [
                (0, "Алгоритмы", "09:00", "10:20", "B-204", "", "А. Иманов", "Лекция"),
                (0, "Английский язык", "11:00", "12:20", "A-113", "", "Д. Ким", "Практика"),
                (1, "Базы данных", "10:00", "11:20", "C-310", "", "М. Садыкова", "Лабораторная"),
                (2, "Математика", "09:30", "10:50", "B-118", "", "Р. Алиев", "Практика"),
                (3, "Алгоритмы", "13:00", "14:20", "B-204", "", "А. Иманов", "Практика"),
                (4, "Проектирование", "11:00", "12:20", "D-402", "", "Е. Пак", "Лекция"),
            ]
            db.executemany(
                """INSERT INTO lessons
                (user_id, weekday, subject, starts_at, ends_at, room, location, teacher, lesson_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(user_id, *lesson) for lesson in lessons],
            )
            db.execute("INSERT OR IGNORE INTO preferences(user_id) VALUES (?)", (user_id,))

    def lessons(self, user_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM lessons WHERE user_id=? ORDER BY weekday, starts_at", (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _lesson_conflict(
        db: sqlite3.Connection, user_id: str, weekday: int, starts_at: str,
        ends_at: str, exclude_id: int | None = None,
    ) -> sqlite3.Row | None:
        query = (
            "SELECT * FROM lessons WHERE user_id=? AND weekday=? "
            "AND starts_at < ? AND ends_at > ?"
        )
        params: list[object] = [user_id, weekday, ends_at, starts_at]
        if exclude_id is not None:
            query += " AND id<>?"
            params.append(exclude_id)
        query += " ORDER BY starts_at LIMIT 1"
        return db.execute(query, params).fetchone()

    def add_lesson(self, user_id: str, lesson: dict) -> dict:
        with self.connection() as db:
            conflict = self._lesson_conflict(
                db, user_id, lesson["weekday"], lesson["starts_at"], lesson["ends_at"]
            )
            if conflict:
                raise LessonConflictError(
                    f"Время пересекается с занятием «{conflict['subject']}» "
                    f"({conflict['starts_at']}–{conflict['ends_at']})"
                )
            cursor = db.execute(
                """INSERT INTO lessons
                (user_id, weekday, subject, starts_at, ends_at, room, location, teacher,
                 lesson_type, group_name, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, lesson["weekday"], lesson["subject"], lesson["starts_at"],
                    lesson["ends_at"], lesson["room"], lesson["location"], lesson["teacher"],
                    lesson["lesson_type"], lesson["group_name"], lesson["notes"],
                ),
            )
            row = db.execute("SELECT * FROM lessons WHERE id=?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def update_lesson(self, user_id: str, lesson_id: int, lesson: dict) -> dict | None:
        with self.connection() as db:
            owned = db.execute(
                "SELECT 1 FROM lessons WHERE id=? AND user_id=?", (lesson_id, user_id)
            ).fetchone()
            if owned is None:
                return None
            conflict = self._lesson_conflict(
                db, user_id, lesson["weekday"], lesson["starts_at"],
                lesson["ends_at"], exclude_id=lesson_id,
            )
            if conflict:
                raise LessonConflictError(
                    f"Время пересекается с занятием «{conflict['subject']}» "
                    f"({conflict['starts_at']}–{conflict['ends_at']})"
                )
            db.execute(
                """UPDATE lessons SET weekday=?, subject=?, starts_at=?, ends_at=?, room=?,
                location=?, teacher=?, lesson_type=?, group_name=?, notes=?
                WHERE id=? AND user_id=?""",
                (
                    lesson["weekday"], lesson["subject"], lesson["starts_at"],
                    lesson["ends_at"], lesson["room"], lesson["location"], lesson["teacher"],
                    lesson["lesson_type"], lesson["group_name"], lesson["notes"],
                    lesson_id, user_id,
                ),
            )
            row = db.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        return dict(row)

    def delete_lesson(self, user_id: str, lesson_id: int) -> bool:
        with self.connection() as db:
            cursor = db.execute(
                "DELETE FROM lessons WHERE id=? AND user_id=?", (lesson_id, user_id)
            )
            return cursor.rowcount == 1

    def import_lessons(self, user_id: str, lessons: list[dict]) -> list[dict]:
        """Import a reviewed preview atomically; never accepts partial persistence."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for index, lesson in enumerate(lessons):
                for previous in lessons[:index]:
                    if (
                        previous["weekday"] == lesson["weekday"]
                        and previous["starts_at"] < lesson["ends_at"]
                        and previous["ends_at"] > lesson["starts_at"]
                    ):
                        raise LessonConflictError(
                            f"Строки импорта «{previous['subject']}» и «{lesson['subject']}» "
                            "пересекаются по времени"
                        )
                conflict = self._lesson_conflict(
                    db, user_id, lesson["weekday"], lesson["starts_at"], lesson["ends_at"]
                )
                if conflict:
                    raise LessonConflictError(
                        f"«{lesson['subject']}» пересекается с существующим занятием "
                        f"«{conflict['subject']}»"
                    )

            inserted_ids: list[int] = []
            for lesson in lessons:
                cursor = db.execute(
                    """INSERT INTO lessons
                    (user_id, weekday, subject, starts_at, ends_at, room, location, teacher,
                     lesson_type, group_name, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id, lesson["weekday"], lesson["subject"], lesson["starts_at"],
                        lesson["ends_at"], lesson["room"], lesson["location"], lesson["teacher"],
                        lesson["lesson_type"], lesson["group_name"], lesson["notes"],
                    ),
                )
                inserted_ids.append(int(cursor.lastrowid))
            placeholders = ",".join("?" for _ in inserted_ids)
            rows = db.execute(
                f"SELECT * FROM lessons WHERE id IN ({placeholders}) ORDER BY weekday, starts_at",
                inserted_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def deadlines(self, user_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM deadlines WHERE user_id=? ORDER BY due_at", (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def preferences(self, user_id: str) -> dict:
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO preferences(user_id) VALUES (?)", (user_id,))
            row = db.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,)).fetchone()
        result = dict(row)
        result["visible_fields"] = [item for item in result["visible_fields"].split(",") if item]
        return result

    def update_preferences(
        self, user_id: str, theme: str, schedule_view: str,
        mobile_schedule_view: str, visible_fields: list[str],
    ) -> dict:
        with self.connection() as db:
            db.execute(
                """INSERT INTO preferences
                (user_id, theme, schedule_view, mobile_schedule_view, visible_fields)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET theme=excluded.theme,
                schedule_view=excluded.schedule_view,
                mobile_schedule_view=excluded.mobile_schedule_view,
                visible_fields=excluded.visible_fields""",
                (user_id, theme, schedule_view, mobile_schedule_view, ",".join(visible_fields)),
            )
        return self.preferences(user_id)

    def add_deadline(
        self, user_id: str, title: str, subject: str, due_at: str,
        description: str, source: str,
    ) -> dict:
        with self.connection() as db:
            db.execute(
                """INSERT OR IGNORE INTO deadlines
                (user_id, title, subject, due_at, description, source)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, title, subject, due_at, description, source),
            )
            row = db.execute(
                """SELECT * FROM deadlines
                WHERE user_id=? AND title=? AND due_at=? AND source=?""",
                (user_id, title, due_at, source),
            ).fetchone()
        return dict(row)

    def set_deadline_completed(self, user_id: str, deadline_id: int, completed: bool) -> dict | None:
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE deadlines SET completed=? WHERE id=? AND user_id=?",
                (int(completed), deadline_id, user_id),
            )
            if cursor.rowcount != 1:
                return None
            row = db.execute("SELECT * FROM deadlines WHERE id=?", (deadline_id,)).fetchone()
        return dict(row)

    def update_deadline(
        self, user_id: str, deadline_id: int, title: str, subject: str, due_at: str,
        description: str, completed: bool,
    ) -> dict | None:
        with self.connection() as db:
            try:
                cursor = db.execute(
                    """UPDATE deadlines SET title=?, subject=?, due_at=?, description=?, completed=?
                    WHERE id=? AND user_id=?""",
                    (title, subject, due_at, description, int(completed), deadline_id, user_id),
                )
            except sqlite3.IntegrityError as exc:
                raise DeadlineConflictError("Такой дедлайн уже существует") from exc
            if cursor.rowcount != 1:
                return None
            row = db.execute(
                "SELECT * FROM deadlines WHERE id=? AND user_id=?", (deadline_id, user_id)
            ).fetchone()
        return dict(row)

    def delete_deadline(self, user_id: str, deadline_id: int) -> bool:
        with self.connection() as db:
            cursor = db.execute(
                "DELETE FROM deadlines WHERE id=? AND user_id=?", (deadline_id, user_id)
            )
            return cursor.rowcount == 1
