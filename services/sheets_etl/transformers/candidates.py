"""inst на проверку → crm.blogger_candidates.

Cols 0..13 by header:
  0: Блогер (handle)        1: ТГ-канал (source_url)   2: Подписки (audience)
  3: Охваты                 4: Цена                    5: Кол-во интеграций
  6: Сумма денег            7: Сумма охватов           8: Средний CPM (avg_cpm_estimate)
  9: Min CPM                10: Max CPM                11: Сумма Кликов
  12: Средний CPC           13: Min CPC
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_decimal, parse_int


def transform(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values or len(values) < 2:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values[1:]:
        if not raw or not raw[0]:
            continue
        handle = str(raw[0]).strip()
        if not handle or handle in seen:
            continue
        seen.add(handle)
        rows.append({
            "handle": handle,
            "source_url": str(raw[1]).strip() if len(raw) > 1 and raw[1] else None,
            "audience": parse_int(raw[2]) if len(raw) > 2 else None,
            "avg_cpm_estimate": parse_decimal(raw[8]) if len(raw) > 8 else None,
            "status": "new",
            "sheet_row_id": sheet_row_id([handle]),
        })
    return rows
