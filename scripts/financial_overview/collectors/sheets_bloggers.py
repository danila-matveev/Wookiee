"""Blogger campaigns collector — reads from Google Sheets via gws CLI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

SHEET_ID = os.getenv("BLOGGERS_SHEET_ID", "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk")

MONTHS_RU = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Read a range from Google Sheets via gws CLI."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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


def collect_bloggers(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect blogger campaign data from Google Sheets.

    Reads 'Блогеры' sheet and aggregates by month.
    Monthly aggregates: budget, placements, CPM, CPC, clicks, carts, orders, CR.
    """
    rows = _gws_read(SHEET_ID, "'Блогеры'!A1:AF800")

    monthly = {}
    current_month = None

    for row in rows[2:]:  # Skip header rows
        if not row or not row[0]:
            continue

        first_cell = row[0].strip()
        # Detect month headers like "Октябрь 2025", "Январь 2026"
        if any(m in first_cell.lower() for m in MONTHS_RU) and \
                any(y in first_cell for y in ["2024", "2025", "2026"]):
            current_month = first_cell
            monthly[current_month] = {
                "placements": 0, "budget": 0, "views": 0,
                "clicks": 0, "carts": 0, "orders": 0,
            }
            continue

        if current_month and len(row) >= 6:
            spend = _safe_float(row[13]) if len(row) > 13 else 0  # Column N = итоговая цена
            if spend <= 0:
                spend = _safe_float(row[10]) if len(row) > 10 else 0  # Column K = стоимость

            if spend > 0:
                monthly[current_month]["placements"] += 1
                monthly[current_month]["budget"] += spend
                monthly[current_month]["views"] += _safe_float(row[23]) if len(row) > 23 else 0
                monthly[current_month]["clicks"] += _safe_float(row[25]) if len(row) > 25 else 0
                monthly[current_month]["carts"] += _safe_float(row[28]) if len(row) > 28 else 0
                monthly[current_month]["orders"] += _safe_float(row[30]) if len(row) > 30 else 0

    # Calculate derived metrics
    for month, data in monthly.items():
        views = data["views"]
        clicks = data["clicks"]
        budget = data["budget"]
        data["cpm"] = round(budget / views * 1000, 0) if views else 0
        data["cpc"] = round(budget / clicks, 1) if clicks else 0
        data["cr_cart"] = round(data["carts"] / clicks * 100, 2) if clicks else 0
        data["cr_order"] = round(data["orders"] / clicks * 100, 2) if clicks else 0

    return {"monthly": monthly}
