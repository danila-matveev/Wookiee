"""Plan-fact data collector: plan from Google Sheets + MTD info."""
from __future__ import annotations

import json
import subprocess
from calendar import monthrange
from datetime import date

# Financier plan sheet
FINANCIER_SHEET_ID = "1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk"


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


def collect_plan_fact(start: str, end: str, month_start: str) -> dict:
    """Collect plan data and compute MTD ratios.

    Args:
        start: period start (YYYY-MM-DD)
        end: period end (YYYY-MM-DD)
        month_start: first day of the month (YYYY-MM-DD)

    Returns:
        {"plan_fact": {...}} with plan data and MTD info.
    """
    # Read plan from Sheets
    plan_wb = _gws_read(FINANCIER_SHEET_ID, "WB!A1:Z50")
    plan_ozon = _gws_read(FINANCIER_SHEET_ID, "OZON!A1:Z30")

    # Compute MTD info
    ms = date.fromisoformat(month_start)
    end_date = date.fromisoformat(end)
    dim = monthrange(ms.year, ms.month)[1]
    days_elapsed = (end_date - ms).days + 1  # inclusive
    mtd_ratio = days_elapsed / dim if dim > 0 else 0

    return {
        "plan_fact": {
            "plan_wb": plan_wb,
            "plan_ozon": plan_ozon,
            "mtd": {
                "days_in_month": dim,
                "days_elapsed": days_elapsed,
                "mtd_ratio": round(mtd_ratio, 4),
            },
        }
    }
