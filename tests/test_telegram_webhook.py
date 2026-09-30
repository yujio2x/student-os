import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from telegram import Bot, User

from app.config import Settings
from app.database import Database
from app.main import create_app
from app.telegram_journal import TelegramJournal, UncertainEffect
from app.telegram_runtime import ASGIOpener, JournalBot, JournalBridge, TelegramRuntime
from app.telegram_webhook import PATH, validate_config
from student_telegram.payment_outbox import PaymentOutbox
from test_bridge_api import SpyStudy

# Public, deliberately invalid fixture values; no live API credentials.
SECRET = 'synthetic_webhook_fixture_only_12345'
BRIDGE_SECRET = 'synthetic_bridge_fixture_only_12345'
TOKEN = '123:synthetic_fixture_only'


def update(identifier=1, text='Реши x + 1 = 2'):
    return {'update_id': identifier, 'message': {'message_id': 12, 'date': 100,
        'chat': {'id': 123, 'type': 'private'}, 'from': {'id': 123, 'is_bot': False, 'first_name': 'Fixture'}, 'text': text}}


def paid(identifier=2, charge='synthetic-charge'):
    payload = update(identifier, '')
    payload['message']['successful_payment'] = {'currency': 'XTR', 'total_amount': 25,
        'invoice_payload': 'task_help_1_v1', 'telegram_payment_charge_id': charge,
        'provider_payment_charge_id': ''}
    return payload


@pytest.fixture
def ingress(tmp_path, monkeypatch):
    config = Settings(tmp_path/'core.db', '', 'fixture', telegram_bot_token=TOKEN,
        bot_bridge_secret=BRIDGE_SECRET, telegram_delivery_mode='webhook', telegram_webhook_secret=SECRET)
    class FakeRuntime:
        def __init__(self, app, config, journal):
            self.ready = False
            self.outbox = PaymentOutbox(tmp_path/'outbox.db')
        async def start(self):
            self.ready = True
        async def stop(self):
            self.ready = False
    monkeypatch.setattr('app.telegram_runtime.TelegramRuntime', FakeRuntime)
    app = create_app(config)
    with TestClient(app) as client:
        yield app, client, {'X-Telegram-Bot-Api-Secret-Token': SECRET}


def test_valid_duplicate_and_unsupported(ingress):
    app, client, headers = ingress
    assert client.post(PATH, json=update(), headers=headers).status_code == 200
    assert client.post(PATH, json=update(), headers=headers).status_code == 200
    assert app.state.telegram_journal.counts() == {'queued': 1}
    assert client.post(PATH, json={'update_id': 3, 'poll': {'id': 'fixture'}}, headers=headers).status_code == 200
    assert app.state.telegram_journal.counts() == {'queued': 1, 'ignored': 1}


@pytest.mark.parametrize('body,status', [({},400), ({'update_id':True,'message':{}},400),
    ({'update_id':1,'message':{}},400), ({'update_id':1},400), ({'update_id':1,'message':{'from':None}},400)])
def test_malformed_payload_does_not_mutate(ingress, body, status):
    app, client, headers = ingress
    assert client.post(PATH, json=body, headers=headers).status_code == status
    assert app.state.telegram_journal.counts() == {}
    assert app.state.telegram_runtime.outbox.backlog()['pending'] == 0


def test_invalid_secret_method_type_size_and_conflict(ingress):
    app, client, headers = ingress
    assert client.post(PATH, json=paid(), headers={'X-Telegram-Bot-Api-Secret-Token':'wrong'}).status_code == 403
    assert client.post(PATH, json=paid(), headers=[('X-Telegram-Bot-Api-Secret-Token',SECRET),('X-Telegram-Bot-Api-Secret-Token',SECRET)]).status_code == 403
    assert client.get(PATH, headers=headers).status_code == 405
    assert client.post(PATH, content=b'{}', headers=headers).status_code == 415
    assert client.post(PATH, content=b'{', headers={**headers,'Content-Type':'application/json'}).status_code == 400
    assert client.post(PATH, content=b'x'*65537, headers={**headers,'Content-Type':'application/json'}).status_code == 413
    assert app.state.telegram_journal.counts() == {}
    assert app.state.telegram_runtime.outbox.backlog()['pending'] == 0
    assert client.post(PATH, json=update(), headers=headers).status_code == 200
    assert client.post(PATH, json=paid(1), headers=headers).status_code == 409
    assert app.state.telegram_runtime.outbox.backlog()['pending'] == 0


