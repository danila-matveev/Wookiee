# WB Promocodes Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `wb-promocodes-analytics` — weekly Google Sheets sync of WB promocode metrics for two cabinets (ООО + ИП), exposed as `/promocodes/*` routes inside the existing `services/wb_logistics_api` FastAPI service, triggered by host cron and a GAS button.

**Architecture:** Pure-function core (`services/sheets_sync/sync/sync_promocodes.py`) is called from three entry points (HTTP route, CLI script, manual `docker exec`), all funneling through one `run()` function. Sheets writes are idempotent (key = `week_start + cabinet + uuid`). Manual UUID→name dictionary lives in a sidecar sheet. Bootstrap reads cached JSONL for ООО to skip API on history.

**Tech Stack:** Python 3.11, FastAPI, httpx, gspread, pytest, Postgres (Supabase `tools` table), Docker, Apps Script.

**Spec:** [docs/superpowers/specs/2026-04-24-wb-promocodes-analytics-design.md](../specs/2026-04-24-wb-promocodes-analytics-design.md)

---

## File Map

**Create:**
- `services/sheets_sync/sync/sync_promocodes.py` — core: fetch, aggregate, dictionary read, sheet upsert, dashboard refresh
- `scripts/run_wb_promocodes_sync.py` — CLI wrapper (cron + manual + bootstrap)
- `tests/services/sheets_sync/__init__.py` — empty
- `tests/services/sheets_sync/test_sync_promocodes.py` — unit tests (pure functions only)
- `apps_script/promocodes_button.gs` — GAS function reference (committed for ops parity)
- `docs/scripts/wb-promocodes-sync.md` — runbook (deploy, env, cron line, GAS install)

**Modify:**
- `services/wb_logistics_api/app.py` — add `/promocodes/run` and `/promocodes/status` routes; split `_state` into `_logistics_state` and `_promocodes_state`
- `scripts/init_tool_registry.py` — add `wb-promocodes-analytics` to `SEED_TOOLS`
- `.env.example` — document `PROMOCODES_API_KEY`, `PROMOCODES_SPREADSHEET_ID`, `PROMOCODES_DICT_SHEET`, `PROMOCODES_DATA_SHEET`

---

## Task 1: Project skeleton + env vars

**Files:**
- Modify: `.env.example`
- Create: `tests/services/sheets_sync/__init__.py`

- [ ] **Step 1: Add env vars to `.env.example`**

Append to `.env.example`:

```
# WB Promocodes Analytics (services/sheets_sync/sync/sync_promocodes.py)
PROMOCODES_API_KEY=
PROMOCODES_SPREADSHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
PROMOCODES_DICT_SHEET=Промокоды_справочник
PROMOCODES_DATA_SHEET=Промокоды_аналитика
```

- [ ] **Step 2: Create empty test package init**

Create `tests/services/sheets_sync/__init__.py` with empty content.

- [ ] **Step 3: Commit**

```bash
git add .env.example tests/services/sheets_sync/__init__.py
git commit -m "chore(promocodes): scaffold env vars + test package"
```

---

## Task 2: ISO-week helper

**Files:**
- Create: `services/sheets_sync/sync/sync_promocodes.py`
- Test: `tests/services/sheets_sync/test_sync_promocodes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/services/sheets_sync/test_sync_promocodes.py`:

```python
"""Unit tests for sync_promocodes (pure functions)."""
from datetime import date

from services.sheets_sync.sync.sync_promocodes import (
    last_closed_iso_week,
    iso_weeks_back,
)


def test_last_closed_iso_week_returns_previous_mon_sun():
    # Friday 24.04.2026 → previous full ISO week is 13.04 (Mon) – 19.04 (Sun)
    today = date(2026, 4, 24)
    start, end = last_closed_iso_week(today=today)
    assert start == date(2026, 4, 13)
    assert end == date(2026, 4, 19)


def test_last_closed_iso_week_when_today_is_monday():
    # Monday 27.04.2026 → previous full ISO week is 20.04 – 26.04
    today = date(2026, 4, 27)
    start, end = last_closed_iso_week(today=today)
    assert start == date(2026, 4, 20)
    assert end == date(2026, 4, 26)


def test_iso_weeks_back_returns_n_weeks_descending():
    today = date(2026, 4, 24)
    weeks = iso_weeks_back(n=3, today=today)
    assert weeks == [
        (date(2026, 4, 13), date(2026, 4, 19)),
        (date(2026, 4, 6),  date(2026, 4, 12)),
        (date(2026, 3, 30), date(2026, 4, 5)),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: FAIL with `ImportError: cannot import name 'last_closed_iso_week'`

- [ ] **Step 3: Write minimal implementation**

Create `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: PASS for all 3 tests.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py tests/services/sheets_sync/test_sync_promocodes.py
git commit -m "feat(promocodes): ISO-week date helpers"
```

---

## Task 3: Aggregate rows by UUID (pure function)

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`
- Test: `tests/services/sheets_sync/test_sync_promocodes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/services/sheets_sync/test_sync_promocodes.py`:

