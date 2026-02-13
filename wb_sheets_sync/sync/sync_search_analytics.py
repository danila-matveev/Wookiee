from __future__ import annotations

"""Sync WB search analytics -> sheet 'Аналитика по запросам'.

Two sub-reports:
1. Search words aggregation (by keyword) -> "Аналитика по запросам"
2. Per-artikul breakdown -> "Аналитика по запросам (поартикульно)"
"""

import logging
from datetime import datetime, timedelta

import httpx

from wb_sheets_sync.clients.sheets_client import (
    get_client,
    get_or_create_worksheet,
    write_range,
)
from wb_sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, SPREADSHEET_ID, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "Аналитика по запросам"
SHEET_NAME_ARTIKUL = "Аналитика по запросам (поартикульно)"

WB_SEARCH_API = "https://seller-analytics-api.wildberries.ru/api/v2/search-report/product/search-texts"

LIMIT_CONFIG = {
    "ООО": 100,
    "ИП": 30,
}


def sync(start_date: str | None = None, end_date: str | None = None) -> int:
    """Run search analytics for both sheets.

    Args:
        start_date: Start date DD.MM.YYYY (if None, reads from sheet A1 or auto last week).
        end_date: End date DD.MM.YYYY (if None, reads from sheet B1 or auto last week).

    Returns total rows written.
    """
    logger.info("=== sync_search_analytics: start ===")

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    total = 0
    total += _sync_search_words(spreadsheet, start_date, end_date)
    total += _sync_artikul(spreadsheet, start_date, end_date)

    logger.info("=== sync_search_analytics: done (%d total) ===", total)
    return total


def _sync_search_words(spreadsheet, start_date: str | None, end_date: str | None) -> int:
    """Aggregate search analytics by keyword -> 'Аналитика по запросам'."""
    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    # Resolve dates
    api_start, api_end, display_start, display_end = _resolve_dates(ws, start_date, end_date)
    if not api_start or not api_end:
        logger.error("Could not resolve dates for search words")
        return 0

    logger.info("Search words period: %s - %s", display_start, display_end)

    # Load search words from column A (A3+)
    col_a = ws.col_values(1)
    search_words = []
    row_map: dict[str, int] = {}
    for i, val in enumerate(col_a[2:], start=3):  # Skip rows 1-2
        word = str(val).strip()
        if word:
            search_words.append(word)
            row_map[word] = i

    if not search_words:
        logger.warning("No search words found in column A")
        return 0

    logger.info("Found %d search words", len(search_words))

    # Load mapping from columns A and B (A3:B) for transition filtering
    all_values = ws.get_all_values()
    mapping = _load_podmen_mapping(all_values)

    # Fetch data from both cabinets
    ooo_results = _analyze_cabinet_search_words(
        "ООО", api_start, api_end, search_words, mapping
    )
    ip_results = _analyze_cabinet_search_words(
        "ИП", api_start, api_end, search_words, mapping
    )

    # Combine results
    combined = {}
    for word in search_words:
        ooo = ooo_results.get(word, {})
        ip = ip_results.get(word, {})
        combined[word] = {
            "frequency": ooo.get("frequency", 0) + ip.get("frequency", 0),
            "openCard": ooo.get("openCard", 0) + ip.get("openCard", 0),
            "addToCart": ooo.get("addToCart", 0) + ip.get("addToCart", 0),
            "orders": ooo.get("orders", 0) + ip.get("orders", 0),
        }

    # Find first empty column
    last_col = ws.col_count
    row2 = ws.row_values(2) if ws.row_count >= 2 else []
    start_col = len(row2) + 1
    # Also check row 1 in case row 2 is shorter
    row1 = ws.row_values(1) if ws.row_count >= 1 else []
    start_col = max(start_col, len(row1) + 1)

    # Write headers at row 1 and dates at row 2
    headers = [["Частота", "Переходы", "Добавления", "Заказы"]]
    write_range(ws, start_row=1, start_col=start_col, data=headers)

    dates_row = [[display_start, display_end, "", ""]]
    write_range(ws, start_row=2, start_col=start_col, data=dates_row)

    # Write data starting at row 3
    last_data_row = max(row_map.values()) if row_map else 2
    data_rows = []
    for row_num in range(3, last_data_row + 1):
        # Find word for this row
        found = False
        for word, r in row_map.items():
            if r == row_num:
                d = combined.get(word, {})
                data_rows.append([
                    d.get("frequency", 0),
                    d.get("openCard", 0),
                    d.get("addToCart", 0),
                    d.get("orders", 0),
                ])
                found = True
                break
        if not found:
            data_rows.append(["", "", "", ""])

    if data_rows:
        write_range(ws, start_row=3, start_col=start_col, data=data_rows)

    logger.info("Search words: wrote %d rows in columns %d-%d", len(data_rows), start_col, start_col + 3)
    return len(data_rows)


