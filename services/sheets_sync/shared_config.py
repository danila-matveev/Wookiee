"""
Database configuration for sheets_sync (self-contained copy from shared/config.py).

Only DB-related settings needed by data_layer queries.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root & .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# ============================================================================
# Database (PostgreSQL) — legacy
# ============================================================================
DB_HOST: str = os.getenv('DB_HOST', 'localhost')
DB_PORT: int = int(os.getenv('DB_PORT', '5432'))
DB_USER: str = os.getenv('DB_USER', '')
DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')

DB_CONFIG: dict = {
    'host': DB_HOST,
    'port': DB_PORT,
    'user': DB_USER,
    'password': DB_PASSWORD,
}

DB_WB: str = os.getenv('DB_NAME_WB', 'pbi_wb_wookiee')
DB_OZON: str = os.getenv('DB_NAME_OZON', 'pbi_ozon_wookiee')

# ============================================================================
# Marketplace ETL Database (managed)
# ============================================================================
MARKETPLACE_DB_HOST: str = os.getenv('MARKETPLACE_DB_HOST', '')
MARKETPLACE_DB_PORT: int = int(os.getenv('MARKETPLACE_DB_PORT', '5432'))
MARKETPLACE_DB_NAME: str = os.getenv('MARKETPLACE_DB_NAME', 'wookiee_marketplace')
MARKETPLACE_DB_USER: str = os.getenv('MARKETPLACE_DB_USER', '')
MARKETPLACE_DB_PASSWORD: str = os.getenv('MARKETPLACE_DB_PASSWORD', '')

MARKETPLACE_DB_CONFIG: dict = {
    'host': MARKETPLACE_DB_HOST,
    'port': MARKETPLACE_DB_PORT,
    'database': MARKETPLACE_DB_NAME,
    'user': MARKETPLACE_DB_USER,
    'password': MARKETPLACE_DB_PASSWORD,
}
