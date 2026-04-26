"""WB Promocodes weekly analytics sync — pivot layout.

Pulls reportDetailByPeriod v5 for both cabinets, aggregates by uuid_promocode,
joins with a manually maintained dictionary sheet, and writes into a pivot
table where rows = promo codes and columns = weeks.
"""
from __future__ import annotations

from datetime import date, timedelta


def last_closed_iso_week(today: date | None = None) -> tuple[date, date]:
    """Return (Mon, Sun) of the most recent fully-closed ISO week."""
    today = today or date.today()
    monday_this_week = today - timedelta(days=today.weekday())
    last_mon = monday_this_week - timedelta(days=7)
    last_sun = last_mon + timedelta(days=6)
    return last_mon, last_sun


def iso_weeks_back(n: int, today: date | None = None) -> list[tuple[date, date]]:
    """Return n most recent fully-closed ISO weeks, newest first."""
    last_mon, last_sun = last_closed_iso_week(today=today)
    weeks: list[tuple[date, date]] = []
    for i in range(n):
        mon = last_mon - timedelta(days=7 * i)
        sun = last_sun - timedelta(days=7 * i)
        weeks.append((mon, sun))
    return weeks


from collections import defaultdict


def aggregate_by_uuid(rows: list[dict]) -> dict[str, dict]:
    """Group reportDetailByPeriod rows by uuid_promocode.

    Skips rows where uuid_promocode is empty/0/None. Returns:
        {uuid: {
            'sales_rub': float,
            'ppvz_rub': float,
            'orders_count': int,
            'returns_count': int,
            'avg_discount_pct': float,
            'top3_models': list[tuple[str, float]],
        }}
    """
    buckets: dict[str, dict] = defaultdict(lambda: {
        "sales_rub": 0.0,
        "ppvz_rub": 0.0,
        "orders_count": 0,
        "returns_count": 0,
        "_disc_sum": 0.0,
        "_disc_n": 0,
        "_models": defaultdict(float),
    })

    for row in rows:
        uuid = row.get("uuid_promocode")
        if not uuid:
            continue
        pid = str(uuid).strip()
        if not pid:
            continue

        doc = (row.get("doc_type_name") or "").strip()
        qty = int(row.get("quantity") or 0)
        retail = float(row.get("retail_amount") or 0.0)
        ppvz = float(row.get("ppvz_for_pay") or 0.0)
        sa = (row.get("sa_name") or "").strip().lower()

        b = buckets[pid]

        if doc == "Продажа":
            b["sales_rub"] += retail
            b["ppvz_rub"] += ppvz
            b["orders_count"] += qty or 1
            if sa:
                b["_models"][sa] += retail
        elif doc in ("Возврат", "Корректный возврат"):
            b["returns_count"] += qty or 1

        d = row.get("sale_price_promocode_discount_prc")
        if d is not None and d != "":
            try:
                b["_disc_sum"] += float(d)
                b["_disc_n"] += 1
            except (TypeError, ValueError):
                pass

    out: dict[str, dict] = {}
    for pid, b in buckets.items():
        avg_d = (b["_disc_sum"] / b["_disc_n"]) if b["_disc_n"] else 0.0
        top3 = sorted(b["_models"].items(), key=lambda kv: kv[1], reverse=True)[:3]
        out[pid] = {
            "sales_rub": b["sales_rub"],
            "ppvz_rub": b["ppvz_rub"],
            "orders_count": b["orders_count"],
            "returns_count": b["returns_count"],
            "avg_discount_pct": avg_d,
            "top3_models": top3,
        }
    return out


def parse_dictionary(raw_rows: list[list[str]]) -> dict[str, dict]:
    """Parse the справочник sheet into {uuid_lower: {name, channel, discount_pct, ...}}.

    Expects header in row 0; rows with empty UUID are dropped.
    """
    if not raw_rows or len(raw_rows) < 2:
        return {}
    out: dict[str, dict] = {}
    for row in raw_rows[1:]:
        cells = (row + [""] * 7)[:7]
        uuid_raw, name, channel, disc, start, end, note = cells
        uuid = (uuid_raw or "").strip().lower()
        if not uuid:
            continue
        try:
            disc_pct = float(disc) if disc not in ("", None) else None
        except ValueError:
            disc_pct = None
        out[uuid] = {
            "name": (name or "").strip(),
            "channel": (channel or "").strip(),
            "discount_pct": disc_pct,
            "start": (start or "").strip(),
            "end": (end or "").strip(),
            "note": (note or "").strip(),
        }
    return out


# ── Legacy flat-format helpers (kept for test compatibility) ─────────────────

