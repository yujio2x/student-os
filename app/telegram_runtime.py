"""One bounded consumer inside web. No polling, subprocess or second dyno.

Bot-owned presentation dispatches through the existing signed Core ASGI bridge.
Effects use durable fences; ambiguous non-idempotent outcomes require review.
"""
import asyncio
from contextlib import suppress
from contextvars import ContextVar
import io
import json
import logging
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit

import httpx
import psycopg
from telegram import Bot, Update
from telegram.ext import ApplicationHandlerStop

from app.telegram_journal import UncertainEffect
from student_telegram.bridge_handlers import dispatch
from student_telegram.bridge_client import BridgeError, StudentOSBridgeClient
from student_telegram.postgres_outbox import PostgresPaymentOutbox

CURRENT = ContextVar('telegram_job', default=None)
TRANSPORT_LOCK = 734923403  # Same lock as the cloud polling worker.


class JournalBot(Bot):
    async def _do_post(self, endpoint, data, **kwargs):
        current = CURRENT.get()
        if current and endpoint in {'sendMessage', 'sendInvoice', 'answerCallbackQuery'}:
            runtime, job, context = current
            if not runtime.ready:
                raise UncertainEffect()
            await asyncio.to_thread(runtime.journal.save_context, context.user_id, context.user_data)
            index = context.send_index
            context.send_index += 1
            key = f'telegram:{index}:{endpoint}'
            # PTB payload includes TelegramObjects; encode their stable dictionaries.
            fingerprint = json.loads(json.dumps(data, default=lambda value: value.to_dict()))
            reused, result = await asyncio.to_thread(runtime.journal.effect, job, key, fingerprint)
            if reused:
                return result
            result = await super()._do_post(endpoint, data, **kwargs)
            await asyncio.to_thread(runtime.journal.complete_effect, job, key, result)
            return result
        return await super()._do_post(endpoint, data, **kwargs)


class ASGIOpener:
    def __init__(self, app, loop):
        self.app, self.loop = app, loop

    def open(self, request, timeout):
        async def post():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='https://core.internal') as client:
                return await client.post(urlsplit(request.full_url).path, content=request.data,
                                         headers=dict(request.header_items()))
        # This is not a routed HTTP request. Wait for the actual in-process work
        # to finish: a client-side timeout would orphan Core work and allow the
        # next job to start another AI call concurrently. Provider I/O is bounded
        # at runtime startup instead; ingress has already durably acknowledged.
        response = asyncio.run_coroutine_threadsafe(post(), self.loop).result()
        if response.status_code >= 400:
            raise HTTPError('https://core.internal', response.status_code, 'Core operation failed', {}, None)
        return io.BytesIO(response.content)


class JournalBridge(StudentOSBridgeClient):
    def post(self, operation, payload, *, timeout=None):
        current = CURRENT.get()
        if current and operation in {'study/text', 'study/photo/quote', 'study/photo/confirm', 'study/photo/answer'}:
            runtime, job, _ = current
            if not runtime.ready:
                raise UncertainEffect()
            key = 'core:' + operation
            reused, result = runtime.journal.effect(job, key, payload)
            if reused:
                if '_bridge_error' in result:
                    raise BridgeError(result['_bridge_error'])
                return result
            # No automatic replay after unknown AI completion. Core's request id
            # remains the authoritative one-charge boundary even during rollback.
            try:
                result = super().post(operation, payload, timeout=timeout)
            except BridgeError as exc:
                if exc.status in {400, 401, 402, 403, 409, 413, 422, 429}:
                    runtime.journal.complete_effect(job, key, {'_bridge_error': exc.status})
                    raise
                raise UncertainEffect() from None
            except Exception:
                raise UncertainEffect() from None
            runtime.journal.complete_effect(job, key, result)
            return result
        return super().post(operation, payload, timeout=timeout)


