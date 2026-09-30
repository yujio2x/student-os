"""Durable inbound jobs and at-most-once external effect fences.

Unknown external outcomes are retained for operator review, never retried blindly.
Repository transactions serialize claims in SQLite/local and PostgreSQL/cloud.
"""
import hashlib
import json
import time
import uuid


class UncertainEffect(RuntimeError):
    def __init__(self):
        super().__init__('Telegram operation requires reconciliation')


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class TelegramJournal:
    def __init__(self, database, *, clock=time.time):
        self.database, self.clock = database, clock

    def initialize(self):
        with self.database.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS telegram_jobs (
                update_id BIGINT PRIMARY KEY, fingerprint TEXT NOT NULL,
                payload TEXT NOT NULL, state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, owner TEXT,
                lease_until BIGINT NOT NULL DEFAULT 0, available_at BIGINT NOT NULL,
                created_at BIGINT NOT NULL, last_error TEXT)''')
            db.execute('CREATE INDEX IF NOT EXISTS telegram_ready ON telegram_jobs(state,available_at)')
            db.execute('''CREATE TABLE IF NOT EXISTS telegram_effects (
                update_id BIGINT NOT NULL, effect_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL, state TEXT NOT NULL, result TEXT,
                PRIMARY KEY(update_id,effect_key))''')
            db.execute('''CREATE TABLE IF NOT EXISTS telegram_context (
                user_id BIGINT PRIMARY KEY, payload TEXT NOT NULL, expires_at BIGINT NOT NULL)''')

    def enqueue(self, payload, *, unsupported=False):
        body = encode(payload)
        digest = hashlib.sha256(body.encode()).hexdigest()
        now = int(self.clock())
        with self.database.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT fingerprint FROM telegram_jobs WHERE update_id=?', (payload['update_id'],)).fetchone()
            if old:
                if old['fingerprint'] != digest:
                    raise ValueError('Conflicting update identifier')
                return False
            db.execute('''INSERT INTO telegram_jobs
                (update_id,fingerprint,payload,state,available_at,created_at)
                VALUES(?,?,?,?,?,?)''', (payload['update_id'], digest, '{}' if unsupported else body,
                                        'ignored' if unsupported else 'queued', now, now))
        return True

    def claim(self):
        now, owner = int(self.clock()), uuid.uuid4().hex
        with self.database.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            # Expired ownership cannot authorize new effects; a fresh owner recovers.
            db.execute("UPDATE telegram_jobs SET state='queued',owner=NULL WHERE state='processing' AND lease_until<=?", (now,))
            db.execute("UPDATE telegram_jobs SET state='review',last_error='retry_exhausted' WHERE state='queued' AND attempts>=3")
            row = db.execute("SELECT * FROM telegram_jobs WHERE state='queued' AND available_at<=? AND attempts<3 ORDER BY update_id LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            db.execute("UPDATE telegram_jobs SET state='processing',owner=?,lease_until=?,attempts=attempts+1 WHERE update_id=?", (owner, now+300, row['update_id']))
            return {**dict(row), 'owner': owner, 'lease_until': now+300, 'attempts': row['attempts']+1}

    def _owned(self, db, job):
        row = db.execute('SELECT state,owner,lease_until FROM telegram_jobs WHERE update_id=?', (job['update_id'],)).fetchone()
        if not row or row['state'] != 'processing' or row['owner'] != job['owner'] or row['lease_until'] <= self.clock():
            raise UncertainEffect()

    def renew(self, job):
        with self.database.connection() as db:
            self._owned(db, job)
            db.execute('UPDATE telegram_jobs SET lease_until=? WHERE update_id=?', (int(self.clock())+300, job['update_id']))

    def finish(self, job, state='done'):
        with self.database.connection() as db:
            self._owned(db, job)
            # Strip raw input after completion; retain id/fingerprint dedupe tombstone.
            db.execute('UPDATE telegram_jobs SET state=?,payload=?,owner=NULL WHERE update_id=?',
                       (state, '{}' if state == 'done' else job['payload'], job['update_id']))
            if state == 'done':
                db.execute('DELETE FROM telegram_effects WHERE update_id=?', (job['update_id'],))

    def retry(self, job):
        with self.database.connection() as db:
            self._owned(db, job)
            db.execute("UPDATE telegram_jobs SET state=?,available_at=?,owner=NULL,last_error='processing_failed' WHERE update_id=?",
                       ('review' if job['attempts'] >= 3 else 'queued', int(self.clock())+30*job['attempts'], job['update_id']))

    def effect(self, job, key, payload):
        fingerprint = hashlib.sha256(encode(payload).encode()).hexdigest()
        with self.database.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._owned(db, job)
            row = db.execute('SELECT * FROM telegram_effects WHERE update_id=? AND effect_key=?', (job['update_id'], key)).fetchone()
            if row:
                if row['fingerprint'] != fingerprint or row['state'] != 'done':
                    raise UncertainEffect()
                return True, json.loads(row['result'])
            db.execute("INSERT INTO telegram_effects VALUES(?,?,?,'started',NULL)", (job['update_id'], key, fingerprint))
            return False, None

    def complete_effect(self, job, key, result):
        with self.database.connection() as db:
            self._owned(db, job)
            db.execute("UPDATE telegram_effects SET state='done',result=? WHERE update_id=? AND effect_key=?", (encode(result), job['update_id'], key))

    def context(self, user_id):
        with self.database.connection() as db:
            row = db.execute('SELECT payload FROM telegram_context WHERE user_id=? AND expires_at>?', (user_id, int(self.clock()))).fetchone()
        return json.loads(row['payload']) if row else {}

    def initial_context(self, job, user_id):
        """Atomic snapshot: no external side effect or uncertain intermediate state."""
        with self.database.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._owned(db, job)
            row = db.execute("SELECT result FROM telegram_effects WHERE update_id=? AND effect_key='context:initial'", (job['update_id'],)).fetchone()
            if row:
                return json.loads(row['result'])
            row = db.execute('SELECT payload FROM telegram_context WHERE user_id=? AND expires_at>?', (user_id, int(self.clock()))).fetchone()
            body = row['payload'] if row else '{}'
            db.execute("INSERT INTO telegram_effects VALUES(?,'context:initial',?,'done',?)", (job['update_id'], str(user_id), body))
            return json.loads(body)

    def save_context(self, user_id, payload):
        body = encode(payload)
        if len(body.encode()) > 512*1024:
            raise ValueError('Telegram context exceeds limit')
        with self.database.connection() as db:
            db.execute('DELETE FROM telegram_context WHERE expires_at<=?', (int(self.clock()),))
            db.execute('DELETE FROM telegram_context WHERE user_id=?', (user_id,))
            db.execute('INSERT INTO telegram_context VALUES(?,?,?)', (user_id, body, int(self.clock())+86400))

    def counts(self):
        with self.database.connection() as db:
            return {row['state']: row['n'] for row in db.execute('SELECT state,COUNT(*) AS n FROM telegram_jobs GROUP BY state')}

    def cleanup(self):
        with self.database.connection() as db:
            db.execute('DELETE FROM telegram_context WHERE expires_at<=?', (int(self.clock()),))
            # Seven days exceeds Telegram's documented 24h update retention.
            # Core request/charge IDs still protect business effects indefinitely.
            db.execute("DELETE FROM telegram_jobs WHERE state IN ('done','ignored') AND created_at<?", (int(self.clock())-7*86400,))