ANALYTICS_HEADERS = [
    "Неделя", "Кабинет", "Название", "UUID", "Скидка %",
    "Продажи (retail), ₽", "К перечислению, ₽",
    "Заказов, шт", "Возвратов, шт", "Ср. чек, ₽",
    "Топ-3 модели", "Обновлено",
]


def format_analytics_row(
    week_start: date, week_end: date, cabinet: str, uuid: str,
    metrics: dict, dictionary: dict[str, dict], updated_at_iso: str,
) -> list:
    """Build one flat-format row (legacy, not used by pivot run())."""
    info = dictionary.get(uuid.lower(), {})
    name = info.get("name") or "неизвестный"
    discount = info.get("discount_pct")
    if discount is None:
        discount = round(metrics.get("avg_discount_pct", 0.0), 2)
    avg_check = (
        round(metrics["sales_rub"] / metrics["orders_count"], 2)
        if metrics["orders_count"] else 0.0
    )
    top3_str = ", ".join(
        f"{m} ({v:,.0f}₽)".replace(",", " ")
        for m, v in metrics.get("top3_models", [])
    ) or "—"
    week_label = f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"
    return [
        week_label, cabinet, name, uuid, discount,
        round(metrics["sales_rub"], 2), round(metrics["ppvz_rub"], 2),
        metrics["orders_count"], metrics["returns_count"], avg_check,
        top3_str, updated_at_iso,
    ]


def compute_dashboard_summary(
    week_aggs: dict[str, dict], dictionary: dict[str, dict]
) -> dict:
    """Return dashboard metrics for the most recent week (across both cabinets)."""
    if not week_aggs:
        return {
            "promocodes_count": 0,
            "sales_total": 0,
            "orders_total": 0,
            "champion_name": "—",
            "champion_sales": 0,
            "unknown_uuids": [],
        }

    sales_total = sum(b["sales_rub"] for b in week_aggs.values())
    orders_total = sum(b["orders_count"] for b in week_aggs.values())
    champion_uuid, champion = max(
        week_aggs.items(), key=lambda kv: kv[1]["sales_rub"]
    )
    champion_name = (
        dictionary.get(champion_uuid.lower(), {}).get("name") or "неизвестный"
    )
    unknown = sorted(uuid for uuid in week_aggs if uuid.lower() not in dictionary)
    return {
        "promocodes_count": len(week_aggs),
        "sales_total": round(sales_total, 2),
        "orders_total": orders_total,
        "champion_name": champion_name,
        "champion_sales": round(champion["sales_rub"], 2),
        "unknown_uuids": unknown,
    }


import logging
import time

import httpx

logger = logging.getLogger(__name__)

WB_REPORT_URL = (
    "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
)
PAGE_LIMIT = 50000
RATE_LIMIT_SLEEP = 62
MAX_RETRIES = 5


def fetch_report(api_key: str, cabinet_name: str,
                 date_from: date, date_to: date) -> list[dict]:
    """Paginate reportDetailByPeriod for [date_from, date_to] inclusive."""
    logger.info("[%s] Fetching %s → %s", cabinet_name, date_from, date_to)
    all_rows: list[dict] = []
    rrd_id = 0
    page = 0
    with httpx.Client(timeout=300.0) as client:
        while True:
            page += 1
            params = {
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
                "limit": PAGE_LIMIT,
                "rrdid": rrd_id,
            }
            data = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = client.get(
                        WB_REPORT_URL, params=params,
                        headers={"Authorization": api_key},
                    )
                    if resp.status_code == 429:
                        logger.warning("[%s] 429, sleep %ss",
                                       cabinet_name, RATE_LIMIT_SLEEP)
                        time.sleep(RATE_LIMIT_SLEEP)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except Exception as e:
                    wait = 15 * attempt
                    logger.warning(
                        "[%s] page %d attempt %d: %s (retry in %ss)",
                        cabinet_name, page, attempt, e, wait,
                    )
                    time.sleep(wait)
            if data is None:
                logger.error("[%s] page %d failed after retries", cabinet_name, page)
                break
            if not data:
                break
            all_rows.extend(data)
            rrd_id = data[-1].get("rrd_id", 0)
            logger.info("[%s] page %d: %d rows (total=%d)",
                        cabinet_name, page, len(data), len(all_rows))
            if len(data) < PAGE_LIMIT:
                break
            time.sleep(RATE_LIMIT_SLEEP)
    logger.info("[%s] total: %d rows", cabinet_name, len(all_rows))
    return all_rows


import os

import gspread

