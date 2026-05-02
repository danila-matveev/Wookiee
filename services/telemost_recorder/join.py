import re
from enum import Enum

from playwright.async_api import Page

_URL_PATTERN = re.compile(
    r"^https?://telemost\.yandex\.(ru|com)/(j|join)/[a-zA-Z0-9_\-]+"
)


def validate_url(url: str) -> bool:
    """Return True if url looks like a valid Telemost meeting link."""
    return bool(_URL_PATTERN.match(url))


class ScreenState(str, Enum):
    CONTINUE_IN_BROWSER = "CONTINUE_IN_BROWSER"
    NAME_FORM = "NAME_FORM"
    WAITING_ROOM = "WAITING_ROOM"
    IN_MEETING = "IN_MEETING"
    MEETING_NOT_FOUND = "MEETING_NOT_FOUND"
    UNKNOWN = "UNKNOWN"


# Selectors checked in priority order (most definitive state first).
# Each state has multiple fallback selectors for Telemost UI resilience.
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
