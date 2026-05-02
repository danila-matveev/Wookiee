# Telemost Recorder — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get a visible bot participant named "Wookiee Recorder" into a Yandex Telemost meeting via Playwright browser automation, with automated tests covering the full join flow.

**Architecture:** Service lives in `services/telemost_recorder/`. A `browser.py` module manages Chromium lifecycle (Xvfb on Linux), `join.py` contains URL validation + screen detection + join logic, and `state.py` holds the in-memory FSM. The CLI shim at `scripts/telemost_record.py` wraps `run_session()` which holds the browser open. Tests at `tests/services/telemost_recorder/` cover unit (state FSM, URL validation), Playwright-against-mock-HTML (screen detection), and live integration.

**Tech Stack:** `playwright>=1.45` (async API), Python 3.11, `pytest` + `anyio` (already in project .venv), Chromium headful + Xvfb (Linux/Docker)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `services/telemost_recorder/__init__.py` | package marker |
| Create | `services/telemost_recorder/config.py` | env vars, browser flags, timeouts |
| Create | `services/telemost_recorder/state.py` | MeetingStatus / FailReason enums + Meeting FSM dataclass |
| Create | `services/telemost_recorder/browser.py` | `launch_browser()` async context manager |
| Create | `services/telemost_recorder/join.py` | URL validation, ScreenState, `detect_screen_state`, `_execute_join`, `join_meeting`, `run_session` |
| Create | `services/telemost_recorder/requirements.txt` | playwright pin |
| Create | `tests/services/telemost_recorder/__init__.py` | package marker |
| Create | `tests/services/telemost_recorder/conftest.py` | `--url` option, `telemost_url` fixture |
| Create | `tests/services/telemost_recorder/test_state_machine.py` | FSM transition unit tests |
| Create | `tests/services/telemost_recorder/test_url_validation.py` | URL pattern unit tests |
| Create | `tests/services/telemost_recorder/fixtures/name_form.html` | mock Telemost name-entry screen |
| Create | `tests/services/telemost_recorder/fixtures/waiting_room.html` | mock Telemost waiting-room screen |
| Create | `tests/services/telemost_recorder/fixtures/in_meeting.html` | mock Telemost in-meeting screen |
| Create | `tests/services/telemost_recorder/fixtures/meeting_not_found.html` | mock Telemost error screen |
| Create | `tests/services/telemost_recorder/fixtures/continue_in_browser.html` | mock Telemost launch-selector screen |
| Create | `tests/services/telemost_recorder/test_state_detection.py` | Playwright-against-mock-HTML detection tests |
| Create | `tests/services/telemost_recorder/test_live_join.py` | live integration test |
| Create | `scripts/telemost_record.py` | CLI shim |
| Create | `deploy/Dockerfile.telemost_recorder` | Docker image with Xvfb + Chromium |

---

## Task 1: Service Scaffolding

**Files:**
- Create: `services/telemost_recorder/__init__.py`
- Create: `services/telemost_recorder/requirements.txt`
- Create: `services/telemost_recorder/config.py`
- Create: `tests/services/telemost_recorder/__init__.py`
- Create: `tests/services/telemost_recorder/conftest.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p services/telemost_recorder
mkdir -p tests/services/telemost_recorder/fixtures
touch services/telemost_recorder/__init__.py
touch tests/services/telemost_recorder/__init__.py
```

- [ ] **Step 2: Create requirements.txt**

```
# services/telemost_recorder/requirements.txt
playwright>=1.45
```

- [ ] **Step 3: Install playwright and download Chromium**

```bash
.venv/bin/pip install playwright>=1.45
.venv/bin/playwright install chromium
```

Expected: downloads `chromium` binary to `~/.cache/ms-playwright/`. Last line: `✔ Chromium ... downloaded`

- [ ] **Step 4: Create config.py**

```python
# services/telemost_recorder/config.py
import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

BOT_NAME: str = os.getenv("TELEMOST_BOT_NAME", "Wookiee Recorder")
JOIN_TIMEOUT: int = int(os.getenv("TELEMOST_JOIN_TIMEOUT", "60"))
WAITING_ROOM_TIMEOUT: int = int(os.getenv("TELEMOST_WAITING_ROOM_TIMEOUT", "600"))
SCREENSHOT_INTERVAL: int = int(os.getenv("TELEMOST_SCREENSHOT_INTERVAL", "30"))

BROWSER_FLAGS: list[str] = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
]
```

