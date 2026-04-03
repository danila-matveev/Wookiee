"""Blogger campaigns collector — reads from Google Sheets via gws CLI."""
from __future__ import annotations

import json as json_mod
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
    """Read a range from Google Sheets via gws CLI. Returns list of rows."""
    cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
        cleaned = (str(val)
                   .replace(",", ".")
                   .replace(" ", "")
                   .replace("\xa0", "")
                   .replace("₽", "")
                   .replace("р.", "")
                   .replace("%", "")
                   .strip())
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _clean_month_name(raw: str) -> str:
    """Strip quotes, commas, and normalize month header."""
    return raw.strip().strip('"').strip("'").rstrip(",").strip()


def _is_month_header(cell: str) -> bool:
    """Check if cell looks like a month header (e.g. 'Январь 2026', '"МАРТ 2025"')."""
    cleaned = _clean_month_name(cell).lower()
    return (any(m in cleaned for m in MONTHS_RU) and
            any(y in cleaned for y in ["2024", "2025", "2026"]))


def collect_bloggers(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect blogger campaign data from Google Sheets.

    Sheet structure ('Блогеры'):
    - Row 0: header (Никнейм, Маркетолог, Ссылка, неделя, месяц, Дата публикации,
                      Артикул, Вид рекламы, Магазин, Канал, Стоимость размещения[10],
                      Стоимость доставки[11], Себестоймость комплектов[12],
                      Итоговая цена[13], ..., Просмотры ФАКТ[23], CPM ФАКТ[24],
                      Клики[25], CTR[26], CPC[27], Корзин[28], CR в корзину[29],
                      Заказы[30], CR в заказ[31])
    - Rows: data interleaved with month headers in column A
    """
    rows = _gws_read(SHEET_ID, "'Блогеры'!A1:AF800")

    monthly = {}
    current_month = None

    for row in rows[1:]:  # Skip header row
        if not row or not row[0]:
            continue

        first_cell = row[0].strip()

        # Detect month headers
        if _is_month_header(first_cell):
            current_month = _clean_month_name(first_cell)
            monthly[current_month] = {
                "placements": 0, "budget": 0, "views": 0,
                "clicks": 0, "carts": 0, "orders": 0,
            }
            continue

        if current_month and len(row) >= 11:
            # Primary spend: col 13 (Итоговая цена), fallback: col 10 (Стоимость размещения)
            spend = _safe_float(row[13]) if len(row) > 13 else 0
            if spend <= 0:
                spend = _safe_float(row[10]) if len(row) > 10 else 0

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
