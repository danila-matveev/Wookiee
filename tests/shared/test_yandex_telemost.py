"""Tests for shared.yandex_telemost — Yandex Telemost API wrapper.

Covers:
- create_conference success (POST 201 → Conference)
- create_conference 401 → TelemostTokenExpired
- delete_conference success (DELETE 204 → None)
- delete_conference 404 → raises RuntimeError
- list_conferences success (GET 200 → list[Conference])
- list_conferences 401 → TelemostTokenExpired
- refresh_oauth_token success (POST 200 → tuple[str, str])
- refresh_oauth_token invalid_grant (POST 400 → raises RuntimeError)
- httpx.TimeoutException propagates from all methods
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_body: dict | None = None, text: str = "") -> MagicMock:
    """Build a fake httpx.Response-like mock."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    resp.text = text or (str(json_body) if json_body else "")
    return resp


def _async_client_ctx(mock_response: MagicMock) -> MagicMock:
    """Return an AsyncMock context manager that yields a client mock."""
    client_mock = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client_mock


# ---------------------------------------------------------------------------
# Patches applied globally per-test via autouse=False (explicit)
# ---------------------------------------------------------------------------

ENV_PATCH = {
    "shared.yandex_telemost.TELEMOST_OAUTH_TOKEN": "test-access-token",
    "shared.yandex_telemost.TELEMOST_REFRESH_TOKEN": "test-refresh-token",
    "shared.yandex_telemost.TELEMOST_CLIENT_ID": "test-client-id",
    "shared.yandex_telemost.TELEMOST_CLIENT_SECRET": "test-client-secret",
}


# ---------------------------------------------------------------------------
# create_conference
# ---------------------------------------------------------------------------

async def test_create_conference_success():
    """POST 201 → Conference(id, join_url) returned."""
    from shared.yandex_telemost import Conference, create_conference

    resp = _make_response(201, {"id": "0158581158", "join_url": "https://telemost.360.yandex.ru/j/0158581158"})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        conf = await create_conference()

    assert isinstance(conf, Conference)
    assert conf.id == "0158581158"
    assert conf.join_url == "https://telemost.360.yandex.ru/j/0158581158"


