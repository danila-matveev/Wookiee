"""
Screen state detection tests using mock HTML (no network, no real Telemost).
Each test loads a fixture via page.set_content() and verifies ScreenState detection.
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import async_playwright

from services.telemost_recorder.join import (
    ScreenState,
    _detect_meeting_not_found,
    detect_screen_state,
)

_FIXTURES = Path(__file__).parent / "fixtures"


async def _detect_from_html(html: str) -> ScreenState:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html)
        result = await detect_screen_state(page)
        await browser.close()
    return result


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text()


@pytest.mark.anyio
async def test_detect_name_form() -> None:
    assert await _detect_from_html(_fixture("name_form.html")) == ScreenState.NAME_FORM


@pytest.mark.anyio
async def test_detect_waiting_room() -> None:
    assert await _detect_from_html(_fixture("waiting_room.html")) == ScreenState.WAITING_ROOM


@pytest.mark.anyio
async def test_detect_in_meeting() -> None:
    assert await _detect_from_html(_fixture("in_meeting.html")) == ScreenState.IN_MEETING


@pytest.mark.anyio
async def test_detect_meeting_not_found() -> None:
    assert await _detect_from_html(_fixture("meeting_not_found.html")) == ScreenState.MEETING_NOT_FOUND


@pytest.mark.anyio
async def test_detect_continue_in_browser() -> None:
    assert await _detect_from_html(_fixture("continue_in_browser.html")) == ScreenState.CONTINUE_IN_BROWSER


@pytest.mark.anyio
async def test_detect_unknown_returns_unknown() -> None:
    html = "<html><body><p>Нет ни одного знакомого элемента</p></body></html>"
    assert await _detect_from_html(html) == ScreenState.UNKNOWN


# ── _detect_meeting_not_found (mocked Page) ──────────────────────────────────


@pytest.mark.anyio
async def test_detect_meeting_not_found_returns_true_when_selector_visible() -> None:
    """When Telemost shows 'Встреча не найдена', detector returns True quickly."""
    page = AsyncMock()
    locator_mock = MagicMock()
    locator_mock.first.is_visible = AsyncMock(return_value=True)
    page.locator.return_value = locator_mock

    assert await _detect_meeting_not_found(page, timeout_seconds=2.0) is True


@pytest.mark.anyio
async def test_detect_meeting_not_found_returns_false_on_timeout() -> None:
    """When no not-found selector ever shows up, detector returns False after timeout."""
    page = AsyncMock()
    locator_mock = MagicMock()
    locator_mock.first.is_visible = AsyncMock(return_value=False)
    page.locator.return_value = locator_mock

    assert await _detect_meeting_not_found(page, timeout_seconds=1.0) is False