from shared.clients.sheets_client import (
    get_client,
    get_or_create_worksheet,
)

# ── Pivot layout constants ────────────────────────────────────────────────────

DASHBOARD_HEADER_ROWS = 8   # rows 1-8: dashboard + GAS button
WEEK_LABELS_ROW = 9         # merged week date labels (e.g. "06.04–12.04.2026")
METRIC_HEADERS_ROW = 10     # metric column names per week + fixed column names
DATA_START_ROW = 11         # data rows start here

FIXED_HEADERS = ["Название", "UUID", "Канал", "Скидка %"]
FIXED_NCOLS = len(FIXED_HEADERS)  # 4  (cols A-D)

WEEK_METRICS = [
    "Продажи, ₽", "К перечислению, ₽",
    "Заказов, шт", "Возвратов, шт", "Ср. чек, ₽", "Топ модель",
]
WEEK_NCOLS = len(WEEK_METRICS)  # 6

DEFAULT_DICT_SHEET = "Промокоды_справочник"
DEFAULT_DATA_SHEET = "Промокоды_аналитика"


def _week_label(week_start: date, week_end: date) -> str:
    return f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"


def _col_letter(col: int) -> str:
    """Convert 1-based column number to spreadsheet letter (A, B, ..., AA, ...)."""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _clear_conditional_formats(ws: gspread.Worksheet) -> None:
    for _ in range(10):
        try:
            ws.spreadsheet.batch_update({
                "requests": [
                    {"deleteConditionalFormatRule": {"sheetId": ws.id, "index": 0}}
                ]
            })
        except Exception:
            break


def _read_pivot_state(
    ws: gspread.Worksheet,
) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """Read current pivot state from the sheet.

    Returns:
        week_col_map:  {week_label: first_metric_col_1based}
        uuid_row_map:  {(uuid, cabinet): row_number_1based}
    """
    all_vals = ws.get_all_values()

    week_col_map: dict[str, int] = {}
    if len(all_vals) >= WEEK_LABELS_ROW:
        week_row = all_vals[WEEK_LABELS_ROW - 1]
        for i in range(FIXED_NCOLS, len(week_row)):
            val = (week_row[i] or "").strip()
            if val and val not in week_col_map:
                week_col_map[val] = i + 1  # 1-based

    uuid_row_map: dict[tuple[str, str], int] = {}
    for row_0 in range(DATA_START_ROW - 1, len(all_vals)):
        row = all_vals[row_0]
        uuid = (row[1] if len(row) > 1 else "").strip()
        cabinet = (row[2] if len(row) > 2 else "").strip()
        if uuid:
            key = (uuid, cabinet)
            if key not in uuid_row_map:
                uuid_row_map[key] = row_0 + 1  # 1-based

    return week_col_map, uuid_row_map


def _add_week_to_sheet(ws: gspread.Worksheet, week_label: str, first_col: int) -> None:
    """Write week date label (row 9) and metric names (row 10) for a new week block."""
    col_start = _col_letter(first_col)
    col_end = _col_letter(first_col + WEEK_NCOLS - 1)

    ws.update(
        range_name=f"{col_start}{WEEK_LABELS_ROW}:{col_end}{WEEK_LABELS_ROW}",
        values=[[week_label] + [""] * (WEEK_NCOLS - 1)],
    )
    ws.update(
        range_name=f"{col_start}{METRIC_HEADERS_ROW}:{col_end}{METRIC_HEADERS_ROW}",
        values=[WEEK_METRICS],
    )
    try:
        from services.sheets_sync.sync.format_promocodes_sheet import format_week_columns
        format_week_columns(ws, first_col)
    except Exception as e:
        logger.warning("Week column formatting failed (data still written): %s", e)


