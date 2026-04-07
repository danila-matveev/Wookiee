"""Sync Google Sheets → Supabase (product matrix).

Usage:
    python scripts/sync_sheets_to_supabase.py [--level LEVEL] [--dry-run] [--spreadsheet-id ID]

Levels: all (default), statusy, modeli_osnova, modeli, artikuly, tovary
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Optional

import gspread
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---

SPREADSHEET_ID = os.getenv(
    "PRODUCT_MATRIX_SPREADSHEET_ID",
    "19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg",
)

LEVELS_ORDER = ["statusy", "cveta", "modeli_osnova", "modeli", "artikuly", "tovary"]

SA_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "services/sheets_sync/credentials/google_sa.json",
)

ARCHIVE_STATUS = "Архив"


# --- Supabase connection ---

def get_supabase_conn():
    """Connect to Supabase via psycopg2."""
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", ""),
    )


def query_all(conn, sql: str) -> list[dict]:
    """Execute SQL and return list of dicts."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


# --- Sheets loader ---

def get_sheets_client() -> gspread.Client:
    """Authenticate and return gspread client."""
    creds = Credentials.from_service_account_file(
        SA_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)


def load_sheet_as_dicts(client: gspread.Client, spreadsheet_id: str, tab_name: str) -> list[dict]:
    """Load a sheet tab as list of dicts (header row = keys)."""
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(tab_name)
    rows = ws.get_all_values()
    if len(rows) < 2:
        return []
    headers = rows[0]
    result = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        d = {}
        for i, h in enumerate(headers):
            if h and i < len(row):
                d[h] = row[i]
        result.append(d)
    return result


# --- Normalization ---

def normalize_key(value: str) -> str:
    """Normalize a text key: lowercase, strip, remove trailing /."""
    if not value:
        return ""
    return value.strip().lower().rstrip("/")


def clean_barcode(value: str) -> Optional[str]:
    """Clean barcode value; return None if invalid."""
    if not value or not value.strip():
        return None
    v = value.strip()
    if v.endswith(".0"):
        v = v[:-2]
    if not v.isdigit() or len(v) < 10:
        return None
    return v


def clean_string(value: str) -> Optional[str]:
    """Clean string value."""
    if not value or not value.strip() or value.strip().lower() == "nan":
        return None
    return value.strip()


def clean_numeric(value: str) -> Optional[float]:
    """Clean numeric value."""
    if not value or not value.strip():
        return None
    try:
        return float(value.replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def clean_integer(value: str) -> Optional[int]:
    """Clean integer value."""
    n = clean_numeric(value)
    return int(n) if n is not None else None


def clean_boolean(value: str) -> bool:
    """Convert to boolean."""
    if not value:
        return False
    return value.strip().lower() in ("да", "yes", "true", "1", "д")