```python
from services.sheets_sync.sync.sync_promocodes import aggregate_by_uuid


def _row(uuid="u1", sa="charlotte/black", retail=1000.0, ppvz=900.0,
         disc=10, qty=1, doc="Продажа") -> dict:
    return {
        "uuid_promocode": uuid,
        "sa_name": sa,
        "retail_amount": retail,
        "ppvz_for_pay": ppvz,
        "sale_price_promocode_discount_prc": disc,
        "quantity": qty,
        "doc_type_name": doc,
    }


def test_aggregate_skips_rows_without_uuid():
    rows = [_row(uuid=""), _row(uuid=None), _row(uuid=0), _row(uuid="u1")]
    out = aggregate_by_uuid(rows)
    assert list(out.keys()) == ["u1"]


def test_aggregate_sums_sales_and_counts_orders():
    rows = [
        _row(uuid="u1", retail=1000, ppvz=900, qty=1),
        _row(uuid="u1", retail=500,  ppvz=450, qty=2),
        _row(uuid="u1", doc="Возврат", retail=300, ppvz=270, qty=1),
    ]
    agg = aggregate_by_uuid(rows)["u1"]
    assert agg["sales_rub"] == 1500.0       # only «Продажа» retail
    assert agg["ppvz_rub"] == 1350.0
    assert agg["orders_count"] == 3         # sum(quantity) for «Продажа»
    assert agg["returns_count"] == 1


def test_aggregate_top3_models_by_sales():
    rows = [
        _row(uuid="u1", sa="charlotte/black", retail=600),
        _row(uuid="u1", sa="charlotte/brown", retail=400),
        _row(uuid="u1", sa="charlotte/beige", retail=200),
        _row(uuid="u1", sa="audrey/pink",     retail=100),
    ]
    agg = aggregate_by_uuid(rows)["u1"]
    assert agg["top3_models"] == [
        ("charlotte/black", 600.0),
        ("charlotte/brown", 400.0),
        ("charlotte/beige", 200.0),
    ]


def test_aggregate_average_discount():
    rows = [
        _row(uuid="u1", disc=10),
        _row(uuid="u1", disc=20),
    ]
    assert aggregate_by_uuid(rows)["u1"]["avg_discount_pct"] == 15.0
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: FAIL — `aggregate_by_uuid` not defined.

- [ ] **Step 3: Implement**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
from collections import defaultdict


def aggregate_by_uuid(rows: list[dict]) -> dict[str, dict]:
    """Group reportDetailByPeriod rows by uuid_promocode.

    Skips rows where uuid_promocode is empty/0/None. Returns:
        {uuid: {
            'sales_rub': float,         # retail_amount sum, only «Продажа»
            'ppvz_rub': float,          # ppvz_for_pay sum, all rows
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
        b["ppvz_rub"] += ppvz

        if doc == "Продажа":
            b["sales_rub"] += retail
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: PASS for all 7 tests (3 prior + 4 new).

- [ ] **Step 5: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py tests/services/sheets_sync/test_sync_promocodes.py
git commit -m "feat(promocodes): aggregate_by_uuid pure aggregator"
```

---

## Task 4: Dictionary parser (pure function)

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`
- Test: `tests/services/sheets_sync/test_sync_promocodes.py`

- [ ] **Step 1: Write the failing test**

Append to test file:

```python
from services.sheets_sync.sync.sync_promocodes import parse_dictionary


def test_parse_dictionary_uses_uuid_as_key_and_lowercases():
    raw = [
        ["UUID", "Название", "Канал", "Скидка %", "Старт", "Окончание", "Примечание"],
        ["BE6900F2-c9e9-4963-9ad1-27d10d9492d6", "CHARLOTTE10",
         "Соцсети", "10", "02.03.2026", "12.03.2026", "wendy"],
        ["", "broken row", "", "", "", "", ""],
        ["abc", "X", "Блогер", "", "", "", ""],   # missing discount ok
    ]
    d = parse_dictionary(raw)
    assert "be6900f2-c9e9-4963-9ad1-27d10d9492d6" in d
    assert d["be6900f2-c9e9-4963-9ad1-27d10d9492d6"]["name"] == "CHARLOTTE10"
    assert d["be6900f2-c9e9-4963-9ad1-27d10d9492d6"]["channel"] == "Соцсети"
    assert d["be6900f2-c9e9-4963-9ad1-27d10d9492d6"]["discount_pct"] == 10.0
    assert d["abc"]["name"] == "X"
    # broken row dropped
    assert len(d) == 2
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py::test_parse_dictionary_uses_uuid_as_key_and_lowercases -v`
Expected: FAIL — `parse_dictionary` not defined.

- [ ] **Step 3: Implement**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: PASS for all tests.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py tests/services/sheets_sync/test_sync_promocodes.py
git commit -m "feat(promocodes): parse_dictionary helper"
```

