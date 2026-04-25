"""External performance marketing collector — reads from Google Sheets via gws CLI."""
from __future__ import annotations

import json as json_mod
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

SHEET_ID = os.getenv("PERFORMANCE_SHEET_ID", "1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg")


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI. Returns list of rows (lists of strings)."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    stdout = result.stdout.strip()
    if result.returncode != 0 or '"error"' in stdout:
        err = result.stderr.replace("Using keyring backend: keyring", "").strip()
        raise RuntimeError(f"gws read failed (exit {result.returncode}): {err or stdout[:200]}")
    data = json_mod.loads(stdout)
    return data.get("values", [])


def _safe_float(val) -> float:
    """Safely convert a value to float, handling commas, spaces, currency symbols."""
    if not val:
        return 0.0
    try:
        cleaned = str(val).replace(",", ".").replace(" ", "").replace("\xa0", "").replace("₽", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def collect_performance(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect external performance marketing data from Google Sheets.

    Each 'Итог {Month}' sheet has:
    - Row 0: platform name + date range
    - Row 1: end date
    - Row 2: header (Модель, Расход с НДС, Внешние переходы, Стоимость внешнего перехода, Просмотры, CPM, ...)
    - Row 3+: model data

    We sum across all models per sheet to get totals.
    """
    monthly = {}
    for sheet_name in ["Итог Март", "Итог Февраль", "Итог Январь",
                       "Итог Декабрь", "Итог Ноябрь", "Итог Октябрь"]:
        try:
            rows = _gws_read(SHEET_ID, f"'{sheet_name}'!A1:Q50")
            if len(rows) < 3:
                continue

            totals = {"spend_nds": 0, "clicks": 0, "views": 0}
            for row in rows[3:]:  # Skip header rows (0-2)
                if not row or not row[0]:
                    continue
                label = row[0].strip().lower()
                if label in ("итого", "итог", ""):
                    continue
                # Col 1 = Расход с НДС, Col 2 = Внешние переходы, Col 4 = Просмотры
                totals["spend_nds"] += _safe_float(row[1]) if len(row) > 1 else 0
                totals["clicks"] += _safe_float(row[2]) if len(row) > 2 else 0
                totals["views"] += _safe_float(row[4]) if len(row) > 4 else 0

            if totals["spend_nds"] > 0:
                totals["cpc"] = round(totals["spend_nds"] / totals["clicks"], 2) if totals["clicks"] else 0
                totals["cpm"] = round(totals["spend_nds"] / totals["views"] * 1000, 2) if totals["views"] else 0
                monthly[sheet_name] = totals
        except Exception:
            continue

    return {"monthly": monthly}