def upsert_pivot(
    ws: gspread.Worksheet,
    week_start: date,
    week_end: date,
    week_data: dict[tuple[str, str], dict],
    week_col_map: dict[str, int],
    uuid_row_map: dict[tuple[str, str], int],
) -> tuple[int, int]:
    """Write week data into the pivot table. Mutates week_col_map and uuid_row_map.

    week_data key: (uuid, cabinet)
    week_data value: {metrics, name, channel, discount}

    Returns (rows_added, rows_updated).
    """
    label = _week_label(week_start, week_end)

    if label not in week_col_map:
        n_existing = len(week_col_map)
        first_col = FIXED_NCOLS + 1 + n_existing * WEEK_NCOLS
        _add_week_to_sheet(ws, label, first_col)
        week_col_map[label] = first_col

    week_first_col = week_col_map[label]
    cells: list[gspread.Cell] = []
    added = updated = 0

    for (uuid, cabinet), row_data in week_data.items():
        key = (uuid, cabinet)
        if key in uuid_row_map:
            row_n = uuid_row_map[key]
            updated += 1
        else:
            row_n = DATA_START_ROW + len(uuid_row_map)
            uuid_row_map[key] = row_n
            added += 1
            cells.append(gspread.Cell(row_n, 1, row_data["name"]))
            cells.append(gspread.Cell(row_n, 2, uuid))
            cells.append(gspread.Cell(row_n, 3, cabinet))
            cells.append(gspread.Cell(row_n, 4, row_data["discount"]))

        m = row_data["metrics"]
        avg_check = (
            round(m["sales_rub"] / m["orders_count"], 2)
            if m["orders_count"] else 0.0
        )
        top1 = m["top3_models"][0][0] if m.get("top3_models") else "—"
        metric_vals = [
            round(m["sales_rub"], 2),
            round(m["ppvz_rub"], 2),
            m["orders_count"],
            m["returns_count"],
            avg_check,
            top1,
        ]
        for i, val in enumerate(metric_vals):
            cells.append(gspread.Cell(row_n, week_first_col + i, val))

    if cells:
        ws.update_cells(cells, value_input_option="USER_ENTERED")

    logger.info("Pivot upsert %s: +%d, ~%d", label, added, updated)
    return added, updated


def _open_spreadsheet():
    sa_file = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "services/sheets_sync/credentials/google_sa.json",
    )
    sid = os.getenv("PROMOCODES_SPREADSHEET_ID", "")
    if not sid:
        raise RuntimeError("PROMOCODES_SPREADSHEET_ID is not set")
    gc = get_client(sa_file)
    return gc.open_by_key(sid)


def read_dictionary_sheet() -> dict[str, dict]:
    """Open spreadsheet and parse the dictionary sheet."""
    sheet_name = os.getenv("PROMOCODES_DICT_SHEET", DEFAULT_DICT_SHEET)
    ss = _open_spreadsheet()
    try:
        ws = ss.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        logger.warning("Dictionary sheet '%s' not found — empty mapping", sheet_name)
        return {}
    return parse_dictionary(ws.get_all_values())


def ensure_analytics_sheet() -> gspread.Worksheet:
    """Ensure analytics sheet exists in pivot layout with fixed column headers."""
    sheet_name = os.getenv("PROMOCODES_DATA_SHEET", DEFAULT_DATA_SHEET)
    ss = _open_spreadsheet()
    ws = get_or_create_worksheet(ss, sheet_name, rows=2000, cols=200)

    # get_or_create_worksheet only sets cols at creation; existing sheets keep original count
    if getattr(ws, "col_count", 0) < 200:
        ws.resize(rows=2000, cols=200)

    current_row10 = ws.row_values(METRIC_HEADERS_ROW)
    needs_init = current_row10[:FIXED_NCOLS] != FIXED_HEADERS

    if needs_init:
        logger.info("Initialising pivot sheet (clearing old data)...")
        ws.clear()
        ws.resize(rows=2000, cols=200)
        _clear_conditional_formats(ws)

        end_col = _col_letter(FIXED_NCOLS)
        ws.update(
            range_name=f"A{METRIC_HEADERS_ROW}:{end_col}{METRIC_HEADERS_ROW}",
            values=[FIXED_HEADERS],
        )
        try:
            from services.sheets_sync.sync.format_promocodes_sheet import apply_base_formatting
            apply_base_formatting(ws)
        except Exception as e:
            logger.warning("Base formatting failed (sheet still usable): %s", e)

    return ws


from shared.clients.sheets_client import get_moscow_now


