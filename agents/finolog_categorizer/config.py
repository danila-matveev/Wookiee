"""
Finolog Categorizer Agent — configuration.

Reads from .env (same as Oleg agent).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

# Finolog API (READ-ONLY — agent never writes to Finolog)
FINOLOG_API_KEY: str = os.getenv("FINOLOG_API_KEY", "")
FINOLOG_BIZ_ID: int = int(os.getenv("FINOLOG_BIZ_ID", "48556"))

# Notion
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Scheduler
SCAN_TIME: str = os.getenv("FINOLOG_CATEGORIZATION_TIME", "05:00")
TIMEZONE: str = "Europe/Moscow"

# Classification thresholds
HIGH_CONFIDENCE_THRESHOLD: float = 0.85

# Data paths
DATA_DIR: Path = Path(__file__).parent / "data"
DB_PATH: str = str(DATA_DIR / "categorizer.db")
CONTRACTOR_RULES_PATH: str = str(ROOT / "data" / "finolog_analysis" / "analysis_results.json")
