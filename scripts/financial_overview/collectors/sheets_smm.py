"""SMM data collector — reads from Google Sheets via gws CLI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

SHEET_ID = os.getenv("SMM_SHEET_ID", "19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU")


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"gws read failed: {result.stderr}")
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def _safe_float(val) -> float:
    if not val:
        return 0.0
    try:
        return float(str(val).replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except (ValueError, TypeError):
        return 0.0


def collect_smm(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect SMM data from Google Sheets.

    Reads 'Отчёт месяц' sheet for monthly aggregates.
    """
    rows = _gws_read(SHEET_ID, "'Отчёт месяц'!A1:N20")

    monthly = {}
    if len(rows) >= 3:
        for row in rows:
            if row and row[0].strip().lower() in ("затраты", "показы", "cpv", "переходы", "cr", "cpc"):
                metric = row[0].strip().lower()
                for i, val in enumerate(row[1:], 1):
                    month_key = f"col_{i}"
                    if month_key not in monthly:
                        monthly[month_key] = {}
                    monthly[month_key][metric] = _safe_float(val) if metric != "cr" else val

    return {"monthly": monthly, "raw_rows": len(rows)}
