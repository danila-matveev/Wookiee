"""Configuration for wb_sheets_sync module."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


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

# --- Test mode: write to *_TEST sheets ---
TEST_MODE = os.getenv("SYNC_TEST_MODE", "true").lower() == "true"

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def get_sheet_name(base_name: str) -> str:
    """Return sheet name with _TEST suffix if TEST_MODE is on."""
    return f"{base_name}_TEST" if TEST_MODE else base_name
