from __future__ import annotations

"""Configuration for wb_sheets_sync module."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass
class Cabinet:
    """Marketplace cabinet (ООО or ИП)."""

    name: str
    wb_api_key: str
    ozon_client_id: str
    ozon_api_key: str


# --- Cabinets ---
CABINET_IP = Cabinet(
    name="ИП",
    wb_api_key=os.getenv("WB_API_KEY_IP", ""),
    ozon_client_id=os.getenv("OZON_CLIENT_ID_IP", ""),
    ozon_api_key=os.getenv("OZON_API_KEY_IP", ""),
)

CABINET_OOO = Cabinet(
    name="ООО",
    wb_api_key=os.getenv("WB_API_KEY_OOO", ""),
    ozon_client_id=os.getenv("OZON_CLIENT_ID_OOO", ""),
    ozon_api_key=os.getenv("OZON_API_KEY_OOO", ""),
)

ALL_CABINETS = [CABINET_IP, CABINET_OOO]

# --- МойСклад ---
MOYSKLAD_TOKEN = os.getenv("MOYSKLAD_TOKEN", "")

# --- Google Sheets ---
GOOGLE_SA_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    str(Path(__file__).parent / "credentials" / "google_sa.json"),
)
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SPREADSHEET_IDS = [s.strip() for s in os.getenv("SPREADSHEET_IDS", "").split(",") if s.strip()]
if not SPREADSHEET_IDS:
    SPREADSHEET_IDS = [SPREADSHEET_ID] if SPREADSHEET_ID else []

# Runtime override for multi-spreadsheet support
_active_spreadsheet_id: str | None = None


def get_active_spreadsheet_id() -> str:
    """Return the currently active spreadsheet ID (override or default)."""
    return _active_spreadsheet_id or SPREADSHEET_ID


def set_active_spreadsheet_id(sid: str | None) -> None:
    """Set a temporary override for the active spreadsheet ID."""
    global _active_spreadsheet_id
    _active_spreadsheet_id = sid


# --- Test mode: write to *_TEST sheets ---
TEST_MODE = os.getenv("SYNC_TEST_MODE", "true").lower() == "true"
_test_mode_override: bool | None = None

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def is_test_mode() -> bool:
    """Return effective test mode, including temporary runtime override."""
    return TEST_MODE if _test_mode_override is None else _test_mode_override


@contextmanager
def test_mode_override(value: bool | None) -> Iterator[None]:
    """Temporarily override TEST_MODE for one run.

    Used by checkbox polling: when a production sheet checkbox fires while the
    service process runs with SYNC_TEST_MODE=true, that one sync must still
    target the production sheet that actually triggered it.
    """
    global _test_mode_override
    previous = _test_mode_override
    if value is not None:
        _test_mode_override = value
    try:
        yield
    finally:
        _test_mode_override = previous


def get_sheet_name(base_name: str) -> str:
    """Return sheet name with _TEST suffix if effective test mode is on."""
    return f"{base_name}_TEST" if is_test_mode() else base_name