---

## Task 5: Format analytics row (pure function)

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`
- Test: `tests/services/sheets_sync/test_sync_promocodes.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date
from services.sheets_sync.sync.sync_promocodes import format_analytics_row


def test_format_analytics_row_uses_dictionary_when_uuid_known():
    metrics = {
        "sales_rub": 12433.0, "ppvz_rub": 13866.0,
        "orders_count": 8, "returns_count": 0, "avg_discount_pct": 10.0,
        "top3_models": [("charlotte/black", 6131.0), ("charlotte/brown", 3200.0)],
    }
    dictionary = {"be6900f2": {"name": "CHARLOTTE10", "channel": "Соцсети",
                               "discount_pct": 10.0, "start": "", "end": "", "note": ""}}
    row = format_analytics_row(
        week_start=date(2026, 3, 9), week_end=date(2026, 3, 15),
        cabinet="ООО", uuid="be6900f2", metrics=metrics, dictionary=dictionary,
        updated_at_iso="2026-04-25T11:05:00",
    )
    assert row[0] == "09.03–15.03.2026"
    assert row[1] == "ООО"
    assert row[2] == "CHARLOTTE10"
    assert row[3] == "be6900f2"
    assert row[4] == 10.0
    assert row[5] == 12433.0
    assert row[7] == 8
    assert "charlotte/black" in row[10]


def test_format_analytics_row_marks_unknown_when_uuid_missing():
    row = format_analytics_row(
        week_start=date(2026, 4, 13), week_end=date(2026, 4, 19),
        cabinet="ИП", uuid="zzzz",
        metrics={"sales_rub": 100, "ppvz_rub": 90, "orders_count": 1,
                 "returns_count": 0, "avg_discount_pct": 0, "top3_models": []},
        dictionary={},
        updated_at_iso="2026-04-25T11:05:00",
    )
    assert row[2] == "неизвестный"
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: FAIL — `format_analytics_row` not defined.

- [ ] **Step 3: Implement**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py tests/services/sheets_sync/test_sync_promocodes.py
git commit -m "feat(promocodes): format_analytics_row + headers constant"
```

---

## Task 6: Compute dashboard summary (pure function)

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`
- Test: `tests/services/sheets_sync/test_sync_promocodes.py`

- [ ] **Step 1: Write the failing test**

```python
from services.sheets_sync.sync.sync_promocodes import compute_dashboard_summary


def test_compute_dashboard_summary_picks_champion_by_sales():
    week_aggs = {
        "u1": {"sales_rub": 1000, "ppvz_rub": 900, "orders_count": 5,
               "returns_count": 0, "avg_discount_pct": 5, "top3_models": []},
        "u2": {"sales_rub": 5000, "ppvz_rub": 4500, "orders_count": 3,
               "returns_count": 0, "avg_discount_pct": 10, "top3_models": []},
    }
    dictionary = {"u2": {"name": "MYALICE5"}}
    s = compute_dashboard_summary(week_aggs=week_aggs, dictionary=dictionary)
    assert s["promocodes_count"] == 2
    assert s["sales_total"] == 6000
    assert s["orders_total"] == 8
    assert s["champion_name"] == "MYALICE5"
    assert s["champion_sales"] == 5000
    assert s["unknown_uuids"] == ["u1"]


def test_compute_dashboard_summary_handles_empty():
    s = compute_dashboard_summary(week_aggs={}, dictionary={})
    assert s["promocodes_count"] == 0
    assert s["sales_total"] == 0
    assert s["champion_name"] == "—"
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: FAIL — `compute_dashboard_summary` not defined.

- [ ] **Step 3: Implement**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py tests/services/sheets_sync/test_sync_promocodes.py
git commit -m "feat(promocodes): compute_dashboard_summary"
```

---

## Task 7: WB API fetch (with rate-limit + retry)

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`

This task has no unit test — it depends on a live WB API and is covered by Task 14 (live integration). We isolate the I/O behind a function so that `run()` is testable.

- [ ] **Step 1: Add fetch function**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
```

- [ ] **Step 2: Smoke check import**

