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
