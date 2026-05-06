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