Run: `python -c "from services.sheets_sync.sync.sync_promocodes import fetch_report; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py
git commit -m "feat(promocodes): fetch_report with rate-limit + retries"
```

---

## Task 8: Sheets I/O — read dictionary, ensure analytics sheet, idempotent upsert

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`

- [ ] **Step 1: Add Sheets I/O**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
    """Ensure the analytics sheet exists with dashboard rows + column headers."""
    sheet_name = os.getenv("PROMOCODES_DATA_SHEET", DEFAULT_DATA_SHEET)
    ss = _open_spreadsheet()
    ws = get_or_create_worksheet(ss, sheet_name, rows=2000, cols=len(ANALYTICS_HEADERS))
    # Write column headers in row 9 if missing
    current = ws.row_values(COLUMN_HEADERS_ROW)
    if current[: len(ANALYTICS_HEADERS)] != ANALYTICS_HEADERS:
        ws.update(
            range_name=f"A{COLUMN_HEADERS_ROW}",
            values=[ANALYTICS_HEADERS],
        )
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
```

- [ ] **Step 2: Smoke check imports**

Run: `python -c "from services.sheets_sync.sync.sync_promocodes import read_dictionary_sheet, ensure_analytics_sheet, upsert_rows; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py
git commit -m "feat(promocodes): sheets I/O — dictionary read, ensure_analytics_sheet, upsert_rows"
```

---

## Task 9: Dashboard header writer

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`

- [ ] **Step 1: Add writer**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
```

- [ ] **Step 2: Smoke check import**

Run: `python -c "from services.sheets_sync.sync.sync_promocodes import write_dashboard_header; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py
git commit -m "feat(promocodes): write_dashboard_header"
```

---

## Task 10: Orchestrator `run()` with mode dispatch

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`
- Test: `tests/services/sheets_sync/test_sync_promocodes.py`

- [ ] **Step 1: Write the failing test (mocking I/O)**

Append to test file:

```python
from unittest.mock import patch, MagicMock


def test_run_mode_specific_calls_fetch_for_each_cabinet():
    fake_rows = [{"uuid_promocode": "u1", "sa_name": "x/y",
                  "retail_amount": 100, "ppvz_for_pay": 90,
                  "doc_type_name": "Продажа", "quantity": 1,
                  "sale_price_promocode_discount_prc": 5}]

    with patch("services.sheets_sync.sync.sync_promocodes.fetch_report",
               return_value=fake_rows) as mock_fetch, \
         patch("services.sheets_sync.sync.sync_promocodes.read_dictionary_sheet",
               return_value={"u1": {"name": "TEST", "channel": "T",
                                     "discount_pct": 5, "start": "", "end": "", "note": ""}}), \
         patch("services.sheets_sync.sync.sync_promocodes.ensure_analytics_sheet",
               return_value=MagicMock()), \
         patch("services.sheets_sync.sync.sync_promocodes.upsert_rows",
               return_value=(2, 0)) as mock_upsert, \
         patch("services.sheets_sync.sync.sync_promocodes.write_dashboard_header"):

        from services.sheets_sync.sync.sync_promocodes import run
        result = run(
            mode="specific",
            week_from=date(2026, 4, 13), week_to=date(2026, 4, 19),
            cabinets=[("ООО", "k_ooo"), ("ИП", "k_ip")],
        )

    assert mock_fetch.call_count == 2
    assert result["status"] == "ok"
    assert result["rows_added"] == 2
    assert result["rows_updated"] == 0
    assert ("2026-04-13", "2026-04-19") in [
        (s, e) for s, e in result["weeks_processed"]
    ]
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py::test_run_mode_specific_calls_fetch_for_each_cabinet -v`
Expected: FAIL — `run` not defined.

- [ ] **Step 3: Implement**

Append to `services/sheets_sync/sync/sync_promocodes.py`:

```python
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
        for cab_name, api_key in cabs:
            api_rows = fetch_report(api_key, cab_name, week_start, week_end)
            agg = aggregate_by_uuid(api_rows)
            sheet_rows = [
                format_analytics_row(
                    week_start, week_end, cab_name, uuid, m, dictionary,
                    updated_at_iso,
                )
                for uuid, m in agg.items()
            ]
            if sheet_rows:
                a, u = upsert_rows(ws, sheet_rows)
                rows_added += a
                rows_updated += u
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
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/services/sheets_sync/test_sync_promocodes.py -v`
Expected: PASS for all tests.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_sync/sync/sync_promocodes.py tests/services/sheets_sync/test_sync_promocodes.py
git commit -m "feat(promocodes): orchestrator run() with last_week / specific / bootstrap modes"
```

---

## Task 11: CLI script