class TelegramRuntime:
    def __init__(self, app, config, journal):
        self.app, self.config, self.journal = app, config, journal
        self.bot = JournalBot(config.telegram_bot_token)
        self.outbox = None
        self.lease = None
        self.ready = False
        self.tasks = []

    def acquire(self):
        self.lease = psycopg.connect(self.config.database_url, autocommit=True, connect_timeout=5,
            sslmode='disable' if urlsplit(self.config.database_url).hostname in {'localhost', '127.0.0.1', '::1'} else 'require')
        if not self.lease.execute('SELECT pg_try_advisory_lock(%s)', (TRANSPORT_LOCK,)).fetchone()[0]:
            self.lease.close()
            self.lease = None
            raise RuntimeError('Telegram polling/webhook transport already owns lease')

    async def start(self):
        # Prevent HTTP client logs from exposing Telegram's token-bearing API URL.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        try:
            await asyncio.to_thread(self.acquire)
            self.outbox = await asyncio.to_thread(PostgresPaymentOutbox, self.config.database_url)
            if self.app.state.study.client is not None:
                self.app.state.study.client = self.app.state.study.client.with_options(timeout=120, max_retries=0)
            await self.bot.initialize()
            self.bridge = JournalBridge('https://core.internal', self.config.bot_bridge_secret)
            self.bridge._opener = ASGIOpener(self.app, asyncio.get_running_loop())
            self.data = {'bridge': self.bridge, 'payment_outbox': self.outbox, 'durable_delivery': True}
            self.ready = True
            self.tasks = [asyncio.create_task(self.consume()), asyncio.create_task(self.payments())]
        except Exception:
            await self.stop()
            raise RuntimeError('Telegram webhook startup failed; verify config and transport lease') from None

    async def stop(self):
        self.ready = False
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with suppress(asyncio.CancelledError):
                await task
        self.tasks = []
        await self.bot.shutdown()
        if self.lease:
            await asyncio.to_thread(self.lease.close)
            self.lease = None

    async def alive(self):
        try:
            await asyncio.to_thread(self.lease.execute, 'SELECT 1')
            return True
        except Exception:
            self.ready = False
            return False

    async def heartbeat(self, job):
        while True:
            await asyncio.sleep(30)
            if not await self.alive():
                return
            await asyncio.to_thread(self.journal.renew, job)

    async def process(self, job):
        update = Update.de_json(json.loads(job['payload']), self.bot)
        user_id = update.effective_user.id
        initial = await asyncio.to_thread(self.journal.initial_context, job, user_id)
        # Replay starts from the same snapshot even if a prior partial attempt
        # persisted advanced photo/defense state before sending its response.
        context = SimpleNamespace(application=SimpleNamespace(bot_data=self.data), bot=self.bot,
            user_id=user_id, user_data=initial, send_index=0)
        token = CURRENT.set((self, job, context))
        heartbeat = asyncio.create_task(self.heartbeat(job))
        try:
            try:
                await dispatch(update, context)
            except ApplicationHandlerStop:
                pass
            await asyncio.to_thread(self.journal.save_context, user_id, context.user_data)
            await asyncio.to_thread(self.journal.finish, job)
        except UncertainEffect:
            await asyncio.to_thread(self.journal.finish, job, 'review')
        except Exception:
            # No exception details or payloads in output/Sentry.
            logging.getLogger(__name__).error('Telegram job failed; durable state retained')
            await asyncio.to_thread(self.journal.retry, job)
        finally:
            CURRENT.reset(token)
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def consume(self):
        while self.ready and await self.alive():
            try:
                job = await asyncio.to_thread(self.journal.claim)
                if job:
                    await self.process(job)
                else:
                    await asyncio.sleep(1)
            except Exception:
                logging.getLogger(__name__).error('Telegram queue unavailable; durable state retained')
                await asyncio.sleep(5)

    async def payments(self):
        while self.ready:
            try:
                await asyncio.to_thread(self.outbox.retry, self.bridge, 20, backoff=True)
            except Exception:
                logging.getLogger(__name__).error('Payment outbox unavailable; durable records retained')
            await asyncio.sleep(60)

    async def webhook_action(self, action):
        """Owner-only caller; no URLs, secret values or provider errors returned."""
        from app.telegram_webhook import PATH
        expected = self.config.telegram_redirect_uri.rstrip('/') + PATH
        origin = urlsplit(self.config.telegram_redirect_uri)
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in {'','/'}:
            raise RuntimeError('Webhook requires canonical HTTPS origin')
        if action == 'register':
            if not self.ready or not await self.alive():
                raise RuntimeError('Webhook runtime unavailable')
            await self.bot.set_webhook(expected, secret_token=self.config.telegram_webhook_secret,
                allowed_updates=['message','callback_query','pre_checkout_query'], max_connections=2,
                drop_pending_updates=False)
        elif action == 'delete':
            # Consumer drains durable work, but ingress stops before polling can start.
            self.ready = False
            await self.bot.delete_webhook(drop_pending_updates=False)
        elif action != 'status':
            raise ValueError('Invalid webhook action')
        info = await self.bot.get_webhook_info()
        return {'registered':bool(info.url), 'expected_origin':info.url == expected,
                'pending_updates':info.pending_update_count,
                'delivery_error_present':bool(info.last_error_date),
                'runtime_ready':self.ready, 'jobs':await asyncio.to_thread(self.journal.counts),
                'payments':await asyncio.to_thread(self.outbox.backlog)}
