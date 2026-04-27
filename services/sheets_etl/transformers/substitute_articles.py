"""Подменные → crm.substitute_articles + crm.substitute_article_metrics_weekly.

Wide layout: meta cols 0-7, then 4-col weekly blocks starting at col 9.
Each block: [Частота, Переходы, Добавления, Заказы]. Row 1 carries week_start
in the first col of each block (cols 9, 13, 17, ...).

Returns (articles, metrics). Articles do NOT carry artikul_id — the loader
resolves that against public.artikuly by code (LOWER match) before upsert.
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_date, parse_int

WEEK_START_COL = 9
WEEK_BLOCK_SIZE = 4

_PURPOSE_MAP = {
    "яндекс": "yandex",
    "таргет вк": "vk_target",
    "adblogger": "adblogger",
    "креаторы": "creators",
    "блогеры": "creators",
    "брендированный запрос": "other",
}

_STATUS_MAP = {
    "используется": "active",
    "продается": "active",
    "продаётся": "active",
    "активно": "active",
    "active": "active",
    "пауза": "paused",
    "приостановлено": "paused",
    "архив": "archived",
    "архивный": "archived",
}


def _normalize_purpose(s: str) -> str:
    return _PURPOSE_MAP.get((s or "").strip().lower(), "other")


def _normalize_status(s: str) -> str:
    return _STATUS_MAP.get((s or "").strip().lower(), "active")


def transform(values: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not values or len(values) < 3:
        return [], []
    week_dates_row = values[1]
    week_starts: list[tuple[int, Any]] = []
    for col in range(WEEK_START_COL, len(week_dates_row), WEEK_BLOCK_SIZE):
        d = parse_date(week_dates_row[col]) if col < len(week_dates_row) else None
        if d:
            week_starts.append((col, d))

    articles: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for raw in values[2:]:
        if not raw or len(raw) < 3 or not raw[2]:
            continue
        code = str(raw[2]).strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        articles.append({
            "code": code,
            "purpose": _normalize_purpose(raw[3]) if len(raw) > 3 and raw[3] else "other",
            "nomenklatura_wb": str(raw[1]).strip() if len(raw) > 1 and raw[1] else None,
            "campaign_name": str(raw[5]).strip() if len(raw) > 5 and raw[5] else None,
            "status": _normalize_status(raw[4]) if len(raw) > 4 and raw[4] else "active",
            "sheet_row_id": sheet_row_id([code]),
        })

        for col, week_start in week_starts:
            freq = parse_int(raw[col])     if len(raw) > col else None
            tran = parse_int(raw[col + 1]) if len(raw) > col + 1 else None
            adds = parse_int(raw[col + 2]) if len(raw) > col + 2 else None
            ords = parse_int(raw[col + 3]) if len(raw) > col + 3 else None
            if freq is None and tran is None and adds is None and ords is None:
                continue
            metrics.append({
                "sub_code_ref": code,
                "week_start": week_start,
                "frequency": freq,
                "transitions": tran,
                "additions": adds,
                "orders": ords,
            })
    return articles, metrics
