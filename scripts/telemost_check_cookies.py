#!/usr/bin/env python3
"""Daily health-check for the Yandex 360 Business storage_state used by the
Telemost recorder bot.

Two checks:
  1. Static: parse Session_id cookie expiry from the JSON file. If it expires
     within COOKIE_WARN_DAYS, alert operator with days remaining.
  2. Live: GET https://passport.yandex.ru/profile with those cookies. If the
     response indicates we got bounced to /auth (cookie revoked / Yandex
     killed the session), alert.

Without this check, the only signal that cookies are stale is that the bot
starts failing on real meetings — alerts here give the operator a 7-day
window to rotate before any user-visible breakage.

Run via cron (wookiee-cron container) once a day, e.g.:
    0 8 * * * cd /app && python scripts/telemost_check_cookies.py

Env:
    TELEMOST_STORAGE_STATE_PATH — JSON file, same path used by the recorder
    TELEGRAM_ALERTS_BOT_TOKEN   — alerts bot token (shared with hygiene)
    HYGIENE_TELEGRAM_CHAT_ID    — chat to deliver alerts to

Exit codes:
    0 — cookies healthy
    1 — alert emitted (file missing / cookie missing / expiring / revoked)
    2 — env/config error
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

COOKIE_WARN_DAYS = 7
PROFILE_URL = "https://passport.yandex.ru/profile"
HTTP_TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _alert(token: str, chat: str, text: str) -> None:
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: alert send failed: {exc}", file=sys.stderr)


def _find_session_cookie(cookies: list[dict]) -> dict | None:
    for c in cookies:
        if c.get("name") == "Session_id" and "yandex" in c.get("domain", ""):
            return c
    return None


def _build_cookie_jar(cookies: list[dict]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for c in cookies:
        domain = c.get("domain", "")
        if "yandex" not in domain:
            continue
        jar.set(
            name=c.get("name", ""),
            value=c.get("value", ""),
            domain=domain.lstrip("."),
            path=c.get("path", "/"),
        )
    return jar


def _looks_logged_out(resp: httpx.Response) -> bool:
    """Heuristic: a logged-in /profile returns 200 with the user's email. A
    revoked session redirects (resolved by httpx if follow_redirects=True) or
    serves a login page. We check for telltale login markers in HTML."""
    if resp.status_code != 200:
        return True
    body = resp.text[:50_000].lower()
    if "passport.yandex.ru/auth" in body and "form" in body:
        return True
    # Yandex login page has "Войти в Яндекс" / "log in" prominently.
    if "войти в" in body and "id_a-form" in body:
        return True
    return False


def main() -> int:
    storage_path_str = os.environ.get("TELEMOST_STORAGE_STATE_PATH", "").strip()
    alerts_token = os.environ.get("TELEGRAM_ALERTS_BOT_TOKEN", "").strip()
    alerts_chat = os.environ.get("HYGIENE_TELEGRAM_CHAT_ID", "").strip()

    if not storage_path_str:
        print("ERROR: TELEMOST_STORAGE_STATE_PATH not set", file=sys.stderr)
        return 2
    if not alerts_token or not alerts_chat:
        print(
            "ERROR: TELEGRAM_ALERTS_BOT_TOKEN / HYGIENE_TELEGRAM_CHAT_ID not set",
            file=sys.stderr,
        )
        return 2

    storage_path = Path(storage_path_str)

    if not storage_path.is_file():
        _alert(
            alerts_token,
            alerts_chat,
            "🔴 *Telemost cookies:* файл storage_state отсутствует на сервере.\n"
            f"Ожидался: `{storage_path}`\n"
            "Бот не сможет залогиниться. Запусти `scripts/telemost_export_cookies.py` "
            "и `scp` файл на сервер. Runbook: `docs/operations/telemost_bot.md`.",
        )
        return 1

    try:
        state = json.loads(storage_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _alert(
            alerts_token,
            alerts_chat,
            f"🔴 *Telemost cookies:* не смог прочитать storage_state.\n"
            f"Файл: `{storage_path}`\nОшибка: `{exc}`",
        )
        return 1

    cookies = state.get("cookies", []) or []
    session_cookie = _find_session_cookie(cookies)
    if session_cookie is None:
        _alert(
            alerts_token,
            alerts_chat,
            "🔴 *Telemost cookies:* в storage_state нет `Session_id` для yandex.ru.\n"
            "Бот не сможет залогиниться. Пере-экспортируй куки.",
        )
        return 1

    expires_ts = session_cookie.get("expires")
    if not isinstance(expires_ts, (int, float)) or expires_ts <= 0:
        # Session cookies without an explicit expiry — uncommon for Yandex
        # but treat as fine, the live check will catch staleness.
        days_left: float | None = None
    else:
        days_left = (expires_ts - time.time()) / 86_400

    # Live check: hit /profile with the cookies and see if we're still logged in.
    jar = _build_cookie_jar(cookies)
    live_failed_reason: str | None = None
    try:
        resp = httpx.get(
            PROFILE_URL,
            cookies=jar,
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if _looks_logged_out(resp):
            live_failed_reason = (
                f"HTTP {resp.status_code} от {resp.url} — Яндекс отвечает страницей логина."
            )
    except httpx.HTTPError as exc:
        live_failed_reason = f"запрос упал: {exc}"

    if live_failed_reason is not None:
        days_part = (
            f"Календарный срок: ещё {days_left:.0f} дн., но это уже не важно.\n"
            if days_left is not None
            else ""
        )
        _alert(
            alerts_token,
            alerts_chat,
            "🔴 *Telemost cookies:* сессия в Яндексе сломана (revoked / истекла).\n"
            f"{days_part}"
            f"Детали: {live_failed_reason}\n"
            "Срочно пере-экспортируй куки: `scripts/telemost_export_cookies.py`.",
        )
        return 1

    if days_left is not None and days_left < COOKIE_WARN_DAYS:
        _alert(
            alerts_token,
            alerts_chat,
            "🟡 *Telemost cookies:* истекают скоро.\n"
            f"Осталось: {days_left:.1f} дн. (порог {COOKIE_WARN_DAYS}).\n"
            "Запусти `scripts/telemost_export_cookies.py` и обнови файл на сервере "
            "до того, как бот перестанет логиниться.",
        )
        return 1

    days_str = f"{days_left:.0f}" if days_left is not None else "session-cookie"
    print(f"OK: Session_id valid, days_left={days_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