def _sync_artikul(spreadsheet, start_date: str | None, end_date: str | None) -> int:
    """Per-artikul breakdown -> 'Аналитика по запросам (поартикульно)'."""
    sheet_name = get_sheet_name(SHEET_NAME_ARTIKUL)
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    # Resolve dates from A2/B2
    a2 = ""
    b2 = ""
    try:
        a2 = ws.acell("A2").value or ""
        b2 = ws.acell("B2").value or ""
    except Exception:
        pass

    if start_date:
        display_start = start_date
    elif a2:
        display_start = a2.strip()
    else:
        display_start, _ = _auto_last_week()
        display_start = display_start

    if end_date:
        display_end = end_date
    elif b2:
        display_end = b2.strip()
    else:
        _, display_end = _auto_last_week()

    api_start = _dd_mm_to_api(display_start)
    api_end = _dd_mm_to_api(display_end)

    if not api_start or not api_end:
        logger.error("Could not resolve dates for artikul analytics")
        return 0

    logger.info("Artikul analytics period: %s - %s", display_start, display_end)

    # Clear old data from row 4
    last_row = ws.row_count
    if last_row >= 4:
        ws.batch_clear([f"A4:J{last_row}"])

    # Fetch from both cabinets
    all_results = []
    for cabinet in ALL_CABINETS:
        limit = LIMIT_CONFIG.get(cabinet.name, 30)
        items = _fetch_search_data(cabinet.wb_api_key, cabinet.name, api_start, api_end, limit)
        for item in items:
            open_card = item.get("openCard", 0)
            add_to_cart = item.get("addToCart", 0)
            orders = item.get("orders", 0)
            open_to_cart = add_to_cart / open_card if open_card > 0 else 0
            cart_to_order = orders / add_to_cart if add_to_cart > 0 else 0

            all_results.append([
                item.get("text", ""),
                item.get("nmId", 0),
                open_card,
                add_to_cart,
                open_to_cart,
                orders,
                cart_to_order,
                display_start,
                display_end,
                cabinet.name,
            ])

    if not all_results:
        logger.warning("No artikul analytics data")
        return 0

    # Write data starting at row 4
    write_range(ws, start_row=4, start_col=1, data=all_results)
    logger.info("Artikul analytics: wrote %d rows", len(all_results))
    return len(all_results)


def _analyze_cabinet_search_words(
    cabinet_name: str,
    api_start: str,
    api_end: str,
    search_words: list[str],
    mapping: dict,
) -> dict:
    """Fetch search data for a cabinet and aggregate by search words."""
    cabinet = None
    for c in ALL_CABINETS:
        if c.name == cabinet_name:
            cabinet = c
            break

    if not cabinet:
        return {}

    limit = LIMIT_CONFIG.get(cabinet_name, 30)
    items = _fetch_search_data(cabinet.wb_api_key, cabinet_name, api_start, api_end, limit)

    if not items:
        return {}

    results: dict[str, dict] = {}
    for word in search_words:
        word_lower = word.lower()
        freq_total = 0
        open_total = 0
        cart_total = 0
        orders_total = 0

        for item in items:
            text = item.get("text", "")
            if word_lower in text.lower():
                freq_total += item.get("frequency", 0)
                cart_total += item.get("addToCart", 0)
                orders_total += item.get("orders", 0)

                # Filter transitions by mapping
                nm_id = item.get("nmId", 0)
                if _should_count_transitions(word, nm_id, mapping):
                    open_total += item.get("openCard", 0)

        if freq_total or open_total or cart_total or orders_total:
            results[word] = {
                "frequency": freq_total,
                "openCard": open_total,
                "addToCart": cart_total,
                "orders": orders_total,
            }

    return results


