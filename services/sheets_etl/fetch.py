"""Reads Google Sheets via service account credentials (gspread)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

_DEFAULT_SA = (
    Path(__file__).resolve().parents[2]
    / "sheets_sync"
    / "credentials"
    / "google_sa.json"
)
_SA_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(_DEFAULT_SA))
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def read_range(spreadsheet_id: str, sheet_range: str) -> list[list[Any]]:
    """Return values matrix; row 0 is the header."""
    ws_name, cell_range = sheet_range.split("!", 1)
    creds = Credentials.from_service_account_file(_SA_FILE, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(spreadsheet_id).worksheet(ws_name)
    return ws.get(cell_range) or []