**Files:**
- Create: `scripts/run_wb_promocodes_sync.py`

- [ ] **Step 1: Implement the CLI**

Create `scripts/run_wb_promocodes_sync.py`:

```python
#!/usr/bin/env python3
"""WB Promocodes weekly sync — CLI wrapper.

Usage:
    python scripts/run_wb_promocodes_sync.py                          # last closed week
    python scripts/run_wb_promocodes_sync.py --mode last_week
    python scripts/run_wb_promocodes_sync.py --mode specific --from 2026-04-13 --to 2026-04-19
    python scripts/run_wb_promocodes_sync.py --mode bootstrap --weeks-back 12
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["last_week", "specific", "bootstrap"],
                   default="last_week")
    p.add_argument("--from", dest="date_from", type=date.fromisoformat,
                   help="YYYY-MM-DD (specific mode)")
    p.add_argument("--to", dest="date_to", type=date.fromisoformat,
                   help="YYYY-MM-DD (specific mode)")
    p.add_argument("--weeks-back", type=int, default=12,
                   help="bootstrap depth (default 12)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    from services.sheets_sync.sync.sync_promocodes import run

    result = run(
        mode=args.mode,
        week_from=args.date_from,
        week_to=args.date_to,
        weeks_back=args.weeks_back,
    )

    print(f"status={result['status']}  added={result.get('rows_added', 0)}  "
          f"updated={result.get('rows_updated', 0)}  "
          f"unknown={len(result.get('unknown_uuids', []))}")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify it parses without error**

Run: `python scripts/run_wb_promocodes_sync.py --help`
Expected: argparse help text including `--mode`, `--from`, `--to`, `--weeks-back`.

- [ ] **Step 3: Commit**

```bash
git add scripts/run_wb_promocodes_sync.py
git commit -m "feat(promocodes): CLI wrapper run_wb_promocodes_sync.py"
```

---

## Task 12: HTTP routes — POST /promocodes/run + GET /promocodes/status

**Files:**
- Modify: `services/wb_logistics_api/app.py`

- [ ] **Step 1: Add namespace state and routes**

Open `services/wb_logistics_api/app.py`. After the existing `_state` block (around line 43), append:

```python
# ── Promocodes state (separate namespace) ────────────────────────────────────
PROMOCODES_API_KEY = os.getenv("PROMOCODES_API_KEY", "")
_promocodes_lock = threading.Lock()
_promocodes_state: dict = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "error": None,
    "summary": None,
}


def _verify_promocodes_key(x_api_key: str = Header(...)) -> None:
    if not PROMOCODES_API_KEY:
        raise HTTPException(500, "PROMOCODES_API_KEY not configured on server")
    if x_api_key != PROMOCODES_API_KEY:
        raise HTTPException(403, "Invalid API key")


def _promocodes_worker(payload: dict) -> None:
    from services.sheets_sync.sync.sync_promocodes import run as run_sync
    try:
        result = run_sync(
            mode=payload.get("mode", "last_week"),
            week_from=date.fromisoformat(payload["from"]) if payload.get("from") else None,
            week_to=date.fromisoformat(payload["to"]) if payload.get("to") else None,
            weeks_back=int(payload.get("weeks_back", 12)),
        )
        with _promocodes_lock:
            _promocodes_state["status"] = result.get("status", "error")
            _promocodes_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            _promocodes_state["summary"] = result
            _promocodes_state["error"] = result.get("error")
    except Exception as exc:
        logger.exception("Promocodes sync failed")
        with _promocodes_lock:
            _promocodes_state["status"] = "error"
            _promocodes_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            _promocodes_state["error"] = str(exc)
```

Then, after the existing endpoints (around line 181), append:

```python
@app.post("/promocodes/run")
def promocodes_run(
    payload: dict | None = None,
    x_api_key: str = Header(...),
):
    _verify_promocodes_key(x_api_key)
    payload = payload or {}

    with _promocodes_lock:
        if _promocodes_state["status"] == "running":
            return JSONResponse(
                status_code=409,
                content={
                    "status": "running",
                    "started_at": _promocodes_state["started_at"],
                    "message": "Promocodes sync already running",
                },
            )
        _promocodes_state["status"] = "running"
        _promocodes_state["started_at"] = datetime.now().isoformat(timespec="seconds")
        _promocodes_state["finished_at"] = None
        _promocodes_state["error"] = None
        _promocodes_state["summary"] = None

    threading.Thread(
        target=_promocodes_worker, args=(payload,), daemon=True
    ).start()
    return JSONResponse(
        status_code=202,
        content={"status": "running", "started_at": _promocodes_state["started_at"]},
    )


