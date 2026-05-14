#!/usr/bin/env python3
"""Smoke test — проверяет что Telegram webhook зарегистрирован на наш URL.

Alert в общий @wookiee_alerts_bot через TELEGRAM_ALERTS_BOT_TOKEN если
URL не совпадает с ожидаемым (например после ребута контейнера, когда
setWebhook не успел вызваться).

Запускать cron'ом каждые 10 минут на app-сервере:
    */10 * * * * deploy /opt/wookiee/.venv/bin/python -m scripts.telemost_smoke

Env:
    TELEGRAM_BOT_TOKEN — токен Telemost-бота (для getWebhookInfo)
    TELEMOST_PUBLIC_URL — публичный URL API (без trailing /)
    TELEGRAM_ALERTS_BOT_TOKEN — токен alerts-бота для уведомлений
    HYGIENE_TELEGRAM_CHAT_ID — chat_id куда слать тревоги (опционально)

Exit codes:
    0 — webhook URL совпадает
    1 — любая проблема (env, network, mismatch)
"""
from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    expected_url = os.environ.get("TELEMOST_PUBLIC_URL", "").rstrip("/") + "/telegram/webhook"
    alerts_token = os.environ.get("TELEGRAM_ALERTS_BOT_TOKEN")
    alerts_chat = os.environ.get("HYGIENE_TELEGRAM_CHAT_ID")

    if not bot_token or not expected_url.startswith("http") or not alerts_token:
        print("Missing env vars: TELEGRAM_BOT_TOKEN / TELEMOST_PUBLIC_URL / TELEGRAM_ALERTS_BOT_TOKEN", file=sys.stderr)
        return 1

    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
            timeout=10,
        )
        data = resp.json()
        current_url = data.get("result", {}).get("url", "")
    except Exception as e:  # noqa: BLE001
        _alert(alerts_token, alerts_chat, f"Telemost smoke: getWebhookInfo failed: {e}")
        return 1

    if current_url != expected_url:
        _alert(
            alerts_token,
            alerts_chat,
            f"Telemost webhook URL mismatch.\nExpected: {expected_url}\nActual: {current_url!r}",
        )
        return 1

    print(f"OK: webhook = {current_url}")
    return 0


def _alert(token: str, chat: str | None, text: str) -> None:
    if not chat:
        print(text, file=sys.stderr)
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": f"⚠️ {text}"},
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    sys.exit(main())
