"""Fast durable webhook ingress. No raw payload/exception logging."""
import asyncio
import hmac
import json
import re

from fastapi import HTTPException, Request
from telegram import Update

from app.entitlements import PRODUCTS
from app.telegram_journal import TelegramJournal

PATH = '/api/telegram/webhook'
MAX_BYTES = 64 * 1024


def validate_config(config):
    if config.telegram_delivery_mode not in {'disabled', 'webhook'}:
        raise RuntimeError('Core TELEGRAM_DELIVERY_MODE must be disabled or webhook')
    if config.telegram_delivery_mode == 'disabled':
        return
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', config.telegram_webhook_secret):
        raise RuntimeError('Webhook requires TELEGRAM_WEBHOOK_SECRET (32-256 allowed characters)')
    if not config.telegram_bot_token or len(config.bot_bridge_secret) < 32:
        raise RuntimeError('Webhook requires TELEGRAM_BOT_TOKEN and BOT_BRIDGE_SECRET')
    if config.environment in {'production', 'staging'} and not config.database_url:
        raise RuntimeError('Webhook requires existing PostgreSQL DATABASE_URL')


def parse_update(payload):
    if not isinstance(payload, dict) or type(payload.get('update_id')) is not int or not 0 <= payload['update_id'] < 2**63:
        raise ValueError('Invalid update')
    kinds = [key for key in payload if key != 'update_id']
    if len(kinds) != 1 or not isinstance(payload[kinds[0]], dict):
        raise ValueError('Invalid update envelope')
    supported = kinds[0] in {'message', 'callback_query', 'pre_checkout_query'}
    if not supported:
        return None
    update = Update.de_json(payload, None)
    if update.effective_user is None or type(update.effective_user.id) is not int or update.effective_user.id <= 0:
        raise ValueError('Missing update identity')
    if update.message and (not update.message.chat or type(update.message.message_id) is not int):
        raise ValueError('Invalid message')
    query = update.pre_checkout_query
    if query and (not isinstance(query.id, str) or not 1 <= len(query.id) <= 256
                  or not isinstance(query.invoice_payload, str) or not 1 <= len(query.invoice_payload) <= 128
                  or type(query.total_amount) is not int or query.total_amount <= 0):
        raise ValueError('Invalid checkout')
    return update


def payment_payload(update):
    payment = update.message.successful_payment if update and update.message else None
    if not payment:
        return None
    if (payment.currency != 'XTR' or type(payment.total_amount) is not int or payment.total_amount <= 0
            or not 1 <= len(payment.telegram_payment_charge_id) <= 180
            or not 1 <= len(payment.invoice_payload) <= 180):
        raise ValueError('Invalid Stars payment')
    from student_telegram.bridge_handlers import identity
    return {'telegram': identity(update.effective_user), 'charge_id': payment.telegram_payment_charge_id,
            'product_id': payment.invoice_payload, 'stars_paid': payment.total_amount}


def install(app, config, database):
    validate_config(config)
    journal = TelegramJournal(database)
    app.state.telegram_journal = journal
    app.state.telegram_runtime = None

    @app.post(PATH)
    async def webhook(request: Request):
        if config.telegram_delivery_mode != 'webhook':
            raise HTTPException(503, 'Webhook disabled')
        supplied = request.headers.getlist('x-telegram-bot-api-secret-token')
        if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode(), config.telegram_webhook_secret.encode()):
            raise HTTPException(403, 'Webhook authentication failed')
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            raise HTTPException(415, 'JSON required')
        body = bytearray()
        async for chunk in request.stream():
            if len(body)+len(chunk) > MAX_BYTES:
                raise HTTPException(413, 'Update exceeds limit')
            body.extend(chunk)
        try:
            payload = json.loads(body)
            update = parse_update(payload)
            paid = payment_payload(update)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
            raise HTTPException(400, 'Invalid Telegram update') from None
        runtime = app.state.telegram_runtime
        if runtime is None or not runtime.ready:
            raise HTTPException(503, 'Webhook runtime unavailable')
        try:
            if update and update.pre_checkout_query:
                query = update.pre_checkout_query
                # No slow AI/catalog HTTP call; same authoritative Core catalog.
                valid = query.currency == 'XTR' and any(
                    p['id'] == query.invoice_payload and p['stars'] == query.total_amount
                    for p in PRODUCTS.values())
                return {'method': 'answerPreCheckoutQuery', 'pre_checkout_query_id': query.id,
                        'ok': valid, **({} if valid else {'error_message': 'Покупка временно недоступна. Открой /buy позже.'})}
            await asyncio.to_thread(journal.enqueue, payload, unsupported=update is None)
            # Both durable journals precede acknowledgement. Enqueue validates
            # update-id conflicts BEFORE touching the payment outbox.
            if paid:
                await asyncio.to_thread(runtime.outbox.enqueue, paid)
        except ValueError:
            raise HTTPException(409, 'Conflicting update or payment') from None
        except Exception:
            raise HTTPException(503, 'Update not acknowledged; retry required') from None
        return {'ok': True}

    return journal
