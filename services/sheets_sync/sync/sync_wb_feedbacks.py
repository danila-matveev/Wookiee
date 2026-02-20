from __future__ import annotations

"""Sync WB feedbacks -> sheets 'Отзывы ООО' and 'Отзывы ИП'.

Layout (matching original GAS):
    Row 1:  A1="Дата составления отчёта"  B1=date     C1=[checkbox]
    Row 2:  A2="Время отчёта"             B2=time
    Row 4:  A4="С"                        B4="До"
    Row 5:  A5=start_date                 B5=end_date
    Row 11: D11="Отзывы, в штуках"
    Row 12: C12="Рейтинг" D12="5★" E12="4★" F12="3★" G12="2★" H12="1★"
    Row 13+: A=cabinet B=nmID C=avg_rating D-H=star counts (5->1)
"""

import logging
from collections import defaultdict
from datetime import datetime

from shared.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_moscow_now,
    get_or_create_worksheet,
    set_checkbox,
    write_range,
)
from shared.clients.wb_client import WBClient
from services.sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, get_active_spreadsheet_id, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAMES = {
    "ИП": "Отзывы ИП",
    "ООО": "Отзывы ООО",
}

DEFAULT_START_DATE = "01.01.2020"


def sync(start_date: str | None = None, end_date: str | None = None) -> int:
    """Fetch feedbacks from WB and write rating aggregation to sheets.

    Args:
        start_date: Period start in DD.MM.YYYY format (default: 01.01.2020).
        end_date: Period end in DD.MM.YYYY format (default: today).

    Returns total number of nmIDs processed.
    """
    logger.info("=== sync_wb_feedbacks: start ===")

    now = get_moscow_now()
    date_str, time_str = get_moscow_datetime()

    if not start_date:
        start_date = DEFAULT_START_DATE
    if not end_date:
        end_date = date_str  # today DD.MM.YYYY

    # Parse dates for filtering
    dt_start = _parse_date(start_date)
    dt_end = _parse_date(end_date, end_of_day=True)
    logger.info("Period: %s — %s", start_date, end_date)

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())
    total = 0

    for cabinet in ALL_CABINETS:
        base_sheet = SHEET_NAMES.get(cabinet.name, f"Отзывы {cabinet.name}")
        sheet_name = get_sheet_name(base_sheet)
        ws = get_or_create_worksheet(spreadsheet, sheet_name)

        client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
        try:
            feedbacks = client.get_all_feedbacks()
            logger.info("[%s] Got %d feedbacks", cabinet.name, len(feedbacks))

            # Filter by date range
            filtered = _filter_by_date(feedbacks, dt_start, dt_end)
            logger.info("[%s] After date filter: %d feedbacks", cabinet.name, len(filtered))

            # Aggregate by nmId
            agg = _aggregate_feedbacks(filtered)

            # Sort by total feedback count descending
            sorted_nm_ids = sorted(
                agg.keys(),
                key=lambda nm: agg[nm].get("total", 0),
                reverse=True,
            )

            # Clear entire sheet (old layout may have leftover data in rows 1-4)
            last_row = ws.row_count
            max_col = _col_letter(max(ws.col_count, 8))
            ws.batch_clear([f"A1:{max_col}{last_row}"])

            # Row 1: "Дата составления отчёта" + date
            write_range(ws, 1, 1, [["Дата составления отчёта", date_str]])

            # Row 2: "Время отчёта" + time
            write_range(ws, 2, 1, [["Время отчёта", time_str]])

            # Row 4: "С" / "До" labels
            write_range(ws, 4, 1, [["С", "До"]])

            # Row 5: date range values
            write_range(ws, 5, 1, [[start_date, end_date]])

            # Row 11: section header
            write_range(ws, 11, 4, [["Отзывы, в штуках"]])

            # Row 12: column headers
            write_range(ws, 12, 1, [["Кабинет", "nmID", "Рейтинг", "5\u2605", "4\u2605", "3\u2605", "2\u2605", "1\u2605"]])

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

            # Checkbox for refresh trigger
            set_checkbox(ws, "C1")

            total += len(sorted_nm_ids)
            logger.info("[%s] Written %d nmIDs", cabinet.name, len(sorted_nm_ids))

        finally:
            client.close()

    logger.info("=== sync_wb_feedbacks: done (%d total nmIDs) ===", total)
    return total


def _filter_by_date(feedbacks: list[dict], dt_start: datetime, dt_end: datetime) -> list[dict]:
    """Filter feedbacks by createdDate within [dt_start, dt_end]."""
    result = []
    for fb in feedbacks:
        created = fb.get("createdDate", "")
        if not created:
            continue
        try:
            # WB API returns ISO format: "2024-01-15T12:30:00Z"
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            # Compare as naive datetimes (strip tzinfo)
            dt_naive = dt.replace(tzinfo=None)
            if dt_start <= dt_naive <= dt_end:
                result.append(fb)
        except (ValueError, TypeError):
            result.append(fb)  # include if date can't be parsed
    return result


def _parse_date(date_str: str, end_of_day: bool = False) -> datetime:
    """Parse DD.MM.YYYY to datetime. If end_of_day, set to 23:59:59."""
    try:
        dt = datetime.strptime(date_str.strip(), "%d.%m.%Y")
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt
    except ValueError:
        # Fallback: try other common formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if end_of_day:
                    dt = dt.replace(hour=23, minute=59, second=59)
                return dt
            except ValueError:
                continue
        # If all fail, return a very early date for start or now for end
        if end_of_day:
            return datetime.now()
        return datetime(2020, 1, 1)


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


def _col_letter(col: int) -> str:
    """Convert column number to letter(s). E.g. 1->A, 27->AA."""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result
