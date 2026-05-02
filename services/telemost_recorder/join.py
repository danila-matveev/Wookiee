import re

_URL_PATTERN = re.compile(
    r"^https?://telemost\.yandex\.(ru|com)/(j|join)/[a-zA-Z0-9_\-]+"
)


def validate_url(url: str) -> bool:
    """Return True if url looks like a valid Telemost meeting link."""
    return bool(_URL_PATTERN.match(url))