def test_payment_durable_before_ack_duplicates_and_restart(ingress, tmp_path):
    app, client, headers = ingress
    for payload in (paid(), paid(), paid(3)):
        assert client.post(PATH, json=payload, headers=headers).status_code == 200
    reopened = PaymentOutbox(tmp_path/'outbox.db')
    assert reopened.backlog() == {'pending':1,'delivered':0}
    from student_telegram.bridge_client import BridgeError
    client_stub = SimpleNamespace(record_payment=lambda payload: (_ for _ in ()).throw(BridgeError()))
    assert reopened.retry(client_stub) == 0
    assert reopened.backlog()['pending'] == 1
    def delivered(payload):
        return {'payment': {'telegram_payment_charge_id': payload['charge_id'],
            'telegram_user_id':payload['telegram']['telegram_user_id'], 'product_id':payload['product_id'], 'stars_paid':payload['stars_paid']}}
    client_stub.record_payment = delivered
    assert reopened.retry(client_stub) == 1
    assert PaymentOutbox(tmp_path/'outbox.db').retry(client_stub) == 0


def test_storage_failure_returns_retryable_status(ingress, monkeypatch):
    app, client, headers = ingress
    monkeypatch.setattr(app.state.telegram_runtime.outbox, 'enqueue', lambda payload: (_ for _ in ()).throw(RuntimeError('private')))
    assert client.post(PATH, json=paid(), headers=headers).status_code == 503
    assert app.state.telegram_journal.counts() == {'queued': 1}


def test_precheckout_is_fast_local_and_fail_closed(ingress):
    app, client, headers = ingress
    query = {'update_id':5,'pre_checkout_query':{'id':'fixture-query','from':{'id':123,'is_bot':False,'first_name':'Fixture'},
        'currency':'XTR','total_amount':25,'invoice_payload':'task_help_1_v1'}}
    result = client.post(PATH,json=query,headers=headers).json()
    assert result['method'] == 'answerPreCheckoutQuery' and result['ok'] is True
    query['pre_checkout_query']['total_amount'] = 1
    assert client.post(PATH,json=query,headers=headers).json()['ok'] is False
    app.state.telegram_runtime.ready = False
    assert client.post(PATH,json=query,headers=headers).status_code == 503


@pytest.fixture
def journal(tmp_path):
    database = Database(tmp_path/'journal.db')
    database.initialize()
    now = [1000]
    journal = TelegramJournal(database, clock=lambda:now[0])
    journal.initialize()
    return journal, now


def test_queue_restart_ownership_stale_recovery_bounded_retry(journal):
    storage, now = journal
    assert storage.enqueue(update()) and not storage.enqueue(update())
    first = storage.claim()
    assert storage.claim() is None
    now[0] += 301
    recovered = TelegramJournal(storage.database, clock=lambda:now[0])
    second = recovered.claim()
    assert second['owner'] != first['owner']
    with pytest.raises(UncertainEffect):
        storage.effect(first, 'unsafe', {})
    recovered.retry(second)
    now[0] += 61
    third = recovered.claim()
    recovered.retry(third)
    now[0] += 91
    assert recovered.claim() is None and recovered.counts() == {'review':1}