async def test_create_conference_with_host_email():
    """POST 201 with host_email → Conference returned, host_email sent in body."""
    from shared.yandex_telemost import Conference, create_conference

    resp = _make_response(201, {"id": "abc123", "join_url": "https://telemost.360.yandex.ru/j/abc123"})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        conf = await create_conference(host_email="recorder@wookiee.shop")

    assert isinstance(conf, Conference)
    # Verify host_email was passed in the POST body
    call_kwargs = client_mock.post.call_args
    assert call_kwargs is not None
    body = call_kwargs.kwargs.get("json", call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
    assert body.get("host_email") == "recorder@wookiee.shop"


async def test_create_conference_401():
    """POST 401 → raises TelemostTokenExpired."""
    from shared.yandex_telemost import TelemostTokenExpired, create_conference

    resp = _make_response(401, text="Unauthorized")
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(TelemostTokenExpired):
            await create_conference()


# ---------------------------------------------------------------------------
# delete_conference
# ---------------------------------------------------------------------------

async def test_delete_conference_success():
    """DELETE 204 → None (no exception)."""
    from shared.yandex_telemost import delete_conference

    resp = _make_response(204)
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.delete = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        result = await delete_conference("0158581158")

    assert result is None


async def test_delete_conference_404():
    """DELETE 404 → raises RuntimeError (conference not found)."""
    from shared.yandex_telemost import delete_conference

    resp = _make_response(404, text="Not Found")
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.delete = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(RuntimeError, match="404"):
            await delete_conference("nonexistent")


async def test_delete_conference_401():
    """DELETE 401 → raises TelemostTokenExpired."""
    from shared.yandex_telemost import TelemostTokenExpired, delete_conference

    resp = _make_response(401, text="Unauthorized")
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.delete = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(TelemostTokenExpired):
            await delete_conference("some-id")


# ---------------------------------------------------------------------------
# list_conferences
# ---------------------------------------------------------------------------

async def test_list_conferences_success():
    """GET 200 → list[Conference] returned."""
    from shared.yandex_telemost import Conference, list_conferences

    resp = _make_response(200, {
        "conferences": [
            {"id": "conf-1", "join_url": "https://telemost.360.yandex.ru/j/conf-1"},
            {"id": "conf-2", "join_url": "https://telemost.360.yandex.ru/j/conf-2"},
        ]
    })
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.get = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        conferences = await list_conferences(limit=2)

    assert len(conferences) == 2
    assert all(isinstance(c, Conference) for c in conferences)
    assert conferences[0].id == "conf-1"


async def test_list_conferences_empty():
    """GET 200 with empty list → returns empty list."""
    from shared.yandex_telemost import list_conferences

    resp = _make_response(200, {"conferences": []})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.get = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        conferences = await list_conferences()

    assert conferences == []


async def test_list_conferences_401():
    """GET 401 → raises TelemostTokenExpired (used by health-check to trigger refresh)."""
    from shared.yandex_telemost import TelemostTokenExpired, list_conferences

    resp = _make_response(401, text="Unauthorized")
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.get = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(TelemostTokenExpired):
            await list_conferences()


# ---------------------------------------------------------------------------
# refresh_oauth_token
# ---------------------------------------------------------------------------

async def test_refresh_oauth_success():
    """POST oauth.yandex.ru/token 200 → (new_access, new_refresh) tuple."""
    from shared.yandex_telemost import refresh_oauth_token

    resp = _make_response(200, {
        "access_token": "new-access-token-abc",
        "refresh_token": "new-refresh-token-xyz",
        "token_type": "Bearer",
        "expires_in": 31535940,
    })
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        new_access, new_refresh = await refresh_oauth_token()

    assert new_access == "new-access-token-abc"
    assert new_refresh == "new-refresh-token-xyz"


async def test_refresh_oauth_sends_correct_params():
    """Refresh POST must include grant_type, client_id, client_secret, refresh_token."""
    from shared.yandex_telemost import refresh_oauth_token

    resp = _make_response(200, {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
    })
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        await refresh_oauth_token()

    call = client_mock.post.call_args
    assert call is not None
    # data should be form-encoded, not JSON
    data = call.kwargs.get("data", {})
    assert data.get("grant_type") == "refresh_token"
    assert data.get("refresh_token") == "test-refresh-token"
    assert data.get("client_id") == "test-client-id"
    assert data.get("client_secret") == "test-client-secret"


async def test_refresh_oauth_invalid_grant():
    """POST 400 with error=invalid_grant → raises RuntimeError."""
    from shared.yandex_telemost import refresh_oauth_token

    resp = _make_response(400, {"error": "invalid_grant", "error_description": "Token expired"})
    resp.text = '{"error": "invalid_grant"}'
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(RuntimeError, match="400"):
            await refresh_oauth_token()


# ---------------------------------------------------------------------------
# Timeout propagation
# ---------------------------------------------------------------------------

async def test_create_conference_timeout_raises():
    """httpx.TimeoutException propagates from create_conference."""
    from shared.yandex_telemost import create_conference

    ctx, client_mock = _async_client_ctx(None)
    client_mock.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(httpx.TimeoutException):
            await create_conference()


async def test_list_conferences_timeout_raises():
    """httpx.TimeoutException propagates from list_conferences."""
    from shared.yandex_telemost import list_conferences

    ctx, client_mock = _async_client_ctx(None)
    client_mock.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(httpx.TimeoutException):
            await list_conferences()


async def test_delete_conference_timeout_raises():
    """httpx.TimeoutException propagates from delete_conference."""
    from shared.yandex_telemost import delete_conference

    ctx, client_mock = _async_client_ctx(None)
    client_mock.delete = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(httpx.TimeoutException):
            await delete_conference("some-id")


async def test_refresh_oauth_timeout_raises():
    """httpx.TimeoutException propagates from refresh_oauth_token."""
    from shared.yandex_telemost import refresh_oauth_token

    ctx, client_mock = _async_client_ctx(None)
    client_mock.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        with pytest.raises(httpx.TimeoutException):
            await refresh_oauth_token()


# ---------------------------------------------------------------------------
# Authorization header check
# ---------------------------------------------------------------------------

async def test_authorization_header_uses_oauth_not_bearer():
    """Header must be 'Authorization: OAuth <token>', not 'Bearer <token>'."""
    from shared.yandex_telemost import list_conferences

    resp = _make_response(200, {"conferences": []})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.get = AsyncMock(return_value=resp)

    with patch("shared.yandex_telemost.httpx.AsyncClient", return_value=ctx), \
         patch.multiple("shared.yandex_telemost", **{k.split(".")[-1]: v for k, v in ENV_PATCH.items()}):
        await list_conferences()

    call = client_mock.get.call_args
    headers = call.kwargs.get("headers", {})
    auth_header = headers.get("Authorization", "")
    assert auth_header.startswith("OAuth "), f"Expected 'OAuth ...' but got: {auth_header!r}"
    assert "Bearer" not in auth_header
