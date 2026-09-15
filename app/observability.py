"""Privacy-safe operational events; raw exception text and user content never leave here."""
import os
import logging
import time
import re

CATEGORIES = {"synthetic_check", "core_unhandled", "outbox_retry_failed",
              "oidc_exchange_failed", "oidc_verify_key_failed",
              "oidc_verify_signature_failed", "oidc_verify_algorithm_failed",
              "oidc_verify_audience_failed", "oidc_verify_issuer_failed",
              "oidc_verify_lifetime_failed", "oidc_verify_claims_failed",
              "oidc_verify_identity_failed"}
ENVIRONMENTS = {"production", "staging", "development", "test"}
_client = None
_logger = logging.getLogger(__name__)
CATEGORIES.add("schedule_import_preview_failed")


def _safe_request_id(value):
    return value if isinstance(value, str) and re.fullmatch(
        r"(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})", value
    ) else None


def import_diagnostic(stage, exc=None, *, started, tile_number=None, tile_count=None,
                      request_id=None, mapped_status=None):
    """Never interpolate provider messages: they may contain image/user payloads."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if not isinstance(status, int) or not 100 <= status <= 599:
        status = None
    kind = type(exc).__name__ if exc is not None else None
    if kind and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", kind):
        kind = "Exception"
    message = ("upstream_http_error" if status else "exception_details_redacted") if exc else None
    correlation = _safe_request_id(request_id)
    fields = {"pipeline_stage": stage,
                "tile_number": tile_number, "tile_count": tile_count,
                "exception_class": kind, "sanitized_message": message,
                "upstream_status": status, "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                "request_id": correlation, "mapped_status": mapped_status}
    _logger.log(logging.WARNING if exc or (mapped_status and mapped_status >= 400) else logging.INFO,
                "schedule_import_diagnostic %s", fields, extra=fields)


def capture_import_exception(category, exc, *, request_id=None):
    """Capture the original chain as allowlisted metadata, never raw exception text."""
    if category != "schedule_import_preview_failed":
        raise ValueError("Unknown import category")
    if _client is None:
        return
    try:
        chain, seen = [], set()
        current = exc
        while current is not None and id(current) not in seen and len(chain) < 8:
            seen.add(id(current))
            kind = type(current).__name__
            chain.append({"type": kind if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", kind) else "Exception",
                          "value": "exception_details_redacted"})
            current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
        tags = {"category": category, "pipeline_stage": "preview_mapped", "http_status": "502"}
        correlation = _safe_request_id(request_id)
        if correlation:
            tags["request_id"] = correlation
        status = getattr(exc, "status_code", None)
        if status is None:
            status = getattr(getattr(exc, "response", None), "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            tags["upstream_status"] = str(status)
        _client.capture_event({"tags": tags, "level": "error",
                               "exception": {"values": list(reversed(chain))}})
    except Exception:
        pass


def scrub(event, hint=None):
    category = event.get("tags", {}).get("category") if isinstance(event.get("tags"), dict) else None
    event_id = event.get("event_id", "")
    if not isinstance(category, str) or category not in CATEGORIES or not isinstance(event_id, str) or not re.fullmatch(r"[a-f0-9]{32}", event_id):
        return None
    # Reconstruct, rather than redact known secret names: unknown data is discarded.
    clean = {"event_id": event_id, "message": category, "level": "error", "tags": {"category": category}}
    if category == "schedule_import_preview_failed":
        tags = event["tags"]
        clean["tags"].update({"pipeline_stage": "preview_mapped", "http_status": "502"})
        correlation = _safe_request_id(tags.get("request_id"))
        if correlation:
            clean["tags"]["request_id"] = correlation
        status = tags.get("upstream_status")
        if isinstance(status, str) and re.fullmatch(r"[1-5][0-9]{2}", status):
            clean["tags"]["upstream_status"] = status
        values = event.get("exception", {}).get("values", [])
        clean["exception"] = {"values": [{"type": value["type"], "value": "exception_details_redacted"}
            for value in values[:8] if isinstance(value, dict) and isinstance(value.get("type"), str)
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", value["type"])]}
    environment = event.get("environment")
    service = event.get("server_name")
    if isinstance(environment, str) and environment in ENVIRONMENTS:
        clean["environment"] = environment
    if isinstance(service, str) and service in {"core", "bot"}:
        clean["tags"]["service"] = service
    return clean


def initialize(service):
    global _client
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    if service not in {"core", "bot"}:
        raise ValueError("Invalid observability service")
    environment = os.getenv("SENTRY_ENVIRONMENT", os.getenv("APP_ENV", "development"))
    if environment not in ENVIRONMENTS:
        raise ValueError("Invalid observability environment")
    import sentry_sdk
    _client = sentry_sdk.Client(
        dsn=dsn, environment=environment, release=None, server_name=service,
        default_integrations=False, auto_enabling_integrations=False,
        send_default_pii=False, include_local_variables=False, include_source_context=False,
        attach_stacktrace=False, max_breadcrumbs=0, traces_sample_rate=0,
        profiles_sample_rate=0, auto_session_tracking=False, send_client_reports=False,
        before_send=scrub)
    return True


def report(category):
    if category not in CATEGORIES:
        raise ValueError("Unknown operational category")
    if _client is not None:
        try:
            _client.capture_event({"message": category, "level": "error", "tags": {"category": category}})
        except Exception:
            pass  # Observability cannot affect a payment or user request.
