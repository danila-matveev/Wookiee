"""Configuration for WB localization service."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================================
# Google Sheets (отдельная таблица для локализации)
# ============================================================================
GOOGLE_SA_FILE: str = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    str(PROJECT_ROOT / "wb_sheets_sync" / "credentials" / "google_sa.json"),
)
VASILY_SPREADSHEET_ID: str = os.getenv("VASILY_SPREADSHEET_ID", "")

# Period and cabinets for service/API runs
REPORT_PERIOD_DAYS: int = int(os.getenv("VASILY_REPORT_PERIOD_DAYS", "2"))
CABINETS: list = os.getenv("VASILY_CABINETS", "ip,ooo").split(",")