def write_dashboard_header(
    ws: gspread.Worksheet,
    summary: dict,
    weeks_processed: list[tuple[date, date]],
) -> None:
    """Render dashboard rows 2-7 with timestamp, status, and last-week metrics."""
    now_str = get_moscow_now().strftime("%Y-%m-%d %H:%M:%S МСК")
    weeks_label = "—" if not weeks_processed else (
        f"{weeks_processed[-1][0].strftime('%d.%m')}–"
        f"{weeks_processed[0][1].strftime('%d.%m')}"
    )
    status_line = (
        f"✅ {len(weeks_processed)} нед. ({weeks_label}), пропусков нет"
        if weeks_processed else "⚠️ Нет данных"
    )
    unknown_n = len(summary.get("unknown_uuids", []))
    unknown_line = (
        f"{unknown_n} (см. жёлтые строки ниже)" if unknown_n else "0 ✓"
    )
    last_week = weeks_processed[0] if weeks_processed else None
    last_week_label = (
        f"{last_week[0].strftime('%d.%m')}–{last_week[1].strftime('%d.%m')}"
        if last_week else "—"
    )
    block = [
        ["Последнее обновление:", now_str, "", "", ""],
        ["Статус полноты:", status_line, "", "", ""],
        ["Неизвестных UUID:", unknown_line, "", "", ""],
        ["", "", "", "", ""],
        [f"── За последнюю неделю ({last_week_label}) ──", "", "", "", ""],
        [
            f"Промокодов: {summary.get('promocodes_count', 0)}  │  "
            f"Продажи: {summary.get('sales_total', 0):,.0f} ₽  │  "
            f"Заказов: {summary.get('orders_total', 0)}  │  "
            f"Чемпион: {summary.get('champion_name', '—')} "
            f"({summary.get('champion_sales', 0):,.0f} ₽)".replace(",", " "),
            "", "", "", "",
        ],
    ]
    ws.update(range_name="A2:E7", values=block, value_input_option="USER_ENTERED")


def _resolve_weeks(mode: str, week_from: date | None, week_to: date | None,
                   weeks_back: int) -> list[tuple[date, date]]:
    if mode == "last_week":
        return [last_closed_iso_week()]
    if mode == "specific":
        if not (week_from and week_to):
            raise ValueError("specific mode requires week_from and week_to")
        return [(week_from, week_to)]
    if mode == "bootstrap":
        return iso_weeks_back(weeks_back)
    raise ValueError(f"Unknown mode: {mode}")


def _cabinets_from_env() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, key_env in (("ИП", "WB_API_KEY_IP"), ("ООО", "WB_API_KEY_OOO")):
        key = os.getenv(key_env, "").strip()
        if key:
            out.append((name, key))
        else:
            logger.warning("Skip cabinet %s — %s not set", name, key_env)
    return out


def run(
    mode: str = "last_week",
    week_from: date | None = None,
    week_to: date | None = None,
    weeks_back: int = 12,
    cabinets: list[tuple[str, str]] | None = None,
) -> dict:
    """Main entry point. Returns status dict."""
    started = get_moscow_now()
    cabs = cabinets or _cabinets_from_env()
    if not cabs:
        return {"status": "error", "error": "No cabinets configured",
                "started_at": started.isoformat(timespec="seconds")}

    weeks = _resolve_weeks(mode, week_from, week_to, weeks_back)
    dictionary = read_dictionary_sheet()
    ws = ensure_analytics_sheet()
    week_col_map, uuid_row_map = _read_pivot_state(ws)

    rows_added = rows_updated = 0
    unknown_set: set[str] = set()
    last_week_aggs: dict[str, dict] = {}

    # Process oldest week first so columns grow left→right chronologically
    for week_start, week_end in reversed(weeks):
        week_data: dict[tuple[str, str], dict] = {}

        for cab_name, api_key in cabs:
            api_rows = fetch_report(api_key, cab_name, week_start, week_end)
            agg = aggregate_by_uuid(api_rows)
            for uuid, m in agg.items():
                if uuid.lower() not in dictionary:
                    unknown_set.add(uuid)
                info = dictionary.get(uuid.lower(), {})
                week_data[(uuid, cab_name)] = {
                    "metrics": m,
                    "name": info.get("name") or "неизвестный",
                    "channel": cab_name,
                    "discount": (
                        info["discount_pct"]
                        if info.get("discount_pct") is not None
                        else round(m["avg_discount_pct"], 2)
                    ),
                }

            # Accumulate latest-week summary (weeks[0] is the most recent)
            if (week_start, week_end) == weeks[0]:
                for uuid, m in agg.items():
                    if uuid not in last_week_aggs:
                        last_week_aggs[uuid] = dict(m)
                    else:
                        last_week_aggs[uuid]["sales_rub"] += m["sales_rub"]
                        last_week_aggs[uuid]["orders_count"] += m["orders_count"]

        a, u = upsert_pivot(ws, week_start, week_end, week_data,
                            week_col_map, uuid_row_map)
        rows_added += a
        rows_updated += u

    summary = compute_dashboard_summary(last_week_aggs, dictionary)
    write_dashboard_header(ws, summary, weeks)

    finished = get_moscow_now()
    return {
        "status": "ok",
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "weeks_processed": [(s.isoformat(), e.isoformat()) for s, e in weeks],
        "cabinets": [c[0] for c in cabs],
        "rows_added": rows_added,
        "rows_updated": rows_updated,
        "unknown_uuids": sorted(unknown_set),
    }
