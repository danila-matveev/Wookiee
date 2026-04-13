from __future__ import annotations

"""Sync WB search query analytics -> new Google Sheet.

Replicates GAS logic: for each search word (brand, artikul, WW-code),
find how many times it was searched, how many card opens, cart adds, and orders.

Two sub-reports:
1. Search words aggregation (by keyword) -> "Аналитика по запросам"
2. Per-artikul breakdown -> "Аналитика по запросам (поартикульно)"
"""

import logging
import time
from datetime import datetime, timedelta

import httpx

from shared.clients.sheets_client import (
    get_client,
    get_or_create_worksheet,
    write_range,
)
from services.sheets_sync.config import (
    ALL_CABINETS,
    GOOGLE_SA_FILE,
    get_active_spreadsheet_id,
    get_sheet_name,
)

logger = logging.getLogger(__name__)

# --- Constants ---
SHEET_NAME = "Аналитика по запросам"
SHEET_NAME_ARTIKUL = "Аналитика по запросам (поартикульно)"
SHEET_NAME_NMIDS = "nmIds"

WB_SEARCH_API = (
    "https://seller-analytics-api.wildberries.ru"
    "/api/v2/search-report/product/search-texts"
)

# Cabinet display names in nmIds sheet
CABINET_DISPLAY = {
    "ООО": "ООО Вуки",
    "ИП": "ИП Медведева П.В.",
}

# API limits
NMID_BATCH_SIZE = 50  # Max nmIds per API request
SEARCH_LIMIT = {"ООО": 100, "ИП": 30}  # Max search words in response
RATE_LIMIT_PAUSE = 21  # Seconds between API requests (3 req/min)
RATE_LIMIT_ERROR_PAUSE = 60  # Seconds on 429


def sync(start_date: str | None = None, end_date: str | None = None) -> int:
    """Run search query analytics for both sheets.

    Args:
        start_date: Start date DD.MM.YYYY (if None, auto last week).
        end_date: End date DD.MM.YYYY (if None, auto last week).

    Returns total rows written.
    """
    logger.info("=== sync_search_queries: start ===")

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())

    total = 0
    total += _sync_search_words(spreadsheet, start_date, end_date)
    total += _sync_artikul(spreadsheet, start_date, end_date)

    logger.info("=== sync_search_queries: done (%d total) ===", total)
    return total


# ============================================================================
# Report 1: Aggregated by search word
# ============================================================================


def _sync_search_words(spreadsheet, start_date: str | None, end_date: str | None) -> int:
    """Aggregate search analytics by keyword -> 'Аналитика по запросам'."""
    ws = get_or_create_worksheet(spreadsheet, get_sheet_name(SHEET_NAME))

    # Resolve dates
    api_start, api_end, display_start, display_end = _resolve_dates(
        ws, start_date, end_date
    )
    if not api_start or not api_end:
        logger.error("Could not resolve dates for search words")
        return 0

    logger.info("Search words period: %s - %s", display_start, display_end)

    # Load search words from column A (A3+)
    col_a = ws.col_values(1)
    search_words: list[str] = []
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

    # Load mapping (search word -> main artikul nmId) from columns A:B
    all_values = ws.get_all_values()
    podmen_mapping = _load_podmen_mapping(all_values)
    logger.info("Loaded %d mapping entries for transition filtering", len(podmen_mapping))

    # Load all nmIds by cabinet from "nmIds" sheet
    ws_nmids = get_or_create_worksheet(spreadsheet, get_sheet_name(SHEET_NAME_NMIDS))
    cabinet_nmids = _load_nmids_by_cabinet(ws_nmids)

    # Analyze each cabinet
    combined: dict[str, dict] = {}
    first_cabinet = True

    for cabinet in ALL_CABINETS:
        display_name = CABINET_DISPLAY.get(cabinet.name, cabinet.name)
        nmids = cabinet_nmids.get(display_name, [])

        if not nmids:
            logger.info("[%s] No nmIds found, skipping", cabinet.name)
            continue

        if not first_cabinet:
            logger.info("Pause 1s between cabinets")
            time.sleep(1)
        first_cabinet = False

        limit = SEARCH_LIMIT.get(cabinet.name, 30)
        results = _analyze_cabinet(
            cabinet.wb_api_key,
            cabinet.name,
            api_start,
            api_end,
            limit,
            nmids,
            search_words,
            podmen_mapping,
        )

        # Merge into combined
        for word, data in results.items():
            if word not in combined:
                combined[word] = {
                    "frequency": 0,
                    "openCard": 0,
                    "addToCart": 0,
                    "orders": 0,
                }
            combined[word]["frequency"] += data["frequency"]
            combined[word]["openCard"] += data["openCard"]
            combined[word]["addToCart"] += data["addToCart"]
            combined[word]["orders"] += data["orders"]

    # Find first empty column pair
    row1 = ws.row_values(1) if ws.row_count >= 1 else []
    row2 = ws.row_values(2) if ws.row_count >= 2 else []
    start_col = max(len(row1), len(row2)) + 1

    # Write headers at row 1
    headers = [["Частота", "Переходы", "Добавления", "Заказы"]]
    write_range(ws, start_row=1, start_col=start_col, data=headers)

    # Write dates at row 2
    dates_row = [[display_start, display_end, "", ""]]
    write_range(ws, start_row=2, start_col=start_col, data=dates_row)

    # Write data starting at row 3
    last_data_row = max(row_map.values()) if row_map else 2
    data_rows: list[list] = []
    for row_num in range(3, last_data_row + 1):
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

    logger.info(
        "Search words: wrote %d rows in columns %d-%d",
        len(data_rows),
        start_col,
        start_col + 3,
    )
    return len(data_rows)


