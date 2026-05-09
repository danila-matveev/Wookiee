"""Tests for /telegram/webhook route."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from services.telemost_recorder_api.app import create_app
from services.telemost_recorder_api.config import TELEMOST_WEBHOOK_SECRET


class _FakeConn:
    async def fetchval(self, query: str):
        return 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConn()


def _msg_update(text: str, chat_id: int = 100, user_id: int = 100) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 5,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "X"},
            "text": text,
        },
    }


def _patch_app_lifespan():
    """Avoid hitting real Supabase during lifespan in tests."""
    return [
        patch(
            "services.telemost_recorder_api.app.get_pool",
            AsyncMock(return_value=_FakePool()),
        ),
        patch(
            "services.telemost_recorder_api.app.close_pool",
            AsyncMock(),
        ),
        patch(
            "services.telemost_recorder_api.app.recorder_loop",
            AsyncMock(return_value=None),
        ),
        patch(
            "services.telemost_recorder_api.app.postprocess_loop",
            AsyncMock(return_value=None),
        ),
    ]


def test_webhook_rejects_missing_secret():
    patches = _patch_app_lifespan()
    for p in patches:
        p.start()
    try:
        app = create_app()
        with TestClient(app) as client:
            resp = client.post("/telegram/webhook", json=_msg_update("/start"))
        assert resp.status_code == 401
    finally:
        for p in patches:
            p.stop()


def test_webhook_rejects_wrong_secret():
    patches = _patch_app_lifespan()
    for p in patches:
        p.start()
    try:
        app = create_app()
        with TestClient(app) as client:
            resp = client.post(
                "/telegram/webhook",
                json=_msg_update("/start"),
                headers={"X-Telegram-Bot-Api-Secret-Token": "WRONG"},
            )
        assert resp.status_code == 401
    finally:
        for p in patches:
            p.stop()


def test_webhook_accepts_correct_secret_and_dispatches():
    dispatched: list = []

    async def fake_dispatch(update):
        dispatched.append(update)

    patches = _patch_app_lifespan() + [
        patch(
            "services.telemost_recorder_api.routes.telegram.dispatch_update",
            AsyncMock(side_effect=fake_dispatch),
        ),
    ]
    for p in patches:
        p.start()
    try:
        app = create_app()
        with TestClient(app) as client:
            resp = client.post(
                "/telegram/webhook",
                json=_msg_update("/start"),
                headers={"X-Telegram-Bot-Api-Secret-Token": TELEMOST_WEBHOOK_SECRET},
            )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert len(dispatched) == 1
        assert dispatched[0]["message"]["text"] == "/start"
    finally:
        for p in patches:
            p.stop()


def test_webhook_returns_200_on_handler_error():
    """Telegram retries non-2xx for ~24h — we must absorb dispatcher errors."""

    async def boom(*_a, **_kw):
        raise RuntimeError("handler crashed")

    patches = _patch_app_lifespan() + [
        patch(
            "services.telemost_recorder_api.routes.telegram.dispatch_update",
            AsyncMock(side_effect=boom),
        ),
    ]
    for p in patches:
        p.start()
    try:
        app = create_app()
        with TestClient(app) as client:
            resp = client.post(
                "/telegram/webhook",
                json=_msg_update("/whatever"),
                headers={"X-Telegram-Bot-Api-Secret-Token": TELEMOST_WEBHOOK_SECRET},
            )
        assert resp.status_code == 200
    finally:
        for p in patches:
            p.stop()
