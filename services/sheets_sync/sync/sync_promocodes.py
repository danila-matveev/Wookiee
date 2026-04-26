"""WB Promocodes weekly analytics sync.

Pulls reportDetailByPeriod v5 for both cabinets, aggregates by
uuid_promocode, joins with a manually maintained dictionary sheet,
and upserts rows into the analytics sheet (idempotent on
week_start + cabinet + uuid).
"""
from __future__ import annotations

from datetime import date, timedelta


def last_closed_iso_week(today: date | None = None) -> tuple[date, date]:
    """Return (Mon, Sun) of the most recent fully-closed ISO week.

    «Fully closed» means today is at least Monday of the next week,
    so the prior week's Sunday data is final at WB.
    """
    today = today or date.today()
    # Move to today's Monday, then jump back 7 days
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
            'sales_rub': float,         # retail_amount sum, only «Продажа»
            'ppvz_rub': float,          # ppvz_for_pay sum, only «Продажа»
            'orders_count': int,        # sum(quantity) for «Продажа»
            'returns_count': int,       # sum(quantity) for «Возврат»
            'avg_discount_pct': float,  # mean of sale_price_promocode_discount_prc
            'top3_models': list[tuple[str, float]],  # by sales_rub desc
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
        if not uuid:                # "", None, 0
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

    # Finalize
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
        # pad missing cells
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
    """Build one row matching ANALYTICS_HEADERS order."""
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
        week_label,
        cabinet,
        name,
        uuid,
        discount,
        round(metrics["sales_rub"], 2),
        round(metrics["ppvz_rub"], 2),
        metrics["orders_count"],
        metrics["returns_count"],
        avg_check,
        top3_str,
        updated_at_iso,
    ]


def compute_dashboard_summary(
    week_aggs: dict[str, dict], dictionary: dict[str, dict]
) -> dict:
    """Return dashboard metrics for the most recent week (across both cabinets).

    Keys: promocodes_count, sales_total, orders_total,
          champion_name, champion_sales, unknown_uuids.
    """
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

    unknown = sorted(
        uuid for uuid in week_aggs.keys()
        if uuid.lower() not in dictionary
    )
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

DASHBOARD_HEADER_ROWS = 8     # rows 1-8 reserved for dashboard
COLUMN_HEADERS_ROW = 9        # row 9 holds column headers
DATA_START_ROW = 10           # rows 10+ hold data

DEFAULT_DICT_SHEET = "Промокоды_справочник"
DEFAULT_DATA_SHEET = "Промокоды_аналитика"


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
    """Ensure the analytics sheet exists with dashboard rows + column headers.

    On first creation, also applies visual formatting (header colors,
    currency formats, banding, freeze, conditional yellow for unknown).
    """
    sheet_name = os.getenv("PROMOCODES_DATA_SHEET", DEFAULT_DATA_SHEET)
    ss = _open_spreadsheet()
    ws = get_or_create_worksheet(ss, sheet_name, rows=2000, cols=len(ANALYTICS_HEADERS))
    # Write column headers in row 9 if missing; apply formatting on first init
    current = ws.row_values(COLUMN_HEADERS_ROW)
    is_first_init = current[: len(ANALYTICS_HEADERS)] != ANALYTICS_HEADERS
    if is_first_init:
        ws.update(
            range_name=f"A{COLUMN_HEADERS_ROW}",
            values=[ANALYTICS_HEADERS],
        )
        try:
            from services.sheets_sync.sync.format_promocodes_sheet import (
                apply_visual_formatting,
            )
            apply_visual_formatting(ws)
        except Exception as e:
            logger.warning("Visual formatting failed (sheet still usable): %s", e)
    return ws


def upsert_rows(ws: gspread.Worksheet, new_rows: list[list]) -> tuple[int, int]:
    """Upsert rows by key (week_label + cabinet + uuid). Returns (added, updated)."""
    existing = ws.get_all_values()[DATA_START_ROW - 1:]   # data rows only
    # Build existing key index: row offset → key
    key_to_row_idx: dict[tuple[str, str, str], int] = {}
    for i, row in enumerate(existing):
        if len(row) < 4:
            continue
        key = (row[0], row[1], (row[3] or "").lower())
        key_to_row_idx[key] = i  # 0-based offset within data range

    updates: list[gspread.Cell] = []
    appends: list[list] = []
    added = updated = 0

    for nr in new_rows:
        key = (nr[0], nr[1], (nr[3] or "").lower())
        if key in key_to_row_idx:
            # update in place
            target_row = DATA_START_ROW + key_to_row_idx[key]
            for col_idx, value in enumerate(nr, start=1):
                updates.append(
                    gspread.Cell(row=target_row, col=col_idx, value=value)
                )
            updated += 1
        else:
            appends.append(nr)
            added += 1

    if updates:
        ws.update_cells(updates, value_input_option="USER_ENTERED")
    if appends:
        next_row = DATA_START_ROW + len(existing)
        ws.update(
            range_name=f"A{next_row}",
            values=appends,
            value_input_option="USER_ENTERED",
        )
    logger.info("Upsert: +%d, ~%d", added, updated)
    return added, updated


from shared.clients.sheets_client import get_moscow_now


def write_dashboard_header(
    ws: gspread.Worksheet,
    summary: dict,
    weeks_processed: list[tuple[date, date]],
) -> None:
    """Render dashboard rows 1-8 with timestamp, status, and last-week metrics."""
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
    """Main entry. Returns:
        {status, started_at, finished_at, weeks_processed,
         cabinets, rows_added, rows_updated, unknown_uuids}
    """
    started = get_moscow_now()
    cabs = cabinets or _cabinets_from_env()
    if not cabs:
        return {"status": "error", "error": "No cabinets configured",
                "started_at": started.isoformat(timespec="seconds")}

    weeks = _resolve_weeks(mode, week_from, week_to, weeks_back)
    dictionary = read_dictionary_sheet()
    ws = ensure_analytics_sheet()
    updated_at_iso = started.strftime("%Y-%m-%d %H:%M")
    rows_added = rows_updated = 0
    unknown_set: set[str] = set()
    last_week_aggs: dict[str, dict] = {}

    for week_start, week_end in weeks:
        week_sheet_rows: list[list] = []
        for cab_name, api_key in cabs:
            api_rows = fetch_report(api_key, cab_name, week_start, week_end)
            agg = aggregate_by_uuid(api_rows)
            for uuid, m in agg.items():
                week_sheet_rows.append(
                    format_analytics_row(
                        week_start, week_end, cab_name, uuid, m, dictionary,
                        updated_at_iso,
                    )
                )
            for uuid in agg:
                if uuid.lower() not in dictionary:
                    unknown_set.add(uuid)
            # Last-week summary uses the chronologically newest week (weeks[0])
            if (week_start, week_end) == weeks[0]:
                for uuid, m in agg.items():
                    cur = last_week_aggs.get(uuid)
                    if cur is None:
                        last_week_aggs[uuid] = dict(m)
                    else:
                        cur["sales_rub"] += m["sales_rub"]
                        cur["orders_count"] += m["orders_count"]
        if week_sheet_rows:
            a, u = upsert_rows(ws, week_sheet_rows)
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
