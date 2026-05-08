"""Tests for Telemost URL canonicalization + validation."""
from __future__ import annotations

import pytest

from services.telemost_recorder_api.url_canon import (
    canonicalize_telemost_url,
    is_valid_telemost_url,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://telemost.360.yandex.ru/j/12345", "https://telemost.yandex.ru/j/12345"),
        ("https://telemost.yandex.ru/j/12345", "https://telemost.yandex.ru/j/12345"),
        ("https://telemost.yandex.ru/j/12345/", "https://telemost.yandex.ru/j/12345"),
        ("https://TELEMOST.yandex.ru/J/AbCdEf", "https://telemost.yandex.ru/j/abcdef"),
        ("https://telemost.yandex.ru/j/12345?utm=x", "https://telemost.yandex.ru/j/12345"),
    ],
)
def test_canonicalize(url: str, expected: str) -> None:
    assert canonicalize_telemost_url(url) == expected


@pytest.mark.parametrize(
    "url,valid",
    [
        ("https://telemost.yandex.ru/j/12345", True),
        ("https://telemost.360.yandex.ru/j/12345", True),
        ("http://telemost.yandex.ru/j/12345", False),  # http запрещён
        ("https://telemost.yandex.ru/", False),
        ("https://example.com/j/12345", False),
        ("not a url", False),
        ("", False),
    ],
)
def test_is_valid_telemost_url(url: str, valid: bool) -> None:
    assert is_valid_telemost_url(url) is valid
