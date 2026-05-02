import asyncio
import json
import re
import time
from enum import Enum
from pathlib import Path

from playwright.async_api import Page

from services.telemost_recorder.browser import launch_browser
from services.telemost_recorder.config import BOT_NAME, JOIN_TIMEOUT, SCREENSHOT_INTERVAL, WAITING_ROOM_TIMEOUT
from services.telemost_recorder.state import FailReason, Meeting, MeetingStatus

_URL_PATTERN = re.compile(
    r"^https?://(telemost\.yandex\.(ru|com)|telemost\.360\.yandex\.ru)/(j|join)/[a-zA-Z0-9_\-]+"
)


def validate_url(url: str) -> bool:
    """Return True if url looks like a valid Telemost meeting link."""
    return bool(_URL_PATTERN.match(url))


# ── Screen state ──────────────────────────────────────────────────────────────


class ScreenState(str, Enum):
    CONTINUE_IN_BROWSER = "CONTINUE_IN_BROWSER"
    NAME_FORM = "NAME_FORM"
    WAITING_ROOM = "WAITING_ROOM"
    IN_MEETING = "IN_MEETING"
    MEETING_NOT_FOUND = "MEETING_NOT_FOUND"
    UNKNOWN = "UNKNOWN"


_STATE_SELECTORS: dict[ScreenState, list[str]] = {
    ScreenState.MEETING_NOT_FOUND: [
        "[data-testid='error-page']",
        "text=Встреча не найдена",
        "text=Meeting not found",
    ],
    ScreenState.IN_MEETING: [
        "[data-testid='meeting-controls']",
        "button[data-testid='mute-button']",
        "[class*='meeting-controls']",
    ],
    ScreenState.WAITING_ROOM: [
        "[data-testid='waiting-room']",
        "text=Зал ожидания",
        "text=Waiting room",
    ],
    ScreenState.NAME_FORM: [
        "[data-testid='display-name-input']",
        "input[placeholder*='имя']",
        "input[placeholder*='name']",
        "input[type='text']",
    ],
    ScreenState.CONTINUE_IN_BROWSER: [
        "[data-testid='continue-button']",
        "button:has-text('Продолжить в браузере')",
        "button:has-text('Continue in browser')",
    ],
}


async def detect_screen_state(page: Page) -> ScreenState:
    """Probe current page for known Telemost UI elements. Returns UNKNOWN if nothing matches."""
    for state, selectors in _STATE_SELECTORS.items():
        for selector in selectors:
            try:
                if await page.locator(selector).first.is_visible(timeout=200):
                    return state
            except Exception:
                continue
    return ScreenState.UNKNOWN


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _wait_for_known_state(page: Page, timeout: float) -> ScreenState:
    """Poll detect_screen_state until a non-UNKNOWN state is found or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = await detect_screen_state(page)
        if state != ScreenState.UNKNOWN:
            return state
        await asyncio.sleep(0.5)
    return ScreenState.UNKNOWN


async def _wait_for_admission(page: Page, timeout: float) -> ScreenState:
    """Poll every 5 s while in waiting room. Returns IN_MEETING on admission or WAITING_ROOM on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(5)
        state = await detect_screen_state(page)
        if state == ScreenState.IN_MEETING:
            return state
        if state == ScreenState.MEETING_NOT_FOUND:
            return state
    return ScreenState.WAITING_ROOM


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


async def _save_screenshot(page: Page, screenshot_dir: Path, name: str) -> Path:
    path = screenshot_dir / f"{name}.png"
    await page.screenshot(path=str(path))
    return path


# ── Core join logic ───────────────────────────────────────────────────────────

