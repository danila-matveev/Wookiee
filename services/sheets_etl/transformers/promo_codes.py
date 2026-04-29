"""Промокоды_справочник → crm.promo_codes."""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_date, parse_decimal


def transform(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values or len(values) < 2:
        return []
    rows: list[dict[str, Any]] = []
    for raw in values[1:]:
        if not raw or len(raw) < 2 or not raw[1]:
            continue
        code = str(raw[1]).strip()
        external_uuid = str(raw[0]).strip() if raw[0] else None
        if not code:
            continue
        rows.append({
            "code": code,
            "external_uuid": external_uuid,
            "channel": str(raw[2]).strip() if len(raw) > 2 and raw[2] else None,
            "discount_pct": parse_decimal(raw[3]) if len(raw) > 3 else None,
            "valid_from": parse_date(raw[4]) if len(raw) > 4 else None,
            "valid_until": parse_date(raw[5]) if len(raw) > 5 else None,
            "notes": str(raw[6]).strip() if len(raw) > 6 and raw[6] else None,
            "status": "active",
            "sheet_row_id": sheet_row_id([code]),
        })
    return rows