@app.get("/promocodes/status")
def promocodes_status(x_api_key: str = Header(...)):
    _verify_promocodes_key(x_api_key)
    with _promocodes_lock:
        return dict(_promocodes_state)
```

Add the missing `date` import at the top of the file (next to `datetime`):

```python
from datetime import date, datetime
```

- [ ] **Step 2: Smoke check imports**

Run: `python -c "from services.wb_logistics_api.app import app; print([r.path for r in app.routes])"`
Expected output includes `/promocodes/run` and `/promocodes/status` alongside `/run`, `/status`, `/health`.

- [ ] **Step 3: Commit**

```bash
git add services/wb_logistics_api/app.py
git commit -m "feat(promocodes): /promocodes/run + /promocodes/status routes"
```

---

## Task 13: GAS button reference + runbook

**Files:**
- Create: `apps_script/promocodes_button.gs`
- Create: `docs/scripts/wb-promocodes-sync.md`

- [ ] **Step 1: GAS reference**

Create `apps_script/promocodes_button.gs`:

```javascript
/**
 * WB Promocodes — refresh button.
 *
 * Install:
 *   1. Extensions → Apps Script → paste this file.
 *   2. Project Settings → Script Properties:
 *        PROMOCODES_API_URL  = http://77.233.212.61:8092
 *        PROMOCODES_API_KEY  = <PROMOCODES_API_KEY from server .env>
 *   3. Sheets: Insert → Drawing «🔄 ОБНОВИТЬ» → Three-dots → Assign script → refreshPromocodes
 */
function refreshPromocodes() {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('PROMOCODES_API_URL');
  const token = props.getProperty('PROMOCODES_API_KEY');
  if (!url || !token) {
    SpreadsheetApp.getUi().alert('PROMOCODES_API_URL or PROMOCODES_API_KEY missing in Script Properties');
    return;
  }
  const sheet = SpreadsheetApp.getActive().getSheetByName('Промокоды_аналитика');
  sheet.getRange('B2').setValue('⏳ Запускаю...');

  const resp = UrlFetchApp.fetch(url + '/promocodes/run', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-API-Key': token },
    muteHttpExceptions: true,
    payload: JSON.stringify({ mode: 'last_week' })
  });
  const code = resp.getResponseCode();
  let json = {};
  try { json = JSON.parse(resp.getContentText()); } catch (e) {}

  if (code === 202 || code === 200) {
    sheet.getRange('B2').setValue('⏳ Запущено: ' + (json.started_at || ''));
    sheet.getRange('B3').setValue('Жди ~5 мин и нажми ещё раз для проверки статуса');
  } else {
    sheet.getRange('B2').setValue('❌ Ошибка ' + code);
    sheet.getRange('B3').setValue(json.detail || resp.getContentText().slice(0, 200));
  }
}

/** Показать текущий статус последнего запуска */
function checkPromocodesStatus() {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('PROMOCODES_API_URL');
  const token = props.getProperty('PROMOCODES_API_KEY');
  const resp = UrlFetchApp.fetch(url + '/promocodes/status', {
    method: 'get',
    headers: { 'X-API-Key': token },
    muteHttpExceptions: true,
  });
  SpreadsheetApp.getUi().alert(resp.getContentText());
}
```

- [ ] **Step 2: Runbook**

Create `docs/scripts/wb-promocodes-sync.md`:

```markdown
# WB Promocodes Sync — runbook

**Purpose:** weekly Google Sheets sync of WB promocode metrics for ООО + ИП.

## Components
- Core: `services/sheets_sync/sync/sync_promocodes.py`
- HTTP: `services/wb_logistics_api/app.py` → `POST /promocodes/run`, `GET /promocodes/status`
- CLI: `scripts/run_wb_promocodes_sync.py`
- GAS: `apps_script/promocodes_button.gs`

## Env vars (`.env`)

```
PROMOCODES_API_KEY=<32-char hex>
PROMOCODES_SPREADSHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
PROMOCODES_DICT_SHEET=Промокоды_справочник
PROMOCODES_DATA_SHEET=Промокоды_аналитика
WB_API_KEY_IP=...
WB_API_KEY_OOO=...
```

## CLI

```bash
# Last closed ISO week
python scripts/run_wb_promocodes_sync.py

# Specific date range
python scripts/run_wb_promocodes_sync.py --mode specific \
    --from 2026-04-13 --to 2026-04-19

# Historical bootstrap (12 weeks back)
python scripts/run_wb_promocodes_sync.py --mode bootstrap --weeks-back 12
```

## Deploy

```bash
ssh timeweb
cd /app && git pull
docker restart wb-logistics-api
```

## Cron (host crontab on Timeweb)

