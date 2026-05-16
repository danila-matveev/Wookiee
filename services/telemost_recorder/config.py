import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

BOT_NAME: str = os.getenv("TELEMOST_BOT_NAME", "Wookiee Recorder")
JOIN_TIMEOUT: int = int(os.getenv("TELEMOST_JOIN_TIMEOUT", "60"))
WAITING_ROOM_TIMEOUT: int = int(os.getenv("TELEMOST_WAITING_ROOM_TIMEOUT", "600"))
SCREENSHOT_INTERVAL: int = int(os.getenv("TELEMOST_SCREENSHOT_INTERVAL", "30"))
# Headless avoids the macOS "Open Yandex Telemost?" OS dialog triggered by btn://.
# Set TELEMOST_HEADLESS=false only for local debugging where you need to see the browser.
HEADLESS: bool = os.getenv("TELEMOST_HEADLESS", "true").lower() != "false"

# Path to a Playwright storage_state JSON (cookies + localStorage) for a
# pre-authenticated Yandex 360 Business user. When set, the recorder joins
# Telemost as that authenticated participant instead of an anonymous guest —
# Yandex does not subject authenticated participants to the guest anti-bot
# kick (~30-300s redirect to homepage) that was breaking recordings.
# Empty/unset = legacy guest mode (kept for tests and local debugging).
STORAGE_STATE_PATH: str = os.getenv("TELEMOST_STORAGE_STATE_PATH", "")

# Debug helper: when set to "1", the recorder dumps the participants-panel DOM
# (and a snapshot of the full page) the first time extract_participants() returns
# an empty list on a non-empty meeting. Used to capture the live HTML structure
# of Yandex 360 corporate UI so the selectors in extract_participants() can be
# repaired. Off by default — production-safe.
DUMP_PARTICIPANTS_DOM: bool = os.getenv("TELEMOST_DUMP_PARTICIPANTS_DOM", "").strip() == "1"

# Phase 2 — audio + transcription
SPEECHKIT_API_KEY: str = os.getenv("SPEECHKIT_API_KEY", "")
YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
TELEMOST_CAPTURE: bool = os.getenv("TELEMOST_CAPTURE", "true").lower() != "false"
MAX_RECORDING_MINUTES: int = int(os.getenv("MAX_RECORDING_MINUTES", "240"))
AUDIO_BITRATE: str = os.getenv("TELEMOST_AUDIO_BITRATE", "64k")
SPEAKERS_FILE: Path = _PROJECT_ROOT / "data" / "speakers.yml"
BITRIX_REST_API: str = os.getenv("Bitrix_rest_api", "")

BROWSER_FLAGS: list[str] = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    # Suppress Chromium's "Open external app?" dialog for custom protocols (btn://)
    "--disable-features=ExternalProtocolDialogShowAlwaysOpen",
    "--no-default-browser-check",
]

# Display names of known meeting bots that should NOT count as humans for
# meeting-ended detection. Substring match (case-insensitive) so trailing
# emoji / suffixes don't break filtering.
# All entries MUST be lowercase — match is case-insensitive via .lower()
# on the participant side. Prefer distinctive tokens over short generic ones
# to avoid false positives on human names (e.g. "sber salut", not "salut").
KNOWN_BOT_NAMES: frozenset[str] = frozenset({
    "wookiee recorder",      # this bot itself
    "navstreche.com",        # navstreche AI assistant
    "sber salut",            # Sber Salut (specific token, "salut" alone catches Salutamica etc.)
    "yandex go",             # Yandex assistant
    "ии-ассистент",          # russian generic AI assistant suffix
})