async def _execute_join(
    page: Page,
    meeting: Meeting,
    bot_name: str,
    screenshot_dir: Path,
) -> None:
    """
    Navigate to meeting URL and drive the join flow to completion.
    Updates meeting.status in place. All outcomes are reflected via FSM transitions.
    """
    meeting.transition(MeetingStatus.JOINING)

    try:
        await page.goto(meeting.url, wait_until="domcontentloaded", timeout=30_000)
    except Exception:
        meeting.transition(MeetingStatus.FAILED, FailReason.JOIN_TIMEOUT)
        return

    state = await _wait_for_known_state(page, timeout=30)

    if state == ScreenState.MEETING_NOT_FOUND:
        meeting.transition(MeetingStatus.FAILED, FailReason.MEETING_NOT_FOUND)
        return

    if state == ScreenState.CONTINUE_IN_BROWSER:
        locator = page.locator(
            "[data-testid='continue-button'], "
            "button:has-text('Продолжить в браузере'), "
            "button:has-text('Continue in browser')"
        ).first
        await locator.click()
        state = await _wait_for_known_state(page, timeout=15)
        # If still CONTINUE_IN_BROWSER after click, the meeting is not active
        if state == ScreenState.CONTINUE_IN_BROWSER:
            meeting.transition(MeetingStatus.FAILED, FailReason.MEETING_NOT_FOUND)
            return

    if state == ScreenState.UNKNOWN:
        await _save_screenshot(page, screenshot_dir, "unknown_state")
        meeting.transition(MeetingStatus.FAILED, FailReason.UI_DETECTION_FAILED)
        return

    if state == ScreenState.NAME_FORM:
        name_input = page.locator(
            "[data-testid='display-name-input'], "
            "input[placeholder*='имя'], "
            "input[placeholder*='name'], "
            "input[type='text']"
        ).first
        await name_input.fill(bot_name)

        join_btn = page.locator(
            "[data-testid='join-button'], "
            "button:has-text('Присоединиться'), "
            "button:has-text('Войти'), "
            "button:has-text('Join')"
        ).first
        await join_btn.click()

        state = await _wait_for_known_state(page, timeout=JOIN_TIMEOUT)

    if state == ScreenState.WAITING_ROOM:
        meeting.transition(MeetingStatus.WAITING_ROOM)
        _emit({
            "status": "WAITING_ROOM",
            "meeting_id": meeting.meeting_id,
            "message": "Wookiee Recorder в зале ожидания — впустите его в интерфейсе Телемоста",
        })
        state = await _wait_for_admission(page, timeout=WAITING_ROOM_TIMEOUT)
        if state != ScreenState.IN_MEETING:
            meeting.transition(MeetingStatus.FAILED, FailReason.NOT_ADMITTED)
            return

    if state == ScreenState.IN_MEETING:
        screenshot = await _save_screenshot(page, screenshot_dir, "screenshot_001")
        meeting.screenshot_path = str(screenshot)
        meeting.transition(MeetingStatus.IN_MEETING)
        _emit({
            "status": "IN_MEETING",
            "meeting_id": meeting.meeting_id,
            "screenshot": meeting.screenshot_path,
        })
        return

    await _save_screenshot(page, screenshot_dir, "failed_state")
    meeting.transition(MeetingStatus.FAILED, FailReason.UI_DETECTION_FAILED)


# ── Public API ────────────────────────────────────────────────────────────────

async def join_meeting(url: str, bot_name: str = BOT_NAME) -> Meeting:
    """
    Join a meeting and return when state is determined. Browser closes on return.
    Use in tests to get a Meeting result without holding the process open.
    """
    meeting = Meeting(url=url)
    if not validate_url(url):
        meeting.transition(MeetingStatus.FAILED, FailReason.INVALID_URL)
        return meeting

    screenshot_dir = Path("data/telemost") / meeting.meeting_id
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with launch_browser() as (_, __, page):
        await _execute_join(page, meeting, bot_name, screenshot_dir)

    return meeting


async def run_session(url: str, bot_name: str = BOT_NAME) -> None:
    """
    Join a meeting and hold the browser open, taking a screenshot every
    SCREENSHOT_INTERVAL seconds until Ctrl+C or the meeting ends.
    Use from the CLI.
    """
    meeting = Meeting(url=url)
    if not validate_url(url):
        meeting.transition(MeetingStatus.FAILED, FailReason.INVALID_URL)
        _emit({
            "status": "FAILED",
            "reason": "INVALID_URL",
            "message": "Ссылка не похожа на Яндекс Телемост",
        })
        return

    screenshot_dir = Path("data/telemost") / meeting.meeting_id
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with launch_browser() as (_, __, page):
        await _execute_join(page, meeting, bot_name, screenshot_dir)

        if meeting.status == MeetingStatus.FAILED:
            return

        screenshot_n = 2
        try:
            while True:
                await asyncio.sleep(SCREENSHOT_INTERVAL)
                await _save_screenshot(
                    page, screenshot_dir, f"screenshot_{screenshot_n:03d}"
                )
                screenshot_n += 1
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