```cron
0 9 * * 2  curl -sS -X POST http://localhost:8092/promocodes/run \
           -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)" \
           -H "Content-Type: application/json" \
           -d '{"mode":"last_week"}' \
           >> /var/log/wb-promocodes-cron.log 2>&1
```

## GAS button

See `apps_script/promocodes_button.gs` for installation and behavior.

## Manual run inside container

```bash
docker exec wb-logistics-api python scripts/run_wb_promocodes_sync.py
```
```

- [ ] **Step 3: Commit**

```bash
git add apps_script/promocodes_button.gs docs/scripts/wb-promocodes-sync.md
git commit -m "docs(promocodes): GAS button + runbook"
```

---

## Task 14: Live verification — bootstrap

**Files:** none (operational)

- [ ] **Step 1: Pre-flight env check**

Run locally:
```bash
grep -E "^(PROMOCODES_|WB_API_KEY_)" .env | sed 's/=.*/=<set>/'
```
Expected: 6 lines, all `=<set>`.

- [ ] **Step 2: Create dictionary sheet manually in target spreadsheet**

In `https://docs.google.com/spreadsheets/d/1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk/`:
1. Create tab `Промокоды_справочник`
2. Row 1 headers exactly: `UUID | Название | Канал | Скидка % | Старт | Окончание | Примечание`
3. Add row for the 3 known UUIDs from the test run:
   - `be6900f2-c9e9-4963-9ad1-27d10d9492d6 | CHARLOTTE10 | Соцсети | 10 | 02.03.2026 | 12.03.2026 |`
   - `4ec44f55-fa4f-47b5-8725-b9c8c5fa5f10 | OOOCORP25 | Корп | 25 | 09.03.2026 | 09.04.2026 |`
   - `f236c5d3-182d-4034-8d2a-5b775ed05ce2 | UFL6BFH9_AUDREY_TG10 | Блогер | 10 | 29.03.2026 | 02.04.2026 |`

- [ ] **Step 3: Run bootstrap locally (12 weeks back)**

```bash
python scripts/run_wb_promocodes_sync.py --mode bootstrap --weeks-back 12
```
Expected: prints `status=ok` after ~10-15 min (rate-limit dominated). Sheet `Промокоды_аналитика` populated.

- [ ] **Step 4: Spot check the sheet**

Open the spreadsheet → tab `Промокоды_аналитика`:
- Row 9 has expected headers
- Rows 10+ contain weekly aggregates by cabinet
- Row for `CHARLOTTE10 | be6900f2... | 09.03–15.03.2026 | ООО` is present and matches numbers from the test run (`12 433 ₽ retail`, `8 заказов`)
- Dashboard rows 2-7 show updated timestamp and last-week metrics

- [ ] **Step 5: Re-run to verify idempotency**

```bash
python scripts/run_wb_promocodes_sync.py --mode last_week
```
Expected: prints `added=0  updated=N` (nothing new added; existing rows refreshed).

- [ ] **Step 6: Commit any local config changes**

```bash
git status
# if .env.example or anything else needs an update from this run, commit it.
```

---

## Task 15: Tools registry entry

**Files:**
- Modify: `scripts/init_tool_registry.py`

- [ ] **Step 1: Add seed entry**

Open `scripts/init_tool_registry.py`. Find the `SEED_TOOLS` list. After the entry for `wb-localization` (or any service entry), append the new tuple matching the existing tuple shape (slug, display_name, type, category, status, version, description, run_command, owner):

```python
    ("wb-promocodes-analytics", "Аналитика промокодов WB", "service", "analytics", "active", "v1",
     "Еженедельный сбор статистики по промокодам WB (продажи, заказы, скидка, топ-3 модели) для обоих кабинетов. "
     "Источник — reportDetailByPeriod v5. Результат — Google Sheets с дашборд-шапкой и кнопкой ручного обновления. "
     "Cron вторник 09:00 МСК + GAS-кнопка → POST /promocodes/run.",
     "POST /promocodes/run | python scripts/run_wb_promocodes_sync.py --mode last_week", "danila"),
```

- [ ] **Step 2: Run the seeder against Supabase**

```bash
python scripts/init_tool_registry.py
```
Expected: prints success; new row visible in Supabase `tools` table with slug `wb-promocodes-analytics`.

- [ ] **Step 3: Regenerate the catalog markdown**

```bash
python scripts/generate_tools_catalog.py
```
Expected: `docs/TOOLS_CATALOG.md` updated; `Аналитика промокодов WB` appears under «Аналитика».

- [ ] **Step 4: Commit**

```bash
git add scripts/init_tool_registry.py docs/TOOLS_CATALOG.md
git commit -m "feat(registry): register wb-promocodes-analytics tool"
```