def test_completed_and_ambiguous_effects_survive_restart(journal):
    storage, now = journal
    storage.enqueue(update())
    job = storage.claim()
    assert storage.effect(job,'answer',{'text':'fixture'}) == (False,None)
    with pytest.raises(UncertainEffect):
        storage.effect(job,'answer',{'text':'fixture'})
    storage.complete_effect(job,'answer',{'message_id':99})
    now[0]+=301
    recovered=TelegramJournal(storage.database,clock=lambda:now[0])
    job=recovered.claim()
    assert recovered.effect(job,'answer',{'text':'fixture'}) == (True,{'message_id':99})
    with pytest.raises(UncertainEffect):
        recovered.effect(job,'answer',{'text':'changed'})
    recovered.finish(job)
    assert recovered.counts()=={'done':1} and recovered.claim() is None


def test_context_restart_expiry_and_no_photo_bytes(journal):
    storage, now = journal
    context={'core_pending_photo':{'file_id':'synthetic','quote_id':'q','expires':1200}}
    storage.save_context(123,context)
    assert TelegramJournal(storage.database,clock=lambda:now[0]).context(123)==context
    now[0]+=86401
    assert storage.context(123)=={}


def test_config_fails_before_runtime(tmp_path):
    config=Settings(tmp_path/'test.db','','fixture')
    validate_config(config)
    for overrides in ({'telegram_delivery_mode':'polling'}, {'telegram_delivery_mode':'webhook'},
        {'telegram_delivery_mode':'webhook','telegram_webhook_secret':SECRET,'telegram_bot_token':TOKEN}):
        with pytest.raises(RuntimeError):
            validate_config(replace(config,**overrides))