- [ ] **Step 5: Create tests conftest.py**

```python
# tests/services/telemost_recorder/conftest.py
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--url", help="Telemost meeting URL for live integration tests")


@pytest.fixture
def telemost_url(request: pytest.FixtureRequest) -> str:
    url = request.config.getoption("--url", default=None)
    if not url:
        pytest.skip("Pass --url=<telemost_url> to run live integration tests")
    return url
```

- [ ] **Step 6: Smoke-check import**

```bash
.venv/bin/python -c "from services.telemost_recorder.config import BOT_NAME; print(BOT_NAME)"
```

Expected: `Wookiee Recorder`

- [ ] **Step 7: Commit**

```bash
git add services/telemost_recorder/ tests/services/telemost_recorder/
git commit -m "feat(telemost): scaffold service structure and config"
```

---

## Task 2: State Module

**Files:**
- Create: `services/telemost_recorder/state.py`
- Create: `tests/services/telemost_recorder/test_state_machine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/telemost_recorder/test_state_machine.py
import pytest
from services.telemost_recorder.state import FailReason, Meeting, MeetingStatus


def test_initial_status_is_pending() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    assert m.status == MeetingStatus.PENDING


def test_pending_to_joining() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    assert m.status == MeetingStatus.JOINING


def test_joining_to_in_meeting() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    assert m.status == MeetingStatus.IN_MEETING


def test_joining_to_waiting_room() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.WAITING_ROOM)
    assert m.status == MeetingStatus.WAITING_ROOM


def test_waiting_room_to_in_meeting() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.WAITING_ROOM)
    m.transition(MeetingStatus.IN_MEETING)
    assert m.status == MeetingStatus.IN_MEETING


def test_waiting_room_to_failed() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.WAITING_ROOM)
    m.transition(MeetingStatus.FAILED, FailReason.NOT_ADMITTED)
    assert m.status == MeetingStatus.FAILED
    assert m.fail_reason == FailReason.NOT_ADMITTED


def test_pending_directly_to_in_meeting_is_invalid() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.IN_MEETING)


def test_in_meeting_is_terminal() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.IN_MEETING)
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.FAILED)


def test_failed_is_terminal() -> None:
    m = Meeting(url="https://telemost.yandex.ru/j/123")
    m.transition(MeetingStatus.JOINING)
    m.transition(MeetingStatus.FAILED, FailReason.JOIN_TIMEOUT)
    with pytest.raises(ValueError, match="Invalid transition"):
        m.transition(MeetingStatus.JOINING)


def test_meeting_id_is_unique() -> None:
    m1 = Meeting(url="https://telemost.yandex.ru/j/123")
    m2 = Meeting(url="https://telemost.yandex.ru/j/123")
    assert m1.meeting_id != m2.meeting_id
```

- [ ] **Step 2: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_machine.py -v 2>&1 | head -20
```

Expected: `ERROR` or `ImportError` (module doesn't exist yet)

- [ ] **Step 3: Implement state.py**

```python
# services/telemost_recorder/state.py
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MeetingStatus(str, Enum):
    PENDING = "PENDING"
    JOINING = "JOINING"
    WAITING_ROOM = "WAITING_ROOM"
    IN_MEETING = "IN_MEETING"
    FAILED = "FAILED"


class FailReason(str, Enum):
    INVALID_URL = "INVALID_URL"
    MEETING_NOT_FOUND = "MEETING_NOT_FOUND"
    JOIN_TIMEOUT = "JOIN_TIMEOUT"
    UI_DETECTION_FAILED = "UI_DETECTION_FAILED"
    NOT_ADMITTED = "NOT_ADMITTED"


_VALID_TRANSITIONS: dict[MeetingStatus, set[MeetingStatus]] = {
    MeetingStatus.PENDING: {MeetingStatus.JOINING, MeetingStatus.FAILED},
    MeetingStatus.JOINING: {MeetingStatus.IN_MEETING, MeetingStatus.WAITING_ROOM, MeetingStatus.FAILED},
    MeetingStatus.WAITING_ROOM: {MeetingStatus.IN_MEETING, MeetingStatus.FAILED},
    MeetingStatus.IN_MEETING: set(),
    MeetingStatus.FAILED: set(),
}