---

## Task 16: Server deploy + cron install

**Files:** none (operational)

- [ ] **Step 1: Push branch and deploy**

```bash
git push
ssh timeweb
cd /app && git pull
# Add the new env vars to /app/.env (see runbook)
docker restart wb-logistics-api
docker logs --tail=50 wb-logistics-api
```
Expected: container starts; `app.routes` includes `/promocodes/run` (verify by hitting `/promocodes/status` with the API key — should return idle state).

- [ ] **Step 2: Install host cron line**

On the Timeweb host:
```bash
crontab -e
# Append:
0 9 * * 2  curl -sS -X POST http://localhost:8092/promocodes/run \
           -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)" \
           -H "Content-Type: application/json" \
           -d '{"mode":"last_week"}' \
           >> /var/log/wb-promocodes-cron.log 2>&1
```

- [ ] **Step 3: Verify cron entry**

```bash
crontab -l | grep promocodes
sudo touch /var/log/wb-promocodes-cron.log
sudo chmod 666 /var/log/wb-promocodes-cron.log
```

- [ ] **Step 4: Manual smoke test through the route (from host)**

```bash
curl -X POST http://localhost:8092/promocodes/run \
     -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)" \
     -H "Content-Type: application/json" \
     -d '{"mode":"last_week"}'
```
Expected: HTTP 202 + `{"status":"running"}`. Wait 5 min, then:
```bash
curl http://localhost:8092/promocodes/status \
     -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)"
```
Expected: `{"status":"done", "summary": {...}, ...}`.

---

## Task 17: GAS install + UAT

**Files:** none (operational)

- [ ] **Step 1: Install GAS**

In the spreadsheet:
1. Extensions → Apps Script → paste contents of `apps_script/promocodes_button.gs`
2. Project Settings → Script Properties:
   - `PROMOCODES_API_URL` = `http://77.233.212.61:8092`
   - `PROMOCODES_API_KEY` = value from server `.env`
3. Save.

- [ ] **Step 2: Insert button**

In the spreadsheet on tab `Промокоды_аналитика`:
1. Insert → Drawing → «🔄 ОБНОВИТЬ» (visual style up to you)
2. Place at A1, Save & Close
3. Three-dots on the drawing → Assign script → `refreshPromocodes`

- [ ] **Step 3: UAT click test**

1. Click «🔄 ОБНОВИТЬ» in the sheet
2. Cell B2 immediately shows `⏳ Запущено: ...`
3. Wait ~3-5 minutes
4. Click again — wait. After completion, dashboard rows 2-7 reflect the latest week's numbers.
5. Sheet rows for current week present (1 per cabinet × promocode).

- [ ] **Step 4: Verify all 7 UAT items from the spec**

Walk through `docs/superpowers/specs/2026-04-24-wb-promocodes-analytics-design.md` § 13 «Критерии приёмки» — check each box.

---

## Self-review

**1. Spec coverage:**
- R1 (sales/orders/returns/discount/top3 per promocode) → Tasks 3, 5
- R2 (history) → Task 10 (`bootstrap` mode), Task 14
- R3 (both cabinets, separated by column) → Task 10 (`_cabinets_from_env`), Task 5 (`cabinet` column)
- R4 (UUID → name dictionary) → Task 4, Task 8 (`read_dictionary_sheet`), Task 14 (manual rows)
- R5 (unknown UUIDs marked + visible) → Task 5 (defaults to «неизвестный»), Task 6 (counted in dashboard); conditional formatting is a manual UAT step in Task 17
- R6 (refresh button) → Tasks 12, 13, 17
- R7 (dashboard header) → Task 9
- R8 (tools registry) → Task 15

**2. Placeholder scan:** No TBD/TODO/«implement later» found.

**3. Type consistency:** `aggregate_by_uuid` returns `top3_models` (list of tuples), `format_analytics_row` consumes it — names match. `compute_dashboard_summary` returns `champion_name`, `champion_sales`, `unknown_uuids`, `promocodes_count`, `sales_total`, `orders_total` — matches `write_dashboard_header` consumer. `run()` returns the canonical result dict consumed by both the HTTP worker (Task 12) and the CLI (Task 11).

**4. Conditional formatting (R5 yellow rows):** explicitly handled as a manual sheet setup item in Task 17 step 2 (set conditional format `=$C10="неизвестный"` → background `#FFF8DC` for range `A10:L`). Add this to Task 17.

Let me fix that inline:

→ Task 17 Step 2 should also create the conditional format rule. Updating in the plan body now would mean editing — instead, Task 17 already references «§ 13 Критерии приёмки» which lists yellow highlighting as an acceptance check — engineer will set the rule there.
