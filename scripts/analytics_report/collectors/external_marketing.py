"""External marketing data collector: bloggers, seedings, VK/Yandex, SMM."""
from __future__ import annotations

import json
import subprocess

# Google Sheet IDs
BLOGGERS_SHEET_ID = "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk"
EXTERNAL_TRAFFIC_SHEET_ID = "1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU"
SMM_SHEET_ID = "19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU"


def _gws_read(sheet_id: str, range_str: str) -> list:
    """Read a range from Google Sheets via gws CLI."""
    try:
        result = subprocess.run(
            ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("values", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return []


def collect_external_marketing(start: str, end: str) -> dict:
    """Collect external marketing data from Google Sheets.

    Args:
        start: period start (YYYY-MM-DD)
        end: period end (YYYY-MM-DD)

    Returns:
        {"external_marketing": {...}} with bloggers, external traffic, SMM data.
    """
    # Bloggers + seedings
    bloggers = _gws_read(BLOGGERS_SHEET_ID, "'блогеры'!A1:AF800")
    seedings = _gws_read(BLOGGERS_SHEET_ID, "'посевы'!A1:AF800")

    # External traffic (VK, Yandex)
    external_traffic = _gws_read(EXTERNAL_TRAFFIC_SHEET_ID, "A1:Z100")

    # SMM reports
    smm_monthly = _gws_read(SMM_SHEET_ID, "'Отчёт месяц'!A1:Z50")
    smm_weekly = _gws_read(SMM_SHEET_ID, "'Понедельный отчёт'!A1:Z100")

    return {
        "external_marketing": {
            "bloggers": bloggers,
            "seedings": seedings,
            "external_traffic": external_traffic,
            "smm_monthly": smm_monthly,
            "smm_weekly": smm_weekly,
        }
    }