@dataclass
class Meeting:
    url: str
    meeting_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: MeetingStatus = field(default=MeetingStatus.PENDING)
    fail_reason: Optional[FailReason] = field(default=None)
    screenshot_path: Optional[str] = field(default=None)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def transition(self, new_status: MeetingStatus, fail_reason: Optional[FailReason] = None) -> None:
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}. "
                f"Allowed from {self.status.value}: {[s.value for s in allowed]}"
            )
        self.status = new_status
        self.fail_reason = fail_reason
        self.updated_at = datetime.utcnow()
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_machine.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder/state.py tests/services/telemost_recorder/test_state_machine.py
git commit -m "feat(telemost): Meeting FSM — MeetingStatus, FailReason, transition validation"
```

---

## Task 3: URL Validation

**Files:**
- Create: `services/telemost_recorder/join.py` (initial, URL validation only)
- Create: `tests/services/telemost_recorder/test_url_validation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/services/telemost_recorder/test_url_validation.py
import pytest
from services.telemost_recorder.join import validate_url


@pytest.mark.parametrize("url,expected", [
    # valid
    ("https://telemost.yandex.ru/j/12345", True),
    ("https://telemost.yandex.ru/j/abc-def-ghi-jkl", True),
    ("http://telemost.yandex.ru/j/123", True),
    ("https://telemost.yandex.com/join/12345", True),
    ("https://telemost.yandex.com/join/abc-def", True),
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
```

- [ ] **Step 2: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_url_validation.py -v 2>&1 | head -10
```

Expected: `ImportError`

- [ ] **Step 3: Create join.py with validate_url only**

```python
# services/telemost_recorder/join.py
import re

_URL_PATTERN = re.compile(
    r"^https?://telemost\.yandex\.(ru|com)/(j|join)/[a-zA-Z0-9_\-]+"
)


def validate_url(url: str) -> bool:
    """Return True if url looks like a valid Telemost meeting link."""
    return bool(_URL_PATTERN.match(url))
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_url_validation.py -v
```

Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add services/telemost_recorder/join.py tests/services/telemost_recorder/test_url_validation.py
git commit -m "feat(telemost): URL validation with regex for telemost.yandex.ru/j/ and .com/join/"
```

---

## Task 4: Browser Context

**Files:**
- Create: `services/telemost_recorder/browser.py`

(No dedicated unit test for browser launch — Playwright tests in Task 5 implicitly verify it.)

- [ ] **Step 1: Create browser.py**

```python
# services/telemost_recorder/browser.py
import platform
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from services.telemost_recorder.config import BROWSER_FLAGS


def _start_xvfb() -> Optional[subprocess.Popen]:
    """Start virtual display on Linux. Returns process handle or None on macOS/Windows."""
    if platform.system() != "Linux":
        return None
    proc = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


@asynccontextmanager
async def launch_browser() -> AsyncIterator[tuple[Browser, BrowserContext, Page]]:
    """
    Async context manager: launches Chromium headful (Xvfb on Linux) with fake
    media devices. Yields (browser, context, page). Cleans up on exit.

    Usage:
        async with launch_browser() as (browser, context, page):
            await page.goto(url)
    """
    xvfb = _start_xvfb()
    env = {"DISPLAY": ":99"} if platform.system() == "Linux" else {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            env=env,
            args=BROWSER_FLAGS,
        )
        context = await browser.new_context()
        page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()

    if xvfb is not None:
        xvfb.terminate()
        xvfb.wait()
```

- [ ] **Step 2: Smoke-check import**

```bash
.venv/bin/python -c "from services.telemost_recorder.browser import launch_browser; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add services/telemost_recorder/browser.py
git commit -m "feat(telemost): browser.py — headful Chromium launcher with Xvfb + fake media"
```

---

## Task 5: Screen State Detection + Mock HTML Fixtures

**Files:**
- Modify: `services/telemost_recorder/join.py` (add ScreenState enum + detect_screen_state)
- Create: `tests/services/telemost_recorder/fixtures/name_form.html`
- Create: `tests/services/telemost_recorder/fixtures/waiting_room.html`
- Create: `tests/services/telemost_recorder/fixtures/in_meeting.html`
- Create: `tests/services/telemost_recorder/fixtures/meeting_not_found.html`
- Create: `tests/services/telemost_recorder/fixtures/continue_in_browser.html`
- Create: `tests/services/telemost_recorder/test_state_detection.py`

- [ ] **Step 1: Create mock HTML fixtures**

```html
<!-- tests/services/telemost_recorder/fixtures/name_form.html -->
<!DOCTYPE html>
<html lang="ru">
<head><title>Telemost — Войти</title></head>
<body>
  <div class="join-form">
    <h2>Введите ваше имя</h2>
    <input data-testid="display-name-input" type="text" placeholder="Ваше имя" />
    <button data-testid="join-button">Присоединиться</button>
  </div>
</body>
</html>
```

```html
<!-- tests/services/telemost_recorder/fixtures/waiting_room.html -->
<!DOCTYPE html>
<html lang="ru">
<head><title>Telemost — Зал ожидания</title></head>
<body>
  <div data-testid="waiting-room">
    <h2>Зал ожидания</h2>
    <p>Ожидаете разрешения организатора</p>
  </div>
</body>
</html>
```

```html
<!-- tests/services/telemost_recorder/fixtures/in_meeting.html -->
<!DOCTYPE html>
<html lang="ru">
<head><title>Telemost — Встреча</title></head>
<body>
  <div data-testid="meeting-controls">
    <button data-testid="mute-button">Микрофон</button>
    <button data-testid="camera-button">Камера</button>
    <div class="participants">Участники (2)</div>
  </div>
</body>
</html>
```

```html
<!-- tests/services/telemost_recorder/fixtures/meeting_not_found.html -->
<!DOCTYPE html>
<html lang="ru">
<head><title>Telemost — Ошибка</title></head>
<body>
  <div data-testid="error-page">
    <h1>Встреча не найдена</h1>
    <p>Встреча не найдена или уже завершилась</p>
  </div>
</body>
</html>
```

```html
<!-- tests/services/telemost_recorder/fixtures/continue_in_browser.html -->
<!DOCTYPE html>
<html lang="ru">
<head><title>Telemost — Запуск</title></head>
<body>
  <div class="launch-page">
    <p>Откройте встречу в браузере</p>
    <button data-testid="continue-button">Продолжить в браузере</button>
  </div>
</body>
</html>
```

- [ ] **Step 2: Write failing detection tests**

```python
# tests/services/telemost_recorder/test_state_detection.py
"""
Screen state detection tests using mock HTML (no network, no real Telemost).
Each test loads a fixture via page.set_content() and verifies ScreenState detection.
"""
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from services.telemost_recorder.join import ScreenState, detect_screen_state

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
```

- [ ] **Step 3: Run to confirm failures**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_detection.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'ScreenState'`

- [ ] **Step 4: Replace join.py entirely (adds ScreenState + detect_screen_state with clean imports)**

```python
# services/telemost_recorder/join.py
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
```

- [ ] **Step 5: Run detection tests**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_detection.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add \
  services/telemost_recorder/join.py \
  tests/services/telemost_recorder/fixtures/ \
  tests/services/telemost_recorder/test_state_detection.py
git commit -m "feat(telemost): ScreenState enum + detect_screen_state + mock HTML fixtures"
```

---

## Task 6: Full Join Flow

**Files:**
- Modify: `services/telemost_recorder/join.py` (add _execute_join, join_meeting, run_session)

No new test file — `test_live_join.py` (Task 9) covers the integrated flow. Internal helpers
`_wait_for_known_state`, `_wait_for_admission`, and `_emit` are private and exercised through
the public surface.

- [ ] **Step 1: Append the join flow to join.py**

The complete `services/telemost_recorder/join.py` should now look like this (replace the file entirely to keep it coherent):

```python
# services/telemost_recorder/join.py
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
    r"^https?://telemost\.yandex\.(ru|com)/(j|join)/[a-zA-Z0-9_\-]+"
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
```

- [ ] **Step 2: Re-run all telemost tests to confirm nothing regressed**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_state_machine.py \
                 tests/services/telemost_recorder/test_url_validation.py \
                 tests/services/telemost_recorder/test_state_detection.py \
                 -v
```

Expected: `29 passed`

- [ ] **Step 3: Commit**

```bash
git add services/telemost_recorder/join.py
git commit -m "feat(telemost): full join flow — _execute_join, join_meeting, run_session"
```

---

## Task 7: CLI Shim

**Files:**
- Create: `scripts/telemost_record.py`

- [ ] **Step 1: Create CLI shim**

```python
#!/usr/bin/env python3
"""
Wookiee Telemost Recorder — CLI entry point.

Usage:
    python scripts/telemost_record.py join <url> [--name NAME]
    docker exec telemost_recorder python scripts/telemost_record.py join <url>
"""
import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.telemost_recorder.config import BOT_NAME  # noqa: E402
from services.telemost_recorder.join import run_session  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telemost_record",
        description="Join a Yandex Telemost meeting as Wookiee Recorder bot",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    join_p = sub.add_parser("join", help="Join a meeting and hold the session open")
    join_p.add_argument("url", help="Telemost meeting URL (telemost.yandex.ru/j/...)")
    join_p.add_argument("--name", default=None, help=f"Bot display name (default: {BOT_NAME!r})")

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    bot_name = args.name or BOT_NAME

    if args.command == "join":
        try:
            asyncio.run(run_session(args.url, bot_name=bot_name))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-check help output**

```bash
.venv/bin/python scripts/telemost_record.py --help
.venv/bin/python scripts/telemost_record.py join --help
```

Expected: usage text with `join` subcommand listed; no `ImportError`

- [ ] **Step 3: Test invalid URL exits cleanly**

```bash
.venv/bin/python scripts/telemost_record.py join "https://zoom.us/j/12345" 2>&1
```

Expected output (JSON on stdout):
```json
{"status": "FAILED", "reason": "INVALID_URL", "message": "Ссылка не похожа на Яндекс Телемост"}
```

- [ ] **Step 4: Commit**

```bash
git add scripts/telemost_record.py
git commit -m "feat(telemost): CLI shim scripts/telemost_record.py join <url>"
```

---

## Task 8: Dockerfile

**Files:**
- Create: `deploy/Dockerfile.telemost_recorder`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
# deploy/Dockerfile.telemost_recorder
# Wookiee Telemost Recorder — Phase 1 (browser bot, no audio)
FROM python:3.11-slim

# System libraries required by Playwright's Chromium build + Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libx11-6 \
    libxcb1 \
    libx11-xcb1 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Playwright and download Chromium
COPY services/telemost_recorder/requirements.txt /tmp/telemost_requirements.txt
RUN pip install --no-cache-dir -r /tmp/telemost_requirements.txt \
    && playwright install --with-deps chromium

# Copy project
COPY . /app

ENV DISPLAY=:99
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default: print help. Production override: join <url>
CMD ["python", "scripts/telemost_record.py", "--help"]
```

- [ ] **Step 2: Verify Docker build (local)**

```bash
docker build -f deploy/Dockerfile.telemost_recorder -t telemost_recorder:test . 2>&1 | tail -5
```

Expected: `Successfully built <id>` (or `=> CACHED` lines followed by success). Build time ~3-5 min on first run due to Playwright download.

- [ ] **Step 3: Test help in container**

```bash
docker run --rm telemost_recorder:test python scripts/telemost_record.py --help
```

Expected: usage text printed, exit 0.

- [ ] **Step 4: Commit**

```bash
git add deploy/Dockerfile.telemost_recorder
git commit -m "feat(telemost): Dockerfile.telemost_recorder — Ubuntu slim + Xvfb + Playwright Chromium"
```

---

## Task 9: Live Integration Test

**Files:**
- Create: `tests/services/telemost_recorder/test_live_join.py`

This test requires a real Telemost meeting URL. It is skipped by default unless `--url` is passed.

- [ ] **Step 1: Create the live integration test**

```python
# tests/services/telemost_recorder/test_live_join.py
"""
Live integration test: joins a real Telemost meeting.

Requires the host to create a Telemost meeting and pass its URL:
    pytest tests/services/telemost_recorder/test_live_join.py \
        --url="https://telemost.yandex.ru/j/XXXX" \
        -v -s

Outcomes:
  IN_MEETING    → test passes immediately, screenshot saved to data/telemost/<id>/
  WAITING_ROOM  → test prints admission instruction and passes (waiting room = Phase 1 success)
  FAILED        → test fails with reason

Phase 1 acceptance: both IN_MEETING and WAITING_ROOM count as success.
"""
from pathlib import Path

import pytest

from services.telemost_recorder.join import join_meeting
from services.telemost_recorder.state import MeetingStatus


@pytest.mark.anyio
async def test_live_join(telemost_url: str) -> None:
    print(f"\n→ Joining: {telemost_url}")
    meeting = await join_meeting(telemost_url)

    print(f"→ Status: {meeting.status.value}")
    if meeting.fail_reason:
        print(f"→ Fail reason: {meeting.fail_reason.value}")

    assert meeting.status in (MeetingStatus.IN_MEETING, MeetingStatus.WAITING_ROOM), (
        f"Expected IN_MEETING or WAITING_ROOM, got {meeting.status.value}"
        + (f" ({meeting.fail_reason.value})" if meeting.fail_reason else "")
    )

    if meeting.status == MeetingStatus.IN_MEETING:
        assert meeting.screenshot_path is not None, "Screenshot path must be set for IN_MEETING"
        assert Path(meeting.screenshot_path).exists(), (
            f"Screenshot file not found: {meeting.screenshot_path}"
        )
        print(f"✓ Bot is IN_MEETING")
        print(f"  Screenshot: {meeting.screenshot_path}")
    else:
        print("⏳ Bot is in WAITING_ROOM")
        print("  → Admit 'Wookiee Recorder' in Telemost interface to complete the phase")
        print(f"  Meeting ID: {meeting.meeting_id}")
```

- [ ] **Step 2: Run unit + mock tests one final time (no URL needed)**

```bash
.venv/bin/pytest \
  tests/services/telemost_recorder/test_state_machine.py \
  tests/services/telemost_recorder/test_url_validation.py \
  tests/services/telemost_recorder/test_state_detection.py \
  -v
```

Expected: `29 passed`

- [ ] **Step 3: Confirm live test skips without --url**

```bash
.venv/bin/pytest tests/services/telemost_recorder/test_live_join.py -v
```

Expected: `1 skipped` (with skip reason "Pass --url=...")

- [ ] **Step 4: Commit**

```bash
git add tests/services/telemost_recorder/test_live_join.py
git commit -m "feat(telemost): live integration test test_live_join.py"
```

---

## Phase 1 Acceptance Checklist

Before declaring Phase 1 done, run against a real Telemost meeting URL:

```bash
# 1. Unit + mock Playwright tests
.venv/bin/pytest \
  tests/services/telemost_recorder/test_state_machine.py \
  tests/services/telemost_recorder/test_url_validation.py \
  tests/services/telemost_recorder/test_state_detection.py \
  -v
# Expected: 29 passed

# 2. Live integration test
.venv/bin/pytest tests/services/telemost_recorder/test_live_join.py \
  --url="https://telemost.yandex.ru/j/XXXX" \
  -v -s
# Expected: 1 passed (IN_MEETING or WAITING_ROOM)
```

Phase 1 is **done** when:
- [ ] All 29 unit + mock tests pass
- [ ] Live test reaches `IN_MEETING` (screenshot shows "Wookiee Recorder" in participants list)
- [ ] Bot's microphone and camera are off (visible in screenshot — `--use-fake-device-for-media-stream`)
- [ ] Process holds session until Ctrl+C when run via `scripts/telemost_record.py join <url>`

**Note on selectors:** Real Telemost selectors may differ from the mock HTML. When the live test reports `UI_DETECTION_FAILED`, check the screenshot in `data/telemost/<id>/unknown_state.png`, inspect the real DOM, update `_STATE_SELECTORS` in `join.py`, and re-run. This is expected during the first real test and is not a plan failure.

---

## .env Keys Added in This Phase

Add to `.env` (values are optional — defaults work):

```bash
TELEMOST_BOT_NAME=Wookiee Recorder
TELEMOST_JOIN_TIMEOUT=60
TELEMOST_WAITING_ROOM_TIMEOUT=600
TELEMOST_SCREENSHOT_INTERVAL=30
```