# ============================================================================
# Report 2: Per-artikul breakdown
# ============================================================================


def _sync_artikul(spreadsheet, start_date: str | None, end_date: str | None) -> int:
    """Per-artikul breakdown -> 'Аналитика по запросам (поартикульно)'."""
    ws = get_or_create_worksheet(
        spreadsheet, get_sheet_name(SHEET_NAME_ARTIKUL)
    )

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
        ws.batch_clear([f"A4:M{last_row}"])

    # Load search words from main sheet to filter results
    ws_main = get_or_create_worksheet(spreadsheet, get_sheet_name(SHEET_NAME))
    col_a = ws_main.col_values(1)
    search_words_lower: set[str] = set()
    for val in col_a[2:]:  # Skip rows 1-2
        word = str(val).strip()
        if word:
            search_words_lower.add(word.lower())

    logger.info("Artikul filter: %d search words loaded", len(search_words_lower))

    # Fetch from both cabinets using all nmIds
    ws_nmids = get_or_create_worksheet(
        spreadsheet, get_sheet_name(SHEET_NAME_NMIDS)
    )
    cabinet_nmids = _load_nmids_by_cabinet(ws_nmids)

    all_results: list[list] = []
    first_cabinet = True

    for cabinet in ALL_CABINETS:
        display_name = CABINET_DISPLAY.get(cabinet.name, cabinet.name)
        nmids = cabinet_nmids.get(display_name, [])
        if not nmids:
            continue

        if not first_cabinet:
            time.sleep(1)
        first_cabinet = False

        limit = SEARCH_LIMIT.get(cabinet.name, 30)
        chunks = _chunk_list(nmids, NMID_BATCH_SIZE)

        for chunk_idx, chunk in enumerate(chunks):
            if chunk_idx > 0:
                logger.info("Rate limit pause %ds...", RATE_LIMIT_PAUSE)
                time.sleep(RATE_LIMIT_PAUSE)

            items = _fetch_search_data(
                cabinet.wb_api_key, cabinet.name, api_start, api_end, limit, chunk
            )

            for item in items:
                text = item.get("text", "")
                # Only keep items matching our tracked search words
                if not any(sw in text.lower() for sw in search_words_lower):
                    continue

                open_card = item.get("openCard", 0)
                add_to_cart = item.get("addToCart", 0)
                orders = item.get("orders", 0)
                open_to_cart = add_to_cart / open_card if open_card > 0 else 0
                cart_to_order = orders / add_to_cart if add_to_cart > 0 else 0

                all_results.append([
                    text,
                    item.get("nmId", 0),
                    open_card,
                    add_to_cart,
                    round(open_to_cart, 4),
                    orders,
                    round(cart_to_order, 4),
                    display_start,
                    display_end,
                    cabinet.name,
                ])

    if not all_results:
        logger.warning("No artikul analytics data")
        return 0

    write_range(ws, start_row=4, start_col=1, data=all_results)
    logger.info("Artikul analytics: wrote %d rows", len(all_results))
    return len(all_results)


