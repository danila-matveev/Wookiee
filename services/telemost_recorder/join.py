import asyncio
import json
import re
import time
from enum import Enum
from pathlib import Path

from playwright.async_api import Page

from services.telemost_recorder.audio import AudioCapture
from services.telemost_recorder.browser import launch_browser
from services.telemost_recorder.config import (
    BOT_NAME,
    JOIN_TIMEOUT,
    KNOWN_BOT_NAMES,
    SCREENSHOT_INTERVAL,
    WAITING_ROOM_TIMEOUT,
)
from services.telemost_recorder.speakers import load_speakers, resolve_speakers
from services.telemost_recorder.state import FailReason, Meeting, MeetingStatus
from services.telemost_recorder.transcribe import transcribe_audio

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
        "text=комнате ожидания",
        "text=Организатор видит ваш запрос",
        "text=Зал ожидания",
        "text=Waiting room",
        "text=You are in the waiting room",
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


async def _wait_for_joined(page: Page, timeout: float) -> ScreenState:
    """After clicking join, poll until WAITING_ROOM/IN_MEETING/MEETING_NOT_FOUND.

    Ignores NAME_FORM — the name input stays in DOM under the waiting-room overlay.
    After 3 s uses absence of WR text as a fallback IN_MEETING signal for meetings
    that admit the bot directly (no waiting room).
    """
    deadline = time.monotonic() + timeout
    join_time = time.monotonic()
    while time.monotonic() < deadline:
        state = await detect_screen_state(page)
        if state in (ScreenState.WAITING_ROOM, ScreenState.IN_MEETING, ScreenState.MEETING_NOT_FOUND):
            return state
        # After the page has had time to settle, treat absence of all known
        # pre-meeting elements as a signal that the bot is already in the meeting.
        if time.monotonic() - join_time >= 3.0 and state == ScreenState.UNKNOWN:
            try:
                wr1 = await page.locator("text=комнате ожидания").first.is_visible(timeout=300)
                wr2 = await page.locator("text=Организатор видит").first.is_visible(timeout=300)
                name_inp = await page.locator("input[type='text']").first.is_visible(timeout=300)
                if not wr1 and not wr2 and not name_inp:
                    return ScreenState.IN_MEETING
            except Exception:
                pass
        await asyncio.sleep(0.5)
    return ScreenState.UNKNOWN