def _fetch_search_data(
    api_key: str, cabinet_name: str, api_start: str, api_end: str, limit: int
) -> list[dict]:
    """POST to WB search-texts API."""
    payload = {
        "currentPeriod": {"start": api_start, "end": api_end},
        "nmIds": [],
        "topOrderBy": "openCard",
        "includeSubstitutedSKUs": True,
        "includeSearchTexts": True,
        "orderBy": {"field": "visibility", "mode": "asc"},
        "limit": limit,
    }

    try:
        with httpx.Client(
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=120.0,
        ) as client:
            resp = client.post(WB_SEARCH_API, json=payload)

        if resp.status_code != 200:
            logger.error("[%s] Search API HTTP %d: %s", cabinet_name, resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        items = data.get("data", {}).get("items", [])
        if not items:
            logger.info("[%s] No search items returned", cabinet_name)
            return []

        # Transform items
        result = []
        for item in items:
            result.append({
                "text": item.get("text", ""),
                "nmId": item.get("nmId", 0),
                "frequency": _extract_metric(item, "frequency"),
                "openCard": _extract_metric(item, "openCard"),
                "addToCart": _extract_metric(item, "addToCart"),
                "orders": _extract_metric(item, "orders"),
            })

        logger.info("[%s] Got %d search items (limit=%d)", cabinet_name, len(result), limit)
        return result

    except httpx.RequestError as e:
        logger.error("[%s] Search API error: %s", cabinet_name, e)
        return []


def _extract_metric(item: dict, key: str) -> int:
    """Extract metric value handling both scalar and object forms."""
    val = item.get(key, 0)
    if isinstance(val, dict):
        return int(val.get("current", 0) or 0)
    return int(val or 0)


def _load_podmen_mapping(all_values: list[list]) -> dict:
    """Load search-word to artikul mapping from columns A and B (rows 3+)."""
    mapping: dict[str, list] = {}
    for row in all_values[2:]:  # Skip rows 1-2
        if len(row) < 2:
            continue
        word = str(row[0]).strip()
        artikul = row[1]
        if not word:
            continue
        if word not in mapping:
            mapping[word] = []
        if artikul:
            mapping[word].append(str(artikul))
    return mapping


def _should_count_transitions(word: str, nm_id: int, mapping: dict) -> bool:
    """Check if transitions should be counted for this word+nmId combo."""
    if word not in mapping:
        return True
    artikuls = mapping[word]
    if not artikuls:
        return True
    return str(nm_id) in artikuls


def _resolve_dates(ws, start_date: str | None, end_date: str | None):
    """Resolve dates from args, sheet, or auto (last week)."""
    if start_date and end_date:
        display_start = start_date
        display_end = end_date
    else:
        # Try reading from sheet A1/B1
        a1 = ""
        b1 = ""
        try:
            a1 = ws.acell("A1").value or ""
            b1 = ws.acell("B1").value or ""
        except Exception:
            pass

        if a1.strip() and b1.strip():
            display_start = a1.strip()
            display_end = b1.strip()
        else:
            display_start, display_end = _auto_last_week()

    api_start = _dd_mm_to_api(display_start)
    api_end = _dd_mm_to_api(display_end)

    return api_start, api_end, display_start, display_end


def _dd_mm_to_api(date_str: str) -> str | None:
    """Convert DD.MM.YYYY to YYYY-MM-DD."""
    try:
        parts = date_str.strip().split(".")
        if len(parts) != 3:
            return None
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        return None


def _auto_last_week() -> tuple[str, str]:
    """Return (start_dd_mm, end_dd_mm) for last week."""
    today = datetime.now()
    day_of_week = today.weekday()  # Monday=0
    last_monday = today - timedelta(days=day_of_week + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.strftime("%d.%m.%Y"), last_sunday.strftime("%d.%m.%Y")
