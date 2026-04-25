"""SMM data collector — reads from Google Sheets via gws CLI."""
from __future__ import annotations

import json as json_mod
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

SHEET_ID = os.getenv("SMM_SHEET_ID", "19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU")

# Month name mapping for header row
MONTHS_MAP = {
    "cентябрь": "2025-09", "октябрь": "2025-10", "ноябрь": "2025-11",
    "декабрь": "2025-12", "январь": "2026-01", "февраль": "2026-02",
    "март": "2026-03",
}


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI. Returns list of rows."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    stdout = result.stdout.strip()
    if result.returncode != 0 or '"error"' in stdout:
        err = result.stderr.replace("Using keyring backend: keyring", "").strip()
        raise RuntimeError(f"gws read failed (exit {result.returncode}): {err or stdout[:200]}")
    data = json_mod.loads(stdout)
    return data.get("values", [])


def _safe_float(val) -> float:
    if not val:
        return 0.0
    try:
        cleaned = str(val).replace(",", ".").replace(" ", "").replace("\xa0", "").replace("₽", "").replace("%", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def collect_smm(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect SMM data from Google Sheets.

    Sheet structure ('Отчёт месяц'):
    - Row 0: month names in odd columns (1, 3, 5, ...), even columns = % delta
    - Row 1: date ranges
    - Row 2+: metrics (Затраты, Показы, CPV, Переходы, CR, CPC, then model breakdown)

    We read months from row 0 and metrics from rows 2-6.
    """
    rows = _gws_read(SHEET_ID, "'Отчёт месяц'!A1:N10")

    if len(rows) < 3:
        return {"monthly": {}}

    # Build month index: col_index -> month_key
    header = rows[0]
    month_cols = {}
    for i, val in enumerate(header):
        if val and val.strip():
            month_name = val.strip().lower()
            if month_name in MONTHS_MAP:
                month_cols[i] = MONTHS_MAP[month_name]

    # Metric rows: row 2 = Затраты, row 3 = Показы, row 4 = CPV, row 5 = Переходы, row 6 = CR
    metric_map = {}
    for row in rows[2:7]:
        if not row or not row[0]:
            continue
        label = row[0].strip().lower()
        if label in ("затраты", "показы", "cpv", "переходы", "cr", "cpc"):
            metric_map[label] = row

    monthly = {}
    for col_idx, month_key in month_cols.items():
        data = {}
        for metric, row in metric_map.items():
            if col_idx < len(row):
                data[metric] = _safe_float(row[col_idx])
        if data:
            monthly[month_key] = data

    return {"monthly": monthly}