async def _wait_for_admission(page: Page, timeout: float) -> ScreenState:
    """Polls every 5 s while in waiting room.

    Returns IN_MEETING on admission or WAITING_ROOM on timeout.
    Falls back to absence of both WR phrases when selector-based detection fails.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(5)
        state = await detect_screen_state(page)
        if state == ScreenState.IN_MEETING:
            return state
        if state == ScreenState.MEETING_NOT_FOUND:
            return state
        # Fallback: both waiting-room phrases absent simultaneously → admitted
        try:
            wr1 = await page.locator("text=комнате ожидания").first.is_visible(timeout=300)
            wr2 = await page.locator("text=Организатор видит").first.is_visible(timeout=300)
            if not wr1 and not wr2:
                return ScreenState.IN_MEETING
        except Exception:
            pass
    return ScreenState.WAITING_ROOM


async def _dismiss_modals(page: Page) -> None:
    """Close known Telemost popups (e.g. Алиса Про) that appear after joining."""
    for selector in (
        "button:has-text('Отлично')",
        "button:has-text('Понятно')",
        "[data-testid='modal-close-button']",
        "button[aria-label='Закрыть']",
    ):
        try:
            loc = page.locator(selector).first
            if await loc.is_visible(timeout=1_000):
                await loc.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass


async def _mute_bot(page: Page) -> None:
    """Click mic-off / camera-off buttons if they appear in the meeting UI."""
    for testid in ("turn-off-mic-button", "turn-off-camera-button"):
        try:
            loc = page.locator(f"[data-testid='{testid}']").first
            if await loc.is_visible(timeout=2_000):
                await loc.click()
        except Exception:
            pass


def _filter_human_participants(names: list[str]) -> list[str]:
    """Remove known bots (case-insensitive substring match) from participant list."""
    return [
        n for n in names
        if not any(bot in n.lower() for bot in KNOWN_BOT_NAMES)
    ]


async def extract_participants(page: Page) -> list[str]:
    """Open Participants panel and scrape display names."""
    names: list[str] = []
    try:
        btn = page.locator(
            "button:has-text('Участники'), [data-testid='participants-button']"
        ).first
        if await btn.is_visible(timeout=2_000):
            await btn.click()
            await asyncio.sleep(0.5)
            items = page.locator(
                "[data-testid='participant-name'], "
                ".participant-name, "
                "[class*='participant'][class*='name']"
            )
            count = await items.count()
            for i in range(count):
                name = (await items.nth(i).text_content() or "").strip()
                if name:
                    names.append(name)
            await btn.click()  # close panel
    except Exception:
        pass

    # Fallback: video tile labels
    if not names:
        try:
            tiles = page.locator("[class*='tile'][class*='name'], .video-tile-name")
            count = await tiles.count()
            for i in range(count):
                name = (await tiles.nth(i).text_content() or "").strip()
                if name:
                    names.append(name)
        except Exception:
            pass

    # Deduplicate, preserve order, then filter known bots
    deduped = list(dict.fromkeys(names))
    return _filter_human_participants(deduped)


async def detect_meeting_ended(page: Page) -> bool:
    """Return True when Telemost signals the meeting has ended."""
    # URL check first — fast and reliable: /j/ is only present in active meeting URLs
    try:
        if "/j/" not in page.url:
            return True
    except Exception:
        pass

    # Explicit "meeting ended" overlays. Раньше сюда были добавлены
    # "Чтобы пригласить других участников" / "To invite other participants",
    # но эти строки реально живут в боковой подсказке share-кнопки Я.Телемоста
    # — и срабатывают как ложный сигнал, выкидывая бота со встречи через
    # ~90 секунд даже когда в звонке 5+ человек (см. кейс 13.05 Dayli).
    for selector in (
        "text=Встреча завершена",
        "text=Meeting ended",
        "text=Конференция завершена",
        "[data-testid='meeting-ended']",
    ):
        try:
            if await page.locator(selector).first.is_visible(timeout=200):
                return True
        except Exception:
            continue

    # Count is dynamic — even if Telemost UI shows 2 participants,
    # they could be us + another bot. Pull names and filter.
    try:
        btn = page.locator("button").filter(has_text="Участники")
        badge_text = (await btn.first.text_content(timeout=500) or "")
        match = re.search(r"\d+", badge_text)
        if match:
            badge_count = int(match.group())
            if badge_count <= 1:
                return True
            # Badge > 1: pull names, filter bots, check if any humans remain.
            # extract_participants already excludes Wookiee Recorder + bots from KNOWN_BOT_NAMES.
            human_names = await extract_participants(page)
            if not human_names:
                return True
    except Exception:
        pass

    return False


def _format_ms(ms: int) -> str:
    total_s = ms // 1000
    h, remainder = divmod(total_s, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _write_transcript(segments: list, output_dir: Path) -> None:
    """Write transcript.txt, transcript.json, and raw_segments.json to output_dir.

    raw_segments.json is the canonical artefact consumed by recorder_worker
    (services/telemost_recorder_api/workers/recorder_worker.py) when ingesting
    finished recordings into Supabase.
    """
    txt_lines = [
        f"[{_format_ms(s.start_ms)}] {s.speaker}: {s.text}"
        for s in segments
    ]
    (output_dir / "transcript.txt").write_text("\n".join(txt_lines), encoding="utf-8")

    json_data = [
        {"speaker": s.speaker, "start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text}
        for s in segments
    ]
    payload = json.dumps(json_data, ensure_ascii=False, indent=2)
    (output_dir / "transcript.json").write_text(payload, encoding="utf-8")
    (output_dir / "raw_segments.json").write_text(payload, encoding="utf-8")


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
    Stops at WAITING_ROOM — admission polling is handled by run_session.
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
            "[data-testid='enter-conference-button'], "
            "[data-testid='join-button'], "
            "button:has-text('Подключиться'), "
            "button:has-text('Присоединиться'), "
            "button:has-text('Войти'), "
            "button:has-text('Join')"
        ).first
        await join_btn.click()

        # Use _wait_for_joined instead of _wait_for_known_state: the name input
        # stays visible in the DOM while the waiting-room overlay appears on top,
        # so a generic poll would return NAME_FORM immediately and miss WAITING_ROOM.
        state = await _wait_for_joined(page, timeout=JOIN_TIMEOUT)

    if state == ScreenState.WAITING_ROOM:
        meeting.transition(MeetingStatus.WAITING_ROOM)
        _emit({
            "status": "WAITING_ROOM",
            "meeting_id": meeting.meeting_id,
            "message": "Wookiee Recorder в зале ожидания — впустите его в интерфейсе Телемоста",
        })
        # Caller (run_session) handles the admission wait. join_meeting returns here.
        return

    if state == ScreenState.IN_MEETING:
        await _dismiss_modals(page)
        await _mute_bot(page)
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

async def join_meeting(
    url: str,
    bot_name: str = BOT_NAME,
    meeting_id: str | None = None,
    output_dir: str | None = None,
) -> Meeting:
    """
    Join a meeting and return when state is determined. Browser closes on return.
    Use in tests to get a Meeting result without holding the process open.

    Both ``meeting_id`` and ``output_dir`` are optional overrides used by the API
    service when it spawns recorder containers. Omitting them preserves the
    historical behaviour: a fresh UUID is generated and artefacts land in
    ``data/telemost/<meeting_id>``.
    """
    meeting = Meeting(url=url)
    if meeting_id is not None:
        meeting.meeting_id = meeting_id
    if not validate_url(url):
        meeting.transition(MeetingStatus.FAILED, FailReason.INVALID_URL)
        return meeting

    screenshot_dir = (
        Path(output_dir) if output_dir is not None
        else Path("data/telemost") / meeting.meeting_id
    )
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with launch_browser() as (_, __, page):
        await _execute_join(page, meeting, bot_name, screenshot_dir)

    return meeting


async def run_session(
    url: str,
    bot_name: str = BOT_NAME,
    meeting_id: str | None = None,
    output_dir: str | None = None,
) -> None:
    """
    Join a meeting, record audio, transcribe after meeting ends.
    Holds the browser open until meeting ends or Ctrl+C.

    Both ``meeting_id`` and ``output_dir`` are optional overrides used by the API
    service when it spawns recorder containers. Omitting them preserves the
    historical behaviour: a fresh UUID is generated and artefacts land in
    ``data/telemost/<meeting_id>``.
    """
    from services.telemost_recorder.audio import AudioCapture

    meeting = Meeting(url=url)
    if meeting_id is not None:
        meeting.meeting_id = meeting_id
    if not validate_url(url):
        meeting.transition(MeetingStatus.FAILED, FailReason.INVALID_URL)
        _emit({"status": "FAILED", "reason": "INVALID_URL", "message": "Ссылка не похожа на Яндекс Телемост"})
        return

    screenshot_dir = (
        Path(output_dir) if output_dir is not None
        else Path("data/telemost") / meeting.meeting_id
    )
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    capture = AudioCapture(meeting_id=meeting.meeting_id, output_dir=screenshot_dir)

    # Init PulseAudio null sink BEFORE Chromium launches so Chrome's dlopen(libpulse.so.0)
    # finds our sink as the default and routes all audio there from the start.
    try:
        capture.start()
    except Exception as exc:
        meeting.transition(MeetingStatus.FAILED, FailReason.RECORDING_FAILED)
        _emit({
            "status": "FAILED",
            "reason": "RECORDING_FAILED",
            "meeting_id": meeting.meeting_id,
            "error": str(exc),
        })
        return

    try:
        async with launch_browser() as (_, __, page):
            await _execute_join(page, meeting, bot_name, screenshot_dir)

            if meeting.status == MeetingStatus.FAILED:
                _emit({
                    "status": "FAILED",
                    "reason": meeting.fail_reason.value if meeting.fail_reason else "UNKNOWN",
                    "meeting_id": meeting.meeting_id,
                })
                return

            if meeting.status == MeetingStatus.WAITING_ROOM:
                state = await _wait_for_admission(page, timeout=WAITING_ROOM_TIMEOUT)
                if state != ScreenState.IN_MEETING:
                    meeting.transition(MeetingStatus.FAILED, FailReason.NOT_ADMITTED)
                    _emit({"status": "FAILED", "reason": "NOT_ADMITTED", "meeting_id": meeting.meeting_id})
                    return
                await _dismiss_modals(page)
                await _mute_bot(page)
                screenshot = await _save_screenshot(page, screenshot_dir, "screenshot_001")
                meeting.screenshot_path = str(screenshot)
                meeting.transition(MeetingStatus.IN_MEETING)
                _emit({"status": "IN_MEETING", "meeting_id": meeting.meeting_id, "screenshot": meeting.screenshot_path})

            meeting.transition(MeetingStatus.RECORDING)
            _emit({"status": "RECORDING", "meeting_id": meeting.meeting_id})

            # Meeting loop
            screenshot_n = 2
            participant_tick = 0
            elapsed = 0
            try:
                while True:
                    await asyncio.sleep(SCREENSHOT_INTERVAL)
                    elapsed += SCREENSHOT_INTERVAL
                    await _save_screenshot(page, screenshot_dir, f"screenshot_{screenshot_n:03d}")
                    screenshot_n += 1

                    # Reroute any new Chrome audio streams that appeared after capture.start()
                    capture.reroute_streams()

                    participant_tick += SCREENSHOT_INTERVAL
                    if participant_tick >= 60:
                        meeting.participants = await extract_participants(page)
                        participant_tick = 0

                    # Grace period: don't exit for the first 90s so the host has time to join
                    if elapsed >= 90 and await detect_meeting_ended(page):
                        _emit({"status": "MEETING_ENDED_DETECTED", "meeting_id": meeting.meeting_id})
                        break
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
    finally:
        # Stop recording — always runs even if browser errors
        audio_path = capture.stop()

    # Transcribe
    meeting.transition(MeetingStatus.TRANSCRIBING)
    _emit({"status": "TRANSCRIBING", "meeting_id": meeting.meeting_id})

    if not audio_path:
        _emit({"status": "TRANSCRIBING_SKIPPED", "reason": "no audio file", "meeting_id": meeting.meeting_id})
        meeting.transition(MeetingStatus.DONE)
        return

    try:
        segments = transcribe_audio(audio_path)
        employees = load_speakers()
        speaker_map = resolve_speakers(segments, meeting.participants, employees)
        for seg in segments:
            seg.speaker = speaker_map.get(seg.speaker, seg.speaker)

        _write_transcript(segments, screenshot_dir)
        meeting.transcript_path = str(screenshot_dir / "transcript.txt")
        meeting.transition(MeetingStatus.DONE)
        _emit({
            "status": "DONE",
            "meeting_id": meeting.meeting_id,
            "transcript": meeting.transcript_path,
            "segments": len(segments),
        })
    except Exception as exc:
        meeting.transition(MeetingStatus.FAILED, FailReason.TRANSCRIPTION_FAILED)
        _emit({
            "status": "FAILED",
            "reason": "TRANSCRIPTION_FAILED",
            "meeting_id": meeting.meeting_id,
            "error": str(exc),
        })
