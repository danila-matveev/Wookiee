import pytest
from services.telemost_recorder.join import validate_url


@pytest.mark.parametrize("url,expected", [
    # valid
    ("https://telemost.yandex.ru/j/12345", True),
    ("https://telemost.yandex.ru/j/abc-def-ghi-jkl", True),
    ("http://telemost.yandex.ru/j/123", True),
    ("https://telemost.yandex.com/join/12345", True),
    ("https://telemost.yandex.com/join/abc-def", True),
    ("https://telemost.360.yandex.ru/j/63944462843605", True),
    ("https://telemost.360.yandex.ru/j/abc-def", True),
    # invalid
    ("https://zoom.us/j/12345", False),
    ("https://meet.google.com/abc-def-ghi", False),
    ("https://teams.microsoft.com/meet/123", False),
    ("not-a-url", False),
    ("", False),
    ("https://telemost.yandex.ru/", False),
    ("https://yandex.ru/telemost/j/123", False),
    ("https://telemost.yandex.ru/j/", False),
])
def test_validate_url(url: str, expected: bool) -> None:
    assert validate_url(url) is expected, f"validate_url({url!r}) should be {expected}"