# ============================================================================
# Core: cabinet analysis with batching
# ============================================================================


def _analyze_cabinet(
    api_key: str,
    cabinet_name: str,
    api_start: str,
    api_end: str,
    limit: int,
    nmids: list[int],
    search_words: list[str],
    podmen_mapping: dict,
) -> dict[str, dict]:
    """Fetch search data for a cabinet in batches and aggregate by search words."""
    logger.info(
        "[%s] Analyzing %d nmIds in batches of %d",
        cabinet_name,
        len(nmids),
        NMID_BATCH_SIZE,
    )

    chunks = _chunk_list(nmids, NMID_BATCH_SIZE)
    aggregated: dict[str, dict] = {}
    successful = 0

    for chunk_idx, chunk in enumerate(chunks):
        logger.info(
            "[%s] Batch %d/%d (%d nmIds)",
            cabinet_name,
            chunk_idx + 1,
            len(chunks),
            len(chunk),
        )

        if chunk_idx > 0:
            logger.info("Rate limit pause %ds...", RATE_LIMIT_PAUSE)
            time.sleep(RATE_LIMIT_PAUSE)

        items = _fetch_search_data(
            api_key, cabinet_name, api_start, api_end, limit, chunk
        )

        if not items:
            continue

        successful += 1

        # Analyze this chunk
        for word in search_words:
            word_lower = word.lower()

            for item in items:
                text = item.get("text", "")
                if word_lower not in text.lower():
                    continue

                if word not in aggregated:
                    aggregated[word] = {
                        "frequency": 0,
                        "openCard": 0,
                        "addToCart": 0,
                        "orders": 0,
                    }

                aggregated[word]["frequency"] += item.get("frequency", 0)
                aggregated[word]["addToCart"] += item.get("addToCart", 0)
                aggregated[word]["orders"] += item.get("orders", 0)

                # Filter transitions by mapping
                nm_id = item.get("nmId", 0)
                if _should_count_transitions(word, nm_id, podmen_mapping):
                    aggregated[word]["openCard"] += item.get("openCard", 0)

    logger.info(
        "[%s] Done: %d/%d batches successful, %d words matched",
        cabinet_name,
        successful,
        len(chunks),
        len(aggregated),
    )
    return aggregated


# ============================================================================
# API client
# ============================================================================


def _fetch_search_data(
    api_key: str,
    cabinet_name: str,
    api_start: str,
    api_end: str,
    limit: int,
    nmids: list[int],
    _retry_depth: int = 0,
) -> list[dict]:
    """POST to WB search-texts API with specific nmIds."""
    payload = {
        "currentPeriod": {"start": api_start, "end": api_end},
        "nmIds": nmids,
        "topOrderBy": "openCard",
        "includeSubstitutedSKUs": True,
        "includeSearchTexts": True,
        "orderBy": {"field": "visibility", "mode": "asc"},
        "limit": limit,
    }

    try:
        with httpx.Client(
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=120.0,
        ) as client:
            resp = client.post(WB_SEARCH_API, json=payload)

        if resp.status_code == 429:
            logger.warning(
                "[%s] Rate limited, pausing %ds...",
                cabinet_name,
                RATE_LIMIT_ERROR_PAUSE,
            )
            time.sleep(RATE_LIMIT_ERROR_PAUSE)
            return []

        if resp.status_code == 403:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                pass

            # Extract bad nmId from error like "Check correctness of nm id: 123456"
            bad_nmid = _extract_bad_nmid(detail)
            if bad_nmid and bad_nmid in nmids and _retry_depth < 10:
                logger.warning(
                    "[%s] nmId %d rejected by API — retrying without it (attempt %d)",
                    cabinet_name,
                    bad_nmid,
                    _retry_depth + 1,
                )
                cleaned = [n for n in nmids if n != bad_nmid]
                if cleaned:
                    # Pause before retry to respect rate limits
                    time.sleep(RATE_LIMIT_PAUSE)
                    return _fetch_search_data(
                        api_key, cabinet_name, api_start, api_end, limit, cleaned,
                        _retry_depth=_retry_depth + 1,
                    )
            logger.warning(
                "[%s] Auth error (403): %s — skipping batch",
                cabinet_name,
                detail[:200],
            )
            return []

        if resp.status_code != 200:
            logger.error(
                "[%s] Search API HTTP %d: %s",
                cabinet_name,
                resp.status_code,
                resp.text[:200],
            )
            return []

        data = resp.json()
        items = data.get("data", {}).get("items", [])
        if not items:
            logger.info("[%s] No search items returned", cabinet_name)
            return []

        # Transform items: extract .current from object metrics
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

        logger.info(
            "[%s] Got %d search items (limit=%d, nmIds=%d)",
            cabinet_name,
            len(result),
            limit,
            len(nmids),
        )
        return result

    except httpx.RequestError as e:
        logger.error("[%s] Search API error: %s", cabinet_name, e)
        return []


