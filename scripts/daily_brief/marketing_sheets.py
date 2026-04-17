"""Daily Brief — маркетинговые данные из Google Sheets.

Собирает:
- Блогеры: публикации за период + запланированные (по дате публикации)
- ВК/Яндекс: размещения (если есть даты)
- СММ: недельный отчёт (последняя неделя)

Пример вызова: collect_marketing_sheets(target=date(2026,4,16), past_days=7, future_days=3)

Если `gws` CLI или листы недоступны — вернёт пустые структуры с error-полем.
"""
from __future__ import annotations
import json
import re
import subprocess
from datetime import date, datetime, timedelta

BLOGGERS_SHEET_ID = "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk"
VK_SHEET_ID = "1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU"
SMM_SHEET_ID = "19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU"


def _gws_read(sheet_id: str, range_str: str) -> list[list[str]]:
    """Читает диапазон из Google Sheets через gws CLI. Пустой список при ошибке."""
    try:
        cmd = ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        return data.get("values", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def _safe_float(val) -> float:
    if not val:
        return 0.0
    try:
        cleaned = (str(val)
                   .replace(",", ".").replace(" ", "").replace("\xa0", "")
                   .replace("₽", "").replace("р.", "").replace("%", "").strip())
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _parse_date(val, fallback_year: int | None = None) -> date | None:
    """Пытается распарсить разные форматы русских дат.

    fallback_year используется для форматов без года (DD.MM) — позволяет
    корректно парсить бэкфил около границы года (иначе всегда подставляется
    текущий год).
    """
    if not val:
        return None
    s = str(val).strip()
    # ISO: 2026-04-16
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # DD.MM.YYYY или DD.MM.YY
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{2,4})", s)
    if m:
        y = int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # DD.MM (год = fallback_year или текущий)
    m = re.match(r"^(\d{1,2})[./](\d{1,2})$", s)
    if m:
        y = fallback_year if fallback_year is not None else datetime.now().year
        try:
            return date(y, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def collect_bloggers_window(target: date, past_days: int = 7, future_days: int = 3) -> dict:
    """Блогеры: публикации в окне [target-past_days, target+future_days].

    Структура листа 'Блогеры' (по колонкам, 0-based):
    0 Никнейм, 1 Маркетолог, 2 Ссылка, 3 Неделя, 4 Месяц, 5 Дата публикации,
    6 Артикул, 7 Вид рекламы, 8 Магазин, 9 Канал, 10 Стоимость размещения,
    13 Итоговая цена, 23 Просмотры ФАКТ, 25 Клики, 28 Корзин, 30 Заказы
    """
    rows = _gws_read(BLOGGERS_SHEET_ID, "'Блогеры'!A1:AF800")
    if not rows:
        return {"error": "sheet_unavailable", "recent": [], "upcoming": [], "totals": {}}

    window_start = target - timedelta(days=past_days - 1)
    window_end = target + timedelta(days=future_days)

    recent = []  # [window_start, target]
    upcoming = []  # (target, window_end]

    for row in rows[1:]:
        if not row or len(row) < 6:
            continue
        pub_date = _parse_date(row[5] if len(row) > 5 else None, fallback_year=target.year)
        if not pub_date:
            continue

        spend = _safe_float(row[13]) if len(row) > 13 else 0
        if spend <= 0:
            spend = _safe_float(row[10]) if len(row) > 10 else 0

        item = {
            "date": pub_date.isoformat(),
            "blogger": (row[0] or "").strip() if len(row) > 0 else "",
            "article": (row[6] or "").strip() if len(row) > 6 else "",
            "type": (row[7] or "").strip() if len(row) > 7 else "",
            "shop": (row[8] or "").strip() if len(row) > 8 else "",
            "channel": (row[9] or "").strip() if len(row) > 9 else "",
            "spend": round(spend),
            "views": round(_safe_float(row[23]) if len(row) > 23 else 0),
            "clicks": round(_safe_float(row[25]) if len(row) > 25 else 0),
            "orders": round(_safe_float(row[30]) if len(row) > 30 else 0),
        }

        if window_start <= pub_date <= target:
            recent.append(item)
        elif target < pub_date <= window_end:
            upcoming.append(item)

    def _sum(items, key):
        return sum(i.get(key, 0) for i in items)

    totals = {
        "recent": {
            "placements": len(recent),
            "spend": _sum(recent, "spend"),
            "views": _sum(recent, "views"),
            "clicks": _sum(recent, "clicks"),
            "orders": _sum(recent, "orders"),
        },
        "upcoming": {
            "placements": len(upcoming),
            "spend": _sum(upcoming, "spend"),
        },
    }
    return {
        "recent": sorted(recent, key=lambda x: x["date"], reverse=True),
        "upcoming": sorted(upcoming, key=lambda x: x["date"]),
        "totals": totals,
    }


def collect_vk_window(target: date, past_days: int = 7) -> dict:
    """ВК/Яндекс: размещения в окне. Читает сырые строки, парсит даты из первой колонки, которая похожа на дату."""
    rows = _gws_read(VK_SHEET_ID, "A1:Z300")
    if not rows:
        return {"error": "sheet_unavailable", "recent": [], "totals": {}}

    window_start = target - timedelta(days=past_days - 1)
    recent = []
    total_spend = 0.0

    for row in rows[1:]:
        if not row:
            continue
        # Ищем первую клетку которая парсится как дата
        row_date = None
        for cell in row[:3]:
            row_date = _parse_date(cell, fallback_year=target.year)
            if row_date:
                break
        if not row_date or not (window_start <= row_date <= target):
            continue

        # Ищем первое числовое значение >= 100 как расход (грубо)
        spend = 0.0
        for cell in row[1:]:
            v = _safe_float(cell)
            if v >= 100:
                spend = v
                break

        recent.append({
            "date": row_date.isoformat(),
            "row_summary": " | ".join(str(c)[:60] for c in row[:6] if c),
            "spend": round(spend),
        })
        total_spend += spend

    return {
        "recent": sorted(recent, key=lambda x: x["date"], reverse=True),
        "totals": {"placements": len(recent), "spend": round(total_spend)},
    }


def collect_smm_week(target: date) -> dict:
    """СММ: последняя недельная строка из листа 'Понедельный отчёт'."""
    rows = _gws_read(SMM_SHEET_ID, "'Понедельный отчёт'!A1:Z100")
    if not rows:
        return {"error": "sheet_unavailable", "last_row": None}

    # Ищем последнюю строку с непустой датой в первых 3 колонках
    last_row_with_date = None
    for row in rows[1:]:
        if not row:
            continue
        for cell in row[:3]:
            d = _parse_date(cell, fallback_year=target.year)
            if d and d <= target:
                last_row_with_date = (d, row)
                break

    if not last_row_with_date:
        return {"last_row": None}

    d, row = last_row_with_date
    # Вытаскиваем все числовые значения
    numerics = []
    for cell in row:
        v = _safe_float(cell)
        if v > 0:
            numerics.append(v)

    return {
        "last_row_date": d.isoformat(),
        "raw_row": [str(c)[:80] for c in row[:15] if c],
        "numeric_values": numerics[:10],
    }


def collect_marketing_sheets(target: date, past_days: int = 7, future_days: int = 3) -> dict:
    """Главный сборщик маркетинга."""
    return {
        "bloggers": collect_bloggers_window(target, past_days, future_days),
        "vk": collect_vk_window(target, past_days),
        "smm_week": collect_smm_week(target),
    }
