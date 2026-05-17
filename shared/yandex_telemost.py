"""
Yandex Telemost API wrapper — Саймон (T2).

Single entry point for all Telemost API calls.
Used by T3 (OAuth health-check) and T5 (conference creation from morning digest).

Authorization header: ``Authorization: OAuth <access_token>``
(Yandex uses "OAuth", NOT "Bearer".)

All HTTP requests use httpx.AsyncClient with timeout=15.0 seconds.
On 401 → TelemostTokenExpired is raised. Caller is responsible for retrying
after calling refresh_oauth_token().
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from shared.config import (
    YANDEX_TELEMOST_CLIENT_ID as TELEMOST_CLIENT_ID,
    YANDEX_TELEMOST_CLIENT_SECRET as TELEMOST_CLIENT_SECRET,
    YANDEX_TELEMOST_OAUTH_TOKEN as TELEMOST_OAUTH_TOKEN,
    YANDEX_TELEMOST_REFRESH_TOKEN as TELEMOST_REFRESH_TOKEN,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://cloud-api.yandex.net/v1/telemost-api"
_OAUTH_TOKEN_URL = "https://oauth.yandex.ru/token"
_TIMEOUT = httpx.Timeout(15.0)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Conference:
    """Telemost conference created via the API."""

    id: str
    join_url: str


class TelemostTokenExpired(Exception):
    """Raised when the API returns 401 Unauthorized.

    Caller should call refresh_oauth_token() to get a new access token,
    persist the new tokens, then retry the original call.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _auth_headers() -> dict[str, str]:
    """Build Authorization header using OAuth scheme (not Bearer)."""
    return {"Authorization": f"OAuth {TELEMOST_OAUTH_TOKEN}"}


def _check_401(response: httpx.Response) -> None:
    """Raise TelemostTokenExpired if response is 401."""
    if response.status_code == 401:
        raise TelemostTokenExpired(response.text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_conference(*, host_email: str | None = None) -> Conference:
    """POST /v1/telemost-api/conferences.

    Creates a new Telemost conference room and returns its id and join_url.

    Args:
        host_email: Optional email of the conference host. If provided,
                    it is sent in the request body as ``host_email``.

    Returns:
        Conference dataclass with id and join_url.

    Raises:
        TelemostTokenExpired: If the API returns 401.
        httpx.TimeoutException: If the request times out (15 s).
        RuntimeError: On unexpected non-2xx response.
    """
    body: dict[str, str] = {}
    if host_email is not None:
        body["host_email"] = host_email

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{_BASE_URL}/conferences",
            json=body,
            headers=_auth_headers(),
        )

    _check_401(response)

    if response.status_code != 201:
        raise RuntimeError(
            f"Telemost create_conference failed: {response.status_code} {response.text}"
        )

    data = response.json()
    return Conference(id=data["id"], join_url=data["join_url"])


async def delete_conference(conference_id: str) -> None:
    """DELETE /v1/telemost-api/conferences/{id}.

    Deletes a Telemost conference by its id.

    Args:
        conference_id: The id returned by create_conference.

    Returns:
        None on success (204 No Content).

    Raises:
        TelemostTokenExpired: If the API returns 401.
        httpx.TimeoutException: If the request times out (15 s).
        RuntimeError: On non-204 response (e.g. 404 not found).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.delete(
            f"{_BASE_URL}/conferences/{conference_id}",
            headers=_auth_headers(),
        )

    _check_401(response)

    if response.status_code != 204:
        raise RuntimeError(
            f"Telemost delete_conference failed: {response.status_code} {response.text}"
        )


async def list_conferences(limit: int = 1) -> list[Conference]:
    """GET /v1/telemost-api/conferences.

    Lists active conferences. Primarily used for OAuth token health-check —
    a successful response confirms the token is valid; 401 means it expired.

    Args:
        limit: Maximum number of conferences to retrieve (default 1,
               sufficient for health-check).

    Returns:
        List of Conference dataclasses (may be empty).

    Raises:
        TelemostTokenExpired: If the API returns 401.
        httpx.TimeoutException: If the request times out (15 s).
        RuntimeError: On unexpected non-200 response.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{_BASE_URL}/conferences",
            params={"limit": limit},
            headers=_auth_headers(),
        )

    _check_401(response)

    if response.status_code != 200:
        raise RuntimeError(
            f"Telemost list_conferences failed: {response.status_code} {response.text}"
        )

    data = response.json()
    conferences_raw = data.get("conferences", [])
    return [Conference(id=c["id"], join_url=c["join_url"]) for c in conferences_raw]


async def refresh_oauth_token() -> tuple[str, str]:
    """POST https://oauth.yandex.ru/token with grant_type=refresh_token.

    Exchanges the current refresh token for a new access/refresh token pair.
    The caller is responsible for persisting the new tokens (e.g. writing to
    .env or a secrets store).

    Returns:
        Tuple of (new_access_token, new_refresh_token).

    Raises:
        httpx.TimeoutException: If the request times out (15 s).
        RuntimeError: On non-200 response (e.g. 400 invalid_grant).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            _OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": TELEMOST_REFRESH_TOKEN,
                "client_id": TELEMOST_CLIENT_ID,
                "client_secret": TELEMOST_CLIENT_SECRET,
            },
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Telemost refresh_oauth_token failed: {response.status_code} {response.text}"
        )

    data = response.json()
    return data["access_token"], data["refresh_token"]
