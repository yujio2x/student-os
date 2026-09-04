"""Explicit PostgreSQL adapter for the existing repository SQL contract.

Beta serializes short repository transactions with a database advisory lock. The
lock is never held across an AI/network call. Connections are bounded and closed
at every unit-of-work boundary (no idle sockets across Eco sleeps).
"""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import re
import sqlite3
import threading
from urllib.parse import urlsplit

import psycopg
from psycopg import sql

from app.database import Database

CORE_LOCK = 734923401
MIGRATIONS = Path(__file__).parent / "migrations" / "postgres"
SERIAL_TABLES = {"lessons", "deadlines", "external_identities", "telegram_star_payments",
                 "product_events", "feedback", "admin_actions"}


class Record(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def record_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Record(zip(names, values))


def translate(statement):
    """Translate only the legacy dialect features used by this repository.

    Values always remain bound parameters. Quoted SQL literals are not rewritten.
    Unsupported SQLite metadata/DDL fails closed instead of being guessed.
    """
    statement = statement.strip().rstrip(";")
    if statement == "BEGIN IMMEDIATE":
        return "SELECT 1", False  # lock acquired before the first repository read
    if statement == "SELECT 1 FROM sqlite_master WHERE type='table' AND name='photo_requests'":
        return "SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='photo_requests'", False
    if re.search(r"\b(PRAGMA|AUTOINCREMENT|sqlite_master)\b", statement, re.I):
        raise ValueError("Unsupported repository SQL dialect")
    ignore = bool(re.match(r"INSERT OR IGNORE\b", statement, re.I))
    statement = re.sub(r"^INSERT OR IGNORE\b", "INSERT", statement, flags=re.I)
    parts = re.split(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")", statement)
    statement = "".join(part.replace("%", "%%").replace("?", "%s") if i % 2 == 0
                        else part.replace("%", "%%") for i, part in enumerate(parts))
    if ignore:
        statement += " ON CONFLICT DO NOTHING"
    inserted = re.match(r"INSERT\s+INTO\s+(\w+)\b", statement, re.I)
    returning = bool(inserted and inserted[1].lower() in SERIAL_TABLES)
    if returning:
        statement += " RETURNING id"
    return statement, returning


class Cursor:
    def __init__(self, cursor, returning=False):
        self.cursor, self.rowcount = cursor, cursor.rowcount
        self.lastrowid = None
        if returning:
            row = cursor.fetchone()
            self.lastrowid = row["id"] if row else None

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __iter__(self):
        return iter(self.cursor)


class RepositoryConnection:
    def __init__(self, connection):
        self.raw = connection

    def execute(self, statement, parameters=()):
        statement, returning = translate(statement)
        if statement.lstrip().upper().startswith("SELECT"):
            return Cursor(self.raw.execute(statement, parameters))
        try:
            # Expected uniqueness failures must not poison the enclosing transaction.
            with self.raw.transaction():
                return Cursor(self.raw.execute(statement, parameters), returning)
        except psycopg.IntegrityError:
            raise sqlite3.IntegrityError("Database constraint rejected the operation") from None

    def executemany(self, statement, parameters):
        for values in parameters:
            self.execute(statement, values)


class PostgresDatabase(Database):
    is_postgres = True

    def __init__(self, url, *, schema="public"):
        if not url.startswith(("postgres://", "postgresql://")):
            raise ValueError("PostgreSQL DATABASE_URL required")
        if schema != "public" and not re.fullmatch(r"test_[a-f0-9]{32}", schema):
            raise ValueError("Invalid database schema")
        self._url, self.schema = url, schema
        self._slots = threading.BoundedSemaphore(4)

    @contextmanager
    def raw_connection(self):
        if not self._slots.acquire(timeout=10):
            raise RuntimeError("Database is busy")
        try:
            try:
                connection = psycopg.connect(self._url, connect_timeout=10,
                    sslmode="disable" if urlsplit(self._url).hostname in {"localhost", "127.0.0.1", "::1"} else "require",
                    row_factory=record_factory, autocommit=True)
            except psycopg.Error:
                raise RuntimeError("PostgreSQL connection unavailable") from None
            with connection:
                with connection.transaction():
                    connection.execute(sql.SQL(
                        "SET LOCAL search_path TO {}; SET LOCAL statement_timeout = '15s'; "
                        "SET LOCAL lock_timeout = '10s'; SELECT pg_advisory_xact_lock({})"
                    ).format(sql.Identifier(self.schema), sql.Literal(CORE_LOCK)), prepare=False)
                    yield connection
        finally:
            self._slots.release()

    @contextmanager
    def connection(self):
        with self.raw_connection() as connection:
            yield RepositoryConnection(connection)

    def initialize(self):
        with self.raw_connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY, checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            applied = {row["version"]: row["checksum"] for row in
                       connection.execute("SELECT version,checksum FROM schema_migrations")}
            files = sorted(MIGRATIONS.glob("*.sql"))
            versions = {int(path.stem.split("_")[0]) for path in files}
            if set(applied) - versions:
                raise RuntimeError("Database schema is newer than this release")
            for path in files:
                version = int(path.stem.split("_")[0])
                body = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(body.encode()).hexdigest()
                if version in applied:
                    if applied[version] != checksum:
                        raise RuntimeError("Applied migration checksum mismatch")
                    continue
                connection.execute(body, prepare=False)
                connection.execute("INSERT INTO schema_migrations(version,checksum) VALUES (%s,%s)",
                                   (version, checksum))
