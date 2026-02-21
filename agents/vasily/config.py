"""Configuration for Vasily Agent — periodic localization reports."""
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

# ============================================================================
# Bitrix24
# ============================================================================
BITRIX_WEBHOOK_URL: str = os.getenv("Bitrix_rest_api", "")
BITRIX_CHAT_ID: str = os.getenv("VASILY_BITRIX_CHAT_ID", "")
BITRIX_FOLDER_ID: str = os.getenv("VASILY_BITRIX_FOLDER_ID", "")

# ============================================================================
# Report schedule
# ============================================================================
REPORT_DAY_OF_WEEK: str = os.getenv("VASILY_REPORT_DAY_OF_WEEK", "*")
REPORT_PERIOD_DAYS: int = int(os.getenv("VASILY_REPORT_PERIOD_DAYS", "2"))
REPORT_HOUR: int = int(os.getenv("VASILY_REPORT_HOUR", "8"))
REPORT_MINUTE: int = int(os.getenv("VASILY_REPORT_MINUTE", "0"))

# Cabinets to process
CABINETS: list = os.getenv("VASILY_CABINETS", "ip,ooo").split(",")

# ============================================================================
# General
# ============================================================================
TIMEZONE: str = "Europe/Moscow"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = str(Path(__file__).parent / "logs" / "vasily.log")