def test_vendor_snapshot_hashes_and_no_legacy_import():
    root=Path(__file__).resolve().parents[1]/'student_telegram'
    manifest=json.loads((root/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        body=(root/name).read_text(encoding='utf-8')
        assert hashlib.sha256(body.encode()).hexdigest()==digest
        assert 'from app.bot' not in body


def test_vendor_matches_pinned_bot_source():
    import os
    root=os.getenv('STUDENT_AI_BOT_ROOT')
    if not root:
        pytest.skip('Bot checkout not configured')
    target=Path(__file__).resolve().parents[1]/'student_telegram'
    manifest=json.loads((target/'manifest.json').read_text())
    for name in manifest['files']:
        body=(Path(root)/'app'/name).read_text(encoding='utf-8')
        for module in ('bridge_client','payment_outbox','postgres_outbox'):
            body=body.replace(f'from app.{module} ',f'from student_telegram.{module} ')
        assert body==(target/name).read_text(encoding='utf-8')


def test_duplicate_text_retry_one_engine_and_one_answer(tmp_path, monkeypatch):
    """Real dispatch -> signed Core ASGI -> synthetic engine -> journaled Bot send."""
    async def exercise():
        config=Settings(tmp_path/'ai.db','','fixture',telegram_bot_token=TOKEN,bot_bridge_secret=BRIDGE_SECRET)
        app=create_app(config)
        async with app.router.lifespan_context(app):
            app.state.study=engine=SpyStudy()
            storage=app.state.telegram_journal
            storage.initialize()
            runtime=TelegramRuntime(app,config,storage)
            runtime.ready=True
            runtime.outbox=PaymentOutbox(tmp_path/'payments.db')
            runtime.bridge=JournalBridge('https://core.internal',BRIDGE_SECRET)
            runtime.bridge._opener=ASGIOpener(app,asyncio.get_running_loop())
            runtime.data={'bridge':runtime.bridge,'payment_outbox':runtime.outbox,'durable_delivery':True}
            runtime.bot._bot_user=User(123,'FixtureBot',True)
            storage.enqueue(update())
            sent=AsyncMock(return_value={'message_id':99,'date':100,'chat':{'id':123,'type':'private'},'text':'fixture'})
            monkeypatch.setattr(Bot,'_do_post',sent)
            await runtime.process(storage.claim())
            assert storage.counts()=={'done':1}
            assert not storage.enqueue(update()) and storage.claim() is None
            assert engine.calls==1 and sent.await_count==1
    asyncio.run(exercise())


def test_restart_after_sent_answer_reuses_result_without_duplicate(tmp_path, monkeypatch):
    async def exercise():
        config=Settings(tmp_path/'restart.db','','fixture',telegram_bot_token=TOKEN,bot_bridge_secret=BRIDGE_SECRET)
        app=create_app(config)
        async with app.router.lifespan_context(app):
            app.state.study=engine=SpyStudy()
            storage=app.state.telegram_journal
            storage.initialize()
            now=[1000]
            storage.clock=lambda:now[0]
            def build():
                runtime=TelegramRuntime(app,config,storage)
                runtime.ready=True
                runtime.outbox=PaymentOutbox(tmp_path/'outbox-restart.db')
                runtime.bridge=JournalBridge('https://core.internal',BRIDGE_SECRET)
                runtime.bridge._opener=ASGIOpener(app,asyncio.get_running_loop())
                runtime.data={'bridge':runtime.bridge,'payment_outbox':runtime.outbox,'durable_delivery':True}
                runtime.bot._bot_user=User(123,'FixtureBot',True)
                return runtime
            storage.enqueue(update())
            sent=AsyncMock(return_value={'message_id':99,'date':100,'chat':{'id':123,'type':'private'},'text':'fixture'})
            monkeypatch.setattr(Bot,'_do_post',sent)
            finish=storage.finish
            monkeypatch.setattr(storage,'finish',lambda job: (_ for _ in ()).throw(RuntimeError('synthetic crash before done')))
            await build().process(storage.claim())
            monkeypatch.setattr(storage,'finish',finish)
            now[0]+=31
            await build().process(storage.claim())
            assert engine.calls==1 and sent.await_count==1
            assert storage.counts()=={'done':1}
    asyncio.run(exercise())


def test_operator_registration_redacted_status_and_preserving_delete(tmp_path):
    async def exercise():
        config=Settings(tmp_path/'operator.db','','fixture',telegram_bot_token=TOKEN,
            bot_bridge_secret=BRIDGE_SECRET,telegram_redirect_uri='https://student-os.example',telegram_webhook_secret=SECRET)
        runtime=TelegramRuntime(None,config,None)
        runtime.ready=True
        runtime.bot=AsyncMock()
        runtime.bot.get_webhook_info.return_value=SimpleNamespace(url='https://student-os.example'+PATH,
            pending_update_count=2,last_error_date=None)
        runtime.journal=SimpleNamespace(counts=lambda:{'queued':2})
        runtime.outbox=SimpleNamespace(backlog=lambda:{'pending':0,'delivered':1})
        runtime.alive=AsyncMock(return_value=True)
        result=await runtime.webhook_action('register')
        assert result['registered'] and result['expected_origin']
        assert SECRET not in json.dumps(result) and TOKEN not in json.dumps(result)
        kwargs=runtime.bot.set_webhook.call_args.kwargs
        assert kwargs['secret_token']==SECRET and kwargs['drop_pending_updates'] is False
        assert kwargs['max_connections']==2
        await runtime.webhook_action('delete')
        runtime.bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
        assert not runtime.ready
    asyncio.run(exercise())


def test_operator_route_owner_and_csrf_required(ingress):
    from app.auth import SESSION_COOKIE
    app,client,_=ingress
    path='/api/admin/telegram/webhook/register'
    assert client.post(path).status_code==401
    user=app.state.database.create_user('Fixture')
    issued=app.state.sessions.issue(user['id'])
    client.cookies.set(SESSION_COOKIE,issued.token)
    assert client.post(path,headers={'X-CSRF-Token':issued.csrf_token}).status_code==403
    owner=app.state.database.create_user('Owner',role='admin')
    issued=app.state.sessions.issue(owner['id'])
    client.cookies.set(SESSION_COOKIE,issued.token)
    assert client.post(path).status_code==403
    app.state.telegram_runtime.webhook_action=AsyncMock(return_value={'registered':True})
    assert client.post(path,headers={'X-CSRF-Token':issued.csrf_token}).json()=={'registered':True}
