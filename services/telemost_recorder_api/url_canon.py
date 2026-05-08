"""Canonicalize Telemost URLs for dedup and storage."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_TELEMOST_HOSTS = ("telemost.yandex.ru", "telemost.360.yandex.ru")
_PATH_RE = re.compile(r"^/j/[A-Za-z0-9_-]+/?$")


def canonicalize_telemost_url(url: str) -> str:
    """Normalize a Telemost meeting URL.

    Rules:
    - Lowercase host and path.
    - Map telemost.360.yandex.ru -> telemost.yandex.ru.
    - Strip trailing slash + query + fragment.
    - Force https.
    """
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().replace(
        "telemost.360.yandex.ru", "telemost.yandex.ru"
    )
    path = parsed.path.lower().rstrip("/")
    return f"https://{host}{path}"


def is_valid_telemost_url(url: str) -> bool:
    """True iff url is https + telemost host + /j/<id> path."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        return False
    if parsed.netloc.lower() not in _TELEMOST_HOSTS:
        return False
    return bool(_PATH_RE.match(parsed.path))