def _extract_bad_nmid(detail: str) -> int | None:
    """Extract bad nmId from API 403 error detail string.

    Example: "Check correctness of nm id: 213774563" -> 213774563
    """
    if "nm id:" in detail.lower():
        try:
            return int(detail.rsplit(":", 1)[-1].strip())
        except (ValueError, IndexError):
            pass
    return None


def _extract_metric(item: dict, key: str) -> int:
    """Extract metric value handling both scalar and object forms."""
    val = item.get(key, 0)
    if isinstance(val, dict):
        return int(val.get("current", 0) or 0)
    return int(val or 0)


# ============================================================================
# nmIds loading from sheet
# ============================================================================


def _load_nmids_by_cabinet(ws) -> dict[str, list[int]]:
    """Load nmIds grouped by cabinet name from 'nmIds' sheet.

    Sheet format: A=nmId, B=cabinet name.
    Returns: {cabinet_display_name: [nmId, ...]}
    """
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        logger.warning("nmIds sheet has no data rows")
        return {}

    result: dict[str, list[int]] = {}
    seen: dict[str, set[int]] = {}

    # Header is row 1: "Нуменклатура", "Импортер"
    for row in all_values[1:]:  # Skip header row
        if len(row) < 2:
            continue
        nm_str = str(row[0]).strip()
        cabinet = str(row[1]).strip()
        if not nm_str or not cabinet:
            continue
        try:
            nm_id = int(float(nm_str))
        except (ValueError, TypeError):
            continue

        if cabinet not in result:
            result[cabinet] = []
            seen[cabinet] = set()
        if nm_id not in seen[cabinet]:
            result[cabinet].append(nm_id)
            seen[cabinet].add(nm_id)

    for cab, ids in result.items():
        logger.info("nmIds: %s -> %d items", cab, len(ids))

    return result


# ============================================================================
# Mapping & filtering
# ============================================================================


def _load_podmen_mapping(all_values: list[list]) -> dict:
    """Load search-word to artikul mapping from columns A and B (rows 3+).

    Returns: {search_word: [nmId, ...]} or {search_word: nmId}
    """
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
    """Check if transitions should be counted for this word+nmId combo.

    If the word has a mapping to specific nmIds, only count transitions
    for those nmIds (our own cards, not competitor cards).
    If no mapping exists, count all transitions.
    """
    if word not in mapping:
        return True
    artikuls = mapping[word]
    if not artikuls:
        return True
    return str(nm_id) in artikuls


# ============================================================================
# Date utilities
# ============================================================================


def _resolve_dates(
    ws, start_date: str | None, end_date: str | None
) -> tuple[str | None, str | None, str, str]:
    """Resolve dates from args, sheet A1/B1, or auto (last week)."""
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
    """Return (start_dd_mm, end_dd_mm) for last full week (Mon-Sun)."""
    today = datetime.now()
    day_of_week = today.weekday()  # Monday=0
    last_monday = today - timedelta(days=day_of_week + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.strftime("%d.%m.%Y"), last_sunday.strftime("%d.%m.%Y")


# ============================================================================
# Helpers
# ============================================================================


def _chunk_list(lst: list, size: int) -> list[list]:
    """Split list into chunks of given size."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
