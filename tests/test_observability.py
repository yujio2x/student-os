import json
import os
import unittest
import time
from types import SimpleNamespace
from unittest.mock import patch
import sentry_sdk
from sentry_sdk.transport import Transport
from app import observability as monitoring


class SafeEventsTest(unittest.TestCase):
    def test_import_log_redacts_untrusted_request_id_and_response(self):
        error = RuntimeError("private body")
        error.response = SimpleNamespace(status_code=504, text="private image")
        with self.assertLogs("app.observability", level="WARNING") as logs:
            monitoring.import_diagnostic("preview_mapped", error, started=time.monotonic(),
                                          request_id="private@example.com\nAuthorization: secret", mapped_status=502)
        record = logs.records[0]
        self.assertEqual(record.upstream_status, 504)
        self.assertIsNone(record.request_id)
        self.assertNotIn("private", "".join(logs.output))
        self.assertNotIn("secret", "".join(logs.output))

    def tearDown(self):
        if monitoring._client:
            monitoring._client.close()
        monitoring._client = None

    def test_disabled_without_dsn(self):
        with patch.dict(os.environ, {}, clear=True), patch("sentry_sdk.Client") as client:
            self.assertFalse(monitoring.initialize("core"))
            client.assert_not_called()

    def test_real_sdk_strips_every_sensitive_surface(self):
        captured = []
        class MemoryTransport(Transport):
            def capture_envelope(self, envelope):
                for item in envelope.items:
                    if item.type == "event":
                        captured.append(item.payload.json)
        real = sentry_sdk.Client
        def factory(**options):
            self.assertFalse(options["send_default_pii"])
            self.assertFalse(options["default_integrations"])
            self.assertEqual(options["max_breadcrumbs"], 0)
            return real(**options, transport=MemoryTransport)
        with patch.dict(os.environ, {"SENTRY_DSN":"https://public@example.invalid/1", "SENTRY_ENVIRONMENT":"staging"}), patch("sentry_sdk.Client",side_effect=factory):
            monitoring.initialize("core")
        monitoring._client.capture_event({
            "message":"private assignment", "tags":{"category":"synthetic_check","secret":"private"},
            "request":{"headers":{"Cookie":"private","Authorization":"private"},"data":"private","query_string":"code=private"},
            "user":{"id":"private"}, "extra":{"DATABASE_URL":"private"},
            "exception":{"values":[{"type":"Error","value":"private","stacktrace":{"frames":[{"vars":{"key":"private"}}]}}]},
            "breadcrumbs":{"values":[{"message":"private"}]}, "contexts":{"photo":"private"}})
        self.assertEqual(len(captured),1)
        self.assertNotIn("private",json.dumps(captured))
        self.assertEqual(set(captured[0]), {"event_id","message","level","tags","environment"})
        self.assertEqual(captured[0]["environment"], "staging")
        self.assertEqual(captured[0]["tags"]["service"], "core")
        self.assertIsNone(monitoring.scrub({"event_id":"a"*32,"tags":{"category":"unknown"}}))
        cause = ValueError("private image base64 SECRET")
        error = RuntimeError("private Authorization sk-secret")
        error.__cause__ = cause
        request_id = "12345678-1234-1234-1234-123456789abc"
        error.response = SimpleNamespace(status_code=504)
        monitoring.capture_import_exception("schedule_import_preview_failed", error, request_id=request_id)
        self.assertEqual(len(captured), 2)
        self.assertEqual([v["type"] for v in captured[1]["exception"]["values"]],
                         ["ValueError", "RuntimeError"])
        self.assertNotIn("private", json.dumps(captured[1]))
        self.assertNotIn("SECRET", json.dumps(captured[1]))
        self.assertNotIn("sk-secret", json.dumps(captured[1]))
        self.assertEqual(captured[1]["tags"]["request_id"], request_id)
        self.assertEqual(captured[1]["tags"]["pipeline_stage"], "preview_mapped")
        self.assertEqual(captured[1]["tags"]["http_status"], "502")
        self.assertEqual(captured[1]["tags"]["upstream_status"], "504")
        monitoring.capture_import_exception("schedule_import_preview_failed", error, request_id="private token")
        self.assertNotIn("request_id", captured[2]["tags"])

    def test_untrusted_environment_and_category_are_not_leaked(self):
        event = {"event_id":"a"*32, "tags":{"category":"synthetic_check"},
                 "environment":"private-token", "server_name":"private-host"}
        clean = monitoring.scrub(event)
        self.assertNotIn("private",json.dumps(clean))
        self.assertIsNone(monitoring.scrub({**event,"tags":{"category":[]}}))
        with patch.dict(os.environ, {"SENTRY_DSN":"https://public@example.invalid/1", "SENTRY_ENVIRONMENT":"private-token"}):
            with self.assertRaisesRegex(ValueError, '^Invalid observability environment$'):
                monitoring.initialize("core")
        self.assertEqual(
            {"oidc_exchange_failed", "oidc_verify_key_failed",
             "oidc_verify_signature_failed", "oidc_verify_algorithm_failed",
             "oidc_verify_audience_failed", "oidc_verify_issuer_failed",
             "oidc_verify_lifetime_failed", "oidc_verify_claims_failed",
             "oidc_verify_identity_failed"} - monitoring.CATEGORIES,
            set(),
        )
