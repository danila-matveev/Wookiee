"""Tests for scripts/telemost_check_cookies.py — daily storage_state health-check."""
from __future__ import annotations

import json
import sys
import time
from types import SimpleNamespace

import pytest


def _reset_module(monkeypatch):
    monkeypatch.delitem(sys.modules, "scripts.telemost_check_cookies", raising=False)


def _set_env(monkeypatch, storage_path: str) -> None:
    monkeypatch.setenv("TELEMOST_STORAGE_STATE_PATH", storage_path)
    monkeypatch.setenv("TELEGRAM_ALERTS_BOT_TOKEN", "alert-token")
    monkeypatch.setenv("HYGIENE_TELEGRAM_CHAT_ID", "12345")


def _write_state(tmp_path, *, session_expires_in_days: float | None, extra_cookies: list[dict] | None = None):
    cookies = list(extra_cookies or [])
    if session_expires_in_days is not None:
        cookies.append({
            "name": "Session_id",
            "value": "3:secret",
            "domain": ".yandex.ru",
            "path": "/",
            "expires": time.time() + session_expires_in_days * 86_400,
        })
    state = {"cookies": cookies, "origins": []}
    p = tmp_path / "state.json"
    p.write_text(json.dumps(state), encoding="utf-8")
    return p


def _stub_alerts(monkeypatch):
    alerts: list[dict] = []

    def _post(url, json, timeout):  # noqa: ARG001
        alerts.append(json)
        return SimpleNamespace()

    monkeypatch.setattr("httpx.post", _post)
    return alerts


def _stub_healthy_profile(monkeypatch):
    def _get(url, cookies=None, timeout=None, follow_redirects=None, headers=None):  # noqa: ARG001
        return SimpleNamespace(
            status_code=200,
            text="<html>Привет, recorder@wookiee.shop</html>",
            url=url,
        )

    monkeypatch.setattr("httpx.get", _get)


def _stub_logged_out_profile(monkeypatch):
    body = (
        "<html><body><form id='passp:sign-in' action='https://passport.yandex.ru/auth/login'>"
        "<div>войти в Яндекс</div><div id='id_a-form'></div></form></body></html>"
    )

    def _get(url, cookies=None, timeout=None, follow_redirects=None, headers=None):  # noqa: ARG001
        return SimpleNamespace(status_code=200, text=body, url=url)

    monkeypatch.setattr("httpx.get", _get)


def test_returns_2_when_env_missing(monkeypatch):
    _reset_module(monkeypatch)
    monkeypatch.delenv("TELEMOST_STORAGE_STATE_PATH", raising=False)
    from scripts.telemost_check_cookies import main

    assert main() == 2


def test_alerts_when_storage_state_file_missing(monkeypatch, tmp_path):
    _reset_module(monkeypatch)
    _set_env(monkeypatch, str(tmp_path / "missing.json"))
    alerts = _stub_alerts(monkeypatch)
    from scripts.telemost_check_cookies import main

    assert main() == 1
    assert any("отсутствует" in a["text"] for a in alerts)


def test_alerts_when_session_cookie_missing(monkeypatch, tmp_path):
    _reset_module(monkeypatch)
    p = _write_state(tmp_path, session_expires_in_days=None, extra_cookies=[
        {"name": "yandexuid", "value": "123", "domain": ".yandex.ru"},
    ])
    _set_env(monkeypatch, str(p))
    alerts = _stub_alerts(monkeypatch)
    from scripts.telemost_check_cookies import main

    assert main() == 1
    assert any("Session_id" in a["text"] for a in alerts)


def test_alerts_when_cookies_about_to_expire(monkeypatch, tmp_path):
    _reset_module(monkeypatch)
    p = _write_state(tmp_path, session_expires_in_days=3)
    _set_env(monkeypatch, str(p))
    alerts = _stub_alerts(monkeypatch)
    _stub_healthy_profile(monkeypatch)
    from scripts.telemost_check_cookies import main

    assert main() == 1
    assert any("истекают" in a["text"] for a in alerts)


def test_alerts_when_session_revoked(monkeypatch, tmp_path):
    _reset_module(monkeypatch)
    p = _write_state(tmp_path, session_expires_in_days=45)
    _set_env(monkeypatch, str(p))
    alerts = _stub_alerts(monkeypatch)
    _stub_logged_out_profile(monkeypatch)
    from scripts.telemost_check_cookies import main

    assert main() == 1
    assert any("revoked" in a["text"].lower() or "сломана" in a["text"] for a in alerts)


def test_passes_when_cookies_valid_and_live_check_ok(monkeypatch, tmp_path):
    _reset_module(monkeypatch)
    p = _write_state(tmp_path, session_expires_in_days=45)
    _set_env(monkeypatch, str(p))
    alerts = _stub_alerts(monkeypatch)
    _stub_healthy_profile(monkeypatch)
    from scripts.telemost_check_cookies import main

    assert main() == 0
    assert alerts == []


def test_alerts_on_live_check_network_failure(monkeypatch, tmp_path):
    _reset_module(monkeypatch)
    p = _write_state(tmp_path, session_expires_in_days=45)
    _set_env(monkeypatch, str(p))
    alerts = _stub_alerts(monkeypatch)

    import httpx

    def _boom(url, cookies=None, timeout=None, follow_redirects=None, headers=None):  # noqa: ARG001
        raise httpx.ConnectError("network down")

    monkeypatch.setattr("httpx.get", _boom)
    from scripts.telemost_check_cookies import main

    assert main() == 1
    assert any("сломана" in a["text"] or "revoked" in a["text"].lower() for a in alerts)
