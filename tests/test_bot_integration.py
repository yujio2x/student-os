"""Actual bot transport/outbox against Core ASGI, with no live credentials.

Set STUDENT_AI_BOT_ROOT to a checkout of yujio2x/student-ai-bot.
"""
import importlib.util
import io
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE, SessionService
from test_bridge_api import SECRET, SpyStudy, bridge_app, telegram


@pytest.fixture
def integration(tmp_path, monkeypatch):
    root = os.getenv("STUDENT_AI_BOT_ROOT")
    if not root:
        pytest.skip("Set STUDENT_AI_BOT_ROOT for the cross-project contract suite")
    loaded = []
    for name in ("bridge_client", "payment_outbox"):
        spec = importlib.util.spec_from_file_location(f"app.{name}", Path(root) / "app" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, f"app.{name}", module)
        spec.loader.exec_module(module)
        loaded.append(module)
    transport, outbox_module = loaded
    app = bridge_app(tmp_path / "core.db")
    engine = SpyStudy()
    app.state.study = engine
    with TestClient(app) as web:
        class Opener:
            offline = False

            def open(self, request, timeout):
                if self.offline:
                    raise URLError("synthetic offline")
                response = web.post(urlsplit(request.full_url).path, content=request.data,
                                    headers=dict(request.header_items()))
                if response.status_code >= 400:
                    raise HTTPError(request.full_url, response.status_code, "test", {}, None)
                return io.BytesIO(response.content)

        bot = transport.StudentOSBridgeClient("https://core.example", SECRET)
        bot._opener = Opener()
        yield app, web, bot, outbox_module.PaymentOutbox(tmp_path / "outbox.db"), engine, transport.BridgeError


def web_session(app, web, user_id):
    session = SessionService(app.state.database, 24).issue(user_id)
    web.cookies.set(SESSION_COOKIE, session.token)
    return {"X-CSRF-Token": session.csrf_token}


def test_shared_identity_trial_credits_unlimited_and_engine(integration):
    app, web, bot, _, engine, error = integration
    identity = telegram()
    user = bot.resolve_user(identity)["user"]["id"]
    assert bot.resolve_user(identity)["user"]["id"] == user
    headers = web_session(app, web, user)
    response = web.post("/api/study/analyze", json={"assignment": "Реши x=1", "request_id": "web-first-001"}, headers=headers)
    assert response.status_code == 200, response.text
    assert not bot.get_entitlement(identity)["entitlement"]["free_trial_available"]
    app.state.database.admin_adjust_credits(user, user, 5, "fixture", "admin-credit-1")
    assert bot.get_entitlement(identity)["entitlement"]["balance"] == 5
    result = bot.submit_text_task(identity, "Реши x=2", "telegram-first-001")
    assert result["result"]["how_to_defend"] == response.json()["how_to_defend"]
    assert web.get("/api/student-ai/entitlement").json()["balance"] == 4
    with pytest.raises(error) as caught:
        bot.submit_text_task(identity, "Реши x=2", "telegram-first-001")
    assert caught.value.status == 409
    assert engine.calls == 2
    app.state.database.admin_set_unlimited(user, user, True, "fixture", "admin-unlimited-1")
    bot.submit_text_task(identity, "Реши x=3", "telegram-unlimited-001")
    assert bot.get_entitlement(identity)["entitlement"]["balance"] == 4
    engine.fail = True
    app.state.database.admin_set_unlimited(user, user, False, "fixture", "admin-unlimited-2")
    with pytest.raises(error):
        bot.submit_text_task(identity, "Реши x=4", "telegram-failure-001")
    assert bot.get_entitlement(identity)["entitlement"]["balance"] == 4


def test_bot_trial_visible_to_web_and_failure_refunds(integration):
    app, web, bot, _, engine, error = integration
    identity = telegram(8240099)
    user = bot.resolve_user(identity)["user"]["id"]
    web_session(app, web, user)
    engine.fail = True
    with pytest.raises(error):
        bot.submit_text_task(identity, "Тест задачи", "trial-failure-001")
    assert bot.get_entitlement(identity)["entitlement"]["free_trial_available"]
    engine.fail = False
    bot.submit_text_task(identity, "Тест задачи", "trial-success-001")
    assert not web.get("/api/student-ai/entitlement").json()["free_trial_available"]


def test_real_client_outbox_outage_duplicate_and_payment_validation(integration):
    app, web, bot, outbox, engine, error = integration
    identity = telegram()
    payload = {"telegram": identity, "charge_id": "synthetic-charge", "product_id": "task_help_1_v1", "stars_paid": 25}
    outbox.enqueue(payload)
    bot._opener.offline = True
    assert outbox.retry(bot) == 0
    bot._opener.offline = False
    assert outbox.retry(bot) == 1
    bot.record_payment(payload)
    assert bot.get_entitlement(identity)["entitlement"]["balance"] == 1
    bot.record_payment({**payload, "charge_id": "pack", "product_id": "task_help_5_v1", "stars_paid": 100})
    assert bot.get_entitlement(identity)["entitlement"]["balance"] == 6
    for invalid in ({"stars_paid": 1}, {"product_id": "unknown"}):
        with pytest.raises(error):
            bot.record_payment({**payload, **invalid, "charge_id": "bad"})
    assert outbox.pending() == []
