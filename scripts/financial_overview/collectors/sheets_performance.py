"""External performance marketing collector — reads from Google Sheets via gws CLI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

SHEET_ID = os.getenv("PERFORMANCE_SHEET_ID", "1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg")


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    stdout = result.stdout.strip()
    # gws may return JSON error even with exit code 0
    if result.returncode != 0 or '"error"' in stdout:
        err = result.stderr.replace("Using keyring backend: keyring", "").strip()
        raise RuntimeError(f"gws read failed (exit {result.returncode}): {err or stdout[:200]}")
    rows = []
    for line in stdout.split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def _safe_float(val) -> float:
    """Safely convert a value to float, handling commas and spaces."""
    if not val:
        return 0.0
    try:
        return float(str(val).replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except (ValueError, TypeError):
        return 0.0


def collect_performance(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect external performance marketing data from Google Sheets.

    Reads the 'Итог Март' style sheets and aggregates by month.
    Returns monthly data with: spend, clicks, cpc, views, cpm.
    """
    monthly = {}
    for sheet_name in ["Итог Март", "Итог Февраль", "Итог Январь",
                       "Итог Декабрь", "Итог Ноябрь", "Итог Октябрь"]:
        try:
            rows = _gws_read(SHEET_ID, f"'{sheet_name}'!A1:Q50")
            if rows:
                for row in rows:
                    if row and row[0].strip().lower() == "итого":
                        monthly[sheet_name] = {
                            "spend_nds": _safe_float(row[1]) if len(row) > 1 else 0,
                            "clicks": _safe_float(row[2]) if len(row) > 2 else 0,
                            "cpc": _safe_float(row[3]) if len(row) > 3 else 0,
                            "views": _safe_float(row[4]) if len(row) > 4 else 0,
                            "cpm": _safe_float(row[5]) if len(row) > 5 else 0,
                        }
                        break
        except Exception:
            continue

    return {"monthly": monthly}
