from __future__ import annotations

import hashlib
import hmac
import time


class TelegramAuthError(ValueError):
    pass


class TelegramLoginVerifier:
    """Verify Telegram Login Widget payloads per the official HMAC contract."""

    def __init__(self, bot_token: str, max_age_seconds: int = 300) -> None:
        self.bot_token = bot_token
        self.max_age_seconds = max_age_seconds

    def verify(self, payload: dict, now: int | None = None) -> dict:
        if not self.bot_token:
            raise TelegramAuthError("Telegram login не настроен")
        received_hash = str(payload.get("hash", ""))
        if len(received_hash) != 64:
            raise TelegramAuthError("Некорректная подпись Telegram")
        try:
            telegram_id = int(payload["id"])
            auth_date = int(payload["auth_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramAuthError("Некорректные данные Telegram") from exc
        if telegram_id <= 0:
            raise TelegramAuthError("Некорректный Telegram ID")
        current = int(time.time()) if now is None else now
        if auth_date > current + 30 or current - auth_date > self.max_age_seconds:
            raise TelegramAuthError("Данные Telegram устарели")
        signed = {
            key: str(value)
            for key, value in payload.items()
            if key != "hash" and value is not None
        }
        data_check_string = "\n".join(f"{key}={signed[key]}" for key in sorted(signed))
        secret_key = hashlib.sha256(self.bot_token.encode("utf-8")).digest()
        expected = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            raise TelegramAuthError("Некорректная подпись Telegram")
        replay_key = hashlib.sha256(
            f"{data_check_string}\n{received_hash}".encode("utf-8")
        ).hexdigest()
        return {
            "telegram_id": str(telegram_id),
            "display_name": " ".join(
                part for part in (signed.get("first_name", ""), signed.get("last_name", "")) if part
            )[:160],
            "username": signed.get("username", "")[:80],
            "auth_date": auth_date,
            "replay_key": replay_key,
        }
