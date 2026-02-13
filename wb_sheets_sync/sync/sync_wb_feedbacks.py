from __future__ import annotations

"""Sync WB feedbacks -> sheets 'Отзывы ООО' and 'Отзывы ИП'.

Layout (matching original GAS):
    Row 1:  A1="Дата составления отчёта"  B1=date
    Row 2:  A2="Время отчёта"             B2=time
    Row 4:  A4="С"
    Row 5:  A5=start_date                 B5=end_date
    Row 11: D11="Отзывы, в штуках"
    Row 12: C12="Рейтинг" D12="5★" E12="4★" F12="3★" G12="2★" H12="1★"
    Row 13+: A=cabinet B=nmID C=avg_rating D-H=star counts (5->1)
"""

import logging
from collections import defaultdict

from wb_sheets_sync.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    set_checkbox,
    write_range,
)
from wb_sheets_sync.clients.wb_client import WBClient
from wb_sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, SPREADSHEET_ID, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAMES = {
    "ИП": "Отзывы ИП",
    "ООО": "Отзывы ООО",
}


def sync() -> int:
    """Fetch feedbacks from WB and write rating aggregation to sheets.

    Populates nmIDs from API response (not from sheet).
    Returns total number of nmIDs processed.
    """
    logger.info("=== sync_wb_feedbacks: start ===")

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    total = 0

    for cabinet in ALL_CABINETS:
        base_sheet = SHEET_NAMES.get(cabinet.name, f"Отзывы {cabinet.name}")
        sheet_name = get_sheet_name(base_sheet)
        ws = get_or_create_worksheet(spreadsheet, sheet_name)

        client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
        try:
            feedbacks = client.get_all_feedbacks()
            logger.info("[%s] Got %d feedbacks", cabinet.name, len(feedbacks))

            # Aggregate by nmId
            agg = _aggregate_feedbacks(feedbacks)

            # Sort by total feedback count descending
            sorted_nm_ids = sorted(
                agg.keys(),
                key=lambda nm: agg[nm].get("total", 0),
                reverse=True,
            )

            # Clear entire sheet
            ws.clear()

            # Write meta rows
            date_str, time_str = get_moscow_datetime()
            write_range(ws, 1, 1, [["Дата составления отчёта", date_str]])
            write_range(ws, 2, 1, [["Время отчёта", time_str]])

            # Row 4-5: date range
            write_range(ws, 4, 1, [["С"]])
            write_range(ws, 5, 1, [["01.01.2020", date_str]])

            # Row 11: section header
            write_range(ws, 11, 4, [["Отзывы, в штуках"]])

            # Row 12: column headers
            write_range(ws, 12, 3, [["Рейтинг", "5\u2605", "4\u2605", "3\u2605", "2\u2605", "1\u2605"]])

            # Row 13+: data
            data_rows = []
            for nm_id in sorted_nm_ids:
                stats = agg[nm_id]
                avg = round(stats["avg"], 1)
                data_rows.append([
                    cabinet.name,
                    nm_id,
                    avg,
                    stats.get(5, 0),
                    stats.get(4, 0),
                    stats.get(3, 0),
                    stats.get(2, 0),
                    stats.get(1, 0),
                ])

            if data_rows:
                write_range(ws, 13, 1, data_rows)

            # Checkbox for refresh
            set_checkbox(ws, "C1")

            total += len(sorted_nm_ids)
            logger.info("[%s] Written %d nmIDs", cabinet.name, len(sorted_nm_ids))

        finally:
            client.close()

    logger.info("=== sync_wb_feedbacks: done (%d total nmIDs) ===", total)
    return total


def _aggregate_feedbacks(feedbacks: list[dict]) -> dict:
    """Aggregate feedbacks by nmId -> {1: count, ..., 5: count, avg: float, total: int}.

    Returns dict keyed by nmId (int).
    """
    by_nm: dict[int, list[int]] = defaultdict(list)

    for fb in feedbacks:
        nm_id = fb.get("nmId") or fb.get("productDetails", {}).get("nmId")
        rating = fb.get("productValuation", 0)
        if nm_id and rating:
            by_nm[nm_id].append(rating)

    result = {}
    for nm_id, ratings in by_nm.items():
        counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in ratings:
            if r in counts:
                counts[r] += 1
        total_count = len(ratings)
        avg = sum(ratings) / total_count if total_count > 0 else 0.0
        result[nm_id] = {**counts, "avg": avg, "total": total_count}

    return result
