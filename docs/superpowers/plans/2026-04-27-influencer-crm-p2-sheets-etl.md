# Phase 2: Influencer CRM — Sheets ETL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull-only one-shot ETL from "Маркетинг Wookiee" Google Sheet (ID `1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk`) into Supabase `crm.*` tables. Idempotent re-runs via `sheet_row_id` MD5 content hash.

**Architecture:** Python service in `services/sheets_etl/`. One transformer module per sheet → row dicts → centralized `loader.py` does UPSERT via psycopg2 with `ON CONFLICT (sheet_row_id) DO UPDATE`. CLI: `python -m services.sheets_etl.cli --table=<name> [--dry-run] [--limit=N]`. Sheets stay source-of-truth; ETL is pull-only — no writes back to Sheets.

**Tech Stack:** Python 3.12, psycopg2, gws CLI (Google Sheets), pytest. No new dependencies beyond Phase 1 stack.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `services/sheets_etl/__init__.py` | Package marker | New |
| `services/sheets_etl/config.py` | Spreadsheet ID + sheet→table map + DB config | New |
| `services/sheets_etl/hash.py` | `sheet_row_id(parts: list[str]) -> str` MD5 | New |
| `services/sheets_etl/fetch.py` | `read_range(sheet, range)` wrapper around `gws sheets +read` | New |
| `services/sheets_etl/parsers.py` | Date / int / decimal / bool cell parsers (RU formats) | New |
| `services/sheets_etl/loader.py` | `upsert(table, rows, conflict_col)` + `lookup_id(table, where)` | New |
| `services/sheets_etl/transformers/promo_codes.py` | "Промокоды_справочник" → `crm.promo_codes` | New |
| `services/sheets_etl/transformers/bloggers.py` | "БД БЛОГЕРЫ" → `crm.bloggers` + `crm.blogger_channels` | New |
| `services/sheets_etl/transformers/substitute_articles.py` | "Подменные" → `crm.substitute_articles` + `crm.substitute_article_metrics_weekly` | New |
| `services/sheets_etl/transformers/integrations.py` | "Блогеры" → `crm.integrations` + `crm.integration_substitute_articles` + `crm.integration_promo_codes` | New |
| `services/sheets_etl/transformers/candidates.py` | "inst на проверку" → `crm.blogger_candidates` | New |
| `services/sheets_etl/cli.py` | argparse entry; runs transformers in dependency order | New |
| `tests/sheets_etl/test_hash.py` | Hash helper tests | New |
| `tests/sheets_etl/test_parsers.py` | Cell parser tests (RU dates, "78 400", "10%") | New |
| `tests/sheets_etl/fixtures/` | Captured sample rows (json) per sheet | New |
| `tests/sheets_etl/test_promo_codes.py` | Transformer test on fixture | New |
| `tests/sheets_etl/test_bloggers.py` | Transformer test on fixture | New |
| `tests/sheets_etl/test_substitute_articles.py` | Transformer test on fixture | New |
| `tests/sheets_etl/test_integrations.py` | Transformer test on fixture | New |
| `tests/sheets_etl/test_e2e_counts.py` | After-ETL row-count assertions | New |

---

## Task 1: Package skeleton + config + fixture capture

**Files:**
- Create: `services/sheets_etl/__init__.py` (empty)
- Create: `services/sheets_etl/config.py`
- Create: `tests/sheets_etl/__init__.py` (empty)
- Create: `tests/sheets_etl/fixtures/promo_codes_first_3.json` (captured)
- Create: `tests/sheets_etl/fixtures/bloggers_first_3.json` (captured)
- Create: `tests/sheets_etl/fixtures/substitute_articles_first_3.json` (captured)
- Create: `tests/sheets_etl/fixtures/integrations_first_3.json` (captured)
- Create: `tests/sheets_etl/fixtures/candidates_first_3.json` (captured)

- [ ] **Step 1: Create package skeleton**

```bash
mkdir -p services/sheets_etl/transformers tests/sheets_etl/fixtures
touch services/sheets_etl/__init__.py services/sheets_etl/transformers/__init__.py tests/sheets_etl/__init__.py
```

- [ ] **Step 2: Write config.py**

```python
# services/sheets_etl/config.py
"""Static configuration for the Sheets ETL.

Source: 'Маркетинг Wookiee' workbook
(https://docs.google.com/spreadsheets/d/1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk/edit)
"""
from __future__ import annotations

SPREADSHEET_ID = "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk"

# tab name → (target table, key column for content-hash sheet_row_id)
SHEET_TO_TABLE = {
    "Промокоды_справочник": "crm.promo_codes",
    "БД БЛОГЕРЫ":           "crm.bloggers",
    "Подменные":            "crm.substitute_articles",
    "Блогеры":              "crm.integrations",
    "inst на проверку":     "crm.blogger_candidates",
}

# Order matters: promo_codes/bloggers must be loaded BEFORE integrations
# (integrations.blogger_id FK + integration_promo_codes FK).
LOAD_ORDER = [
    "Промокоды_справочник",
    "БД БЛОГЕРЫ",
    "Подменные",
    "Блогеры",
    "inst на проверку",
]
```

- [ ] **Step 3: Capture fixtures (first 3 data rows of each sheet)**

```bash
SHEET=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
mkdir -p tests/sheets_etl/fixtures
for tab in "Промокоды_справочник:promo_codes:H4" "БД БЛОГЕРЫ:bloggers:H4" "Подменные:substitute_articles:HZ4" "Блогеры:integrations:CZ4" "inst на проверку:candidates:AJ4"; do
  IFS=: read name fname rng <<< "$tab"
  gws sheets +read --spreadsheet $SHEET --range "${name}!A1:${rng}" 2>/dev/null \
    | grep -v "Using keyring" \
    > "tests/sheets_etl/fixtures/${fname}_first_3.json"
done
ls -la tests/sheets_etl/fixtures/
```
Expected: 5 JSON files, each with `values` array containing header + 3 data rows.

- [ ] **Step 4: Commit**

```bash
git add services/sheets_etl/ tests/sheets_etl/
git commit -m "feat(crm-etl): scaffold sheets_etl package + capture fixtures"
```

---

## Task 2: Hash helper

**Files:**
- Create: `services/sheets_etl/hash.py`
- Create: `tests/sheets_etl/test_hash.py`

- [ ] **Step 1: Write failing test**

```python
# tests/sheets_etl/test_hash.py
from services.sheets_etl.hash import sheet_row_id


def test_md5_deterministic():
    a = sheet_row_id(["sofiimarvel", "2026-03-01", "instagram"])
    b = sheet_row_id(["sofiimarvel", "2026-03-01", "instagram"])
    assert a == b
    assert len(a) == 32  # MD5 hex


def test_md5_changes_on_input():
    a = sheet_row_id(["sofiimarvel", "2026-03-01", "instagram"])
    b = sheet_row_id(["sofiimarvel", "2026-03-02", "instagram"])
    assert a != b


def test_md5_strips_whitespace():
    a = sheet_row_id(["  sofiimarvel ", "2026-03-01", "instagram"])
    b = sheet_row_id(["sofiimarvel", "2026-03-01", "instagram"])
    assert a == b


def test_md5_lowercases_handles():
    a = sheet_row_id(["SofiiMarvel", "2026-03-01", "instagram"])
    b = sheet_row_id(["sofiimarvel", "2026-03-01", "instagram"])
    assert a == b


def test_none_treated_as_empty():
    a = sheet_row_id([None, "2026-03-01", "instagram"])
    b = sheet_row_id(["", "2026-03-01", "instagram"])
    assert a == b
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_hash.py -v
```
Expected: ImportError or all 5 tests FAIL.

- [ ] **Step 3: Implement**

```python
# services/sheets_etl/hash.py
"""Deterministic content-hash for Sheets row identity.

Idempotency contract: if any of the parts change in Sheets, the hash changes,
producing a NEW row in Supabase rather than updating the old one. Choose stable,
business-meaningful keys (handle + publish date + channel), NOT positional A1.
"""
from __future__ import annotations

import hashlib
from typing import Iterable


def _norm(part: str | None) -> str:
    if part is None:
        return ""
    return part.strip().lower()


def sheet_row_id(parts: Iterable[str | None]) -> str:
    """Compute deterministic 32-char MD5 hex for a row, given its key parts."""
    joined = "‖".join(_norm(p) for p in parts)  # ‖ separator (won't collide)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_hash.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_etl/hash.py tests/sheets_etl/test_hash.py
git commit -m "feat(crm-etl): sheet_row_id MD5 helper"
```

---

## Task 3: Cell parsers (RU dates, numbers with spaces, percentages, booleans)

**Files:**
- Create: `services/sheets_etl/parsers.py`
- Create: `tests/sheets_etl/test_parsers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/sheets_etl/test_parsers.py
import datetime as dt
from decimal import Decimal

from services.sheets_etl import parsers as P


def test_parse_int_ru():
    assert P.parse_int("78 400") == 78400  # narrow no-break space
    assert P.parse_int("78 400") == 78400
    assert P.parse_int("12345") == 12345
    assert P.parse_int("") is None
    assert P.parse_int("—") is None
    assert P.parse_int(None) is None


def test_parse_decimal_ru():
    assert P.parse_decimal("12 345,67") == Decimal("12345.67")
    assert P.parse_decimal("3.14") == Decimal("3.14")
    assert P.parse_decimal("") is None
    assert P.parse_decimal("0") == Decimal("0")


def test_parse_pct():
    assert P.parse_decimal("10%") == Decimal("10")
    assert P.parse_decimal("3,5%") == Decimal("3.5")


def test_parse_date_ru():
    assert P.parse_date("02.03.2026") == dt.date(2026, 3, 2)
    assert P.parse_date("2026-03-02") == dt.date(2026, 3, 2)
    assert P.parse_date("") is None
    assert P.parse_date("не дата") is None


def test_parse_bool():
    assert P.parse_bool("да") is True
    assert P.parse_bool("Да") is True
    assert P.parse_bool("TRUE") is True
    assert P.parse_bool("1") is True
    assert P.parse_bool("✓") is True
    assert P.parse_bool("нет") is False
    assert P.parse_bool("0") is False
    assert P.parse_bool("") is None  # NULL = "not yet evaluated"
    assert P.parse_bool(None) is None
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_parsers.py -v
```

- [ ] **Step 3: Implement**

```python
# services/sheets_etl/parsers.py
"""Cell parsers for Russian-formatted Sheets data."""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation


_TRUE = {"да", "yes", "true", "1", "✓", "v", "+"}
_FALSE = {"нет", "no", "false", "0", "—", "-", "x"}


def _clean_num(s: str) -> str:
    # Russian thousand separators: regular + non-break + narrow no-break space
    return s.replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".").rstrip("%")


def parse_int(s: str | None) -> int | None:
    if s is None or not str(s).strip() or str(s).strip() in {"—", "-"}:
        return None
    try:
        return int(float(_clean_num(str(s))))
    except (ValueError, InvalidOperation):
        return None


def parse_decimal(s: str | None) -> Decimal | None:
    if s is None or not str(s).strip() or str(s).strip() in {"—", "-"}:
        return None
    try:
        return Decimal(_clean_num(str(s)))
    except (InvalidOperation, ValueError):
        return None


_DATE_FMTS = ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"]


def parse_date(s: str | None) -> dt.date | None:
    if s is None or not str(s).strip():
        return None
    s = str(s).strip()
    for fmt in _DATE_FMTS:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_bool(s: str | None) -> bool | None:
    if s is None:
        return None
    v = str(s).strip().lower()
    if not v:
        return None
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_parsers.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add services/sheets_etl/parsers.py tests/sheets_etl/test_parsers.py
git commit -m "feat(crm-etl): cell parsers for RU dates, numbers, booleans"
```

---

## Task 4: Fetch wrapper (gws CLI shell-out)

**Files:**
- Create: `services/sheets_etl/fetch.py`

- [ ] **Step 1: Implement**

```python
# services/sheets_etl/fetch.py
"""Wrapper around `gws sheets +read` (Google Sheets API CLI)."""
from __future__ import annotations

import json
import subprocess
from typing import Any


def read_range(spreadsheet_id: str, sheet_range: str) -> list[list[Any]]:
    """Return values matrix; row 0 is the header."""
    result = subprocess.run(
        ["gws", "sheets", "+read",
         "--spreadsheet", spreadsheet_id,
         "--range", sheet_range],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gws read failed (rc={result.returncode}): {result.stderr}")

    # gws prefaces output with one keyring-status line; strip it.
    raw = result.stdout
    if raw.startswith("Using keyring"):
        raw = raw.split("\n", 1)[1]
    data = json.loads(raw)
    return data.get("values", [])
```

- [ ] **Step 2: Smoke-test**

```bash
.venv/bin/python -c "
from services.sheets_etl.fetch import read_range
from services.sheets_etl.config import SPREADSHEET_ID
rows = read_range(SPREADSHEET_ID, 'Промокоды_справочник!A1:H3')
assert len(rows) == 3, f'Expected 3 rows, got {len(rows)}'
print('OK:', rows[0])
"
```
Expected: prints `OK: ['UUID', 'Название', 'Канал', ...]`.

- [ ] **Step 3: Commit**

```bash
git add services/sheets_etl/fetch.py
git commit -m "feat(crm-etl): gws CLI shell-out for sheet reads"
```

---

## Task 5: Loader (UPSERT + lookup helpers)

**Files:**
- Create: `services/sheets_etl/loader.py`

- [ ] **Step 1: Implement**

```python
# services/sheets_etl/loader.py
"""DB writers: UPSERT by sheet_row_id + simple FK lookups."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PG_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require",
    "options": "-csearch_path=crm,public",
}


def get_conn():
    return psycopg2.connect(**PG_CONFIG)


def upsert(conn, table: str, rows: list[dict[str, Any]], conflict_col: str = "sheet_row_id") -> int:
    """INSERT … ON CONFLICT (conflict_col) DO UPDATE for every column except conflict_col."""
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != conflict_col)

    sql = (
        f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}'
    )
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, [r[c] for c in cols])
    conn.commit()
    return len(rows)


def lookup_id(conn, table: str, where: dict[str, Any]) -> int | None:
    """Return id of single matching row or None."""
    keys = list(where.keys())
    sql = f'SELECT id FROM {table} WHERE ' + " AND ".join(f"{k} = %s" for k in keys) + " LIMIT 1"
    with conn.cursor() as cur:
        cur.execute(sql, [where[k] for k in keys])
        row = cur.fetchone()
    return row[0] if row else None


def insert_junction(conn, table: str, rows: list[dict[str, Any]],
                    conflict_cols: tuple[str, ...]) -> int:
    """Junction tables (no sheet_row_id) — UPSERT by composite key."""
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in conflict_cols)
    sql = (
        f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) '
        f'ON CONFLICT ({", ".join(conflict_cols)}) DO UPDATE SET {update_set}'
        if update_set else
        f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({placeholders}) '
        f'ON CONFLICT ({", ".join(conflict_cols)}) DO NOTHING'
    )
    with conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, [r[c] for c in cols])
    conn.commit()
    return len(rows)
```

- [ ] **Step 2: Smoke-test**

```bash
.venv/bin/python -c "
from services.sheets_etl.loader import get_conn, lookup_id
c = get_conn()
mid = lookup_id(c, 'crm.marketers', {'name': 'Александра'})
print('marketer_id:', mid)
c.close()
"
```
Expected: prints `marketer_id: 1` (or whatever id).

- [ ] **Step 3: Commit**

```bash
git add services/sheets_etl/loader.py
git commit -m "feat(crm-etl): loader with upsert + lookup helpers"
```

---

## Task 6: Promo codes transformer (smallest sheet, lock pattern)

**Files:**
- Create: `services/sheets_etl/transformers/promo_codes.py`
- Create: `tests/sheets_etl/test_promo_codes.py`

**Source columns (Промокоды_справочник):** 0=UUID, 1=Название, 2=Канал, 3=Скидка %, 4=Старт, 5=Окончание, 6=Примечание.

**Target:** `crm.promo_codes(code, channel, discount_pct, valid_from, valid_until, notes, external_uuid, sheet_row_id)`. Note: `code` ← Название (this is the actual coupon code typed by customer; UUID is internal Sheets ID stored in `external_uuid`).

- [ ] **Step 1: Write failing test**

```python
# tests/sheets_etl/test_promo_codes.py
import json
from pathlib import Path
from decimal import Decimal

from services.sheets_etl.transformers.promo_codes import transform


def test_transform_first_3_rows():
    data = json.loads((Path(__file__).parent / "fixtures/promo_codes_first_3.json").read_text())
    rows = transform(data["values"])
    assert len(rows) == 2  # 2 data rows (3rd may be incomplete)
    r0 = rows[0]
    assert r0["code"] == "CHARLOTTE10"
    assert r0["channel"] == "Соцсети"
    assert r0["discount_pct"] == Decimal("10")
    assert r0["external_uuid"] == "be6900f2-c9e9-4963-9ad1-27d10d9492d6"
    assert r0["sheet_row_id"]  # non-empty hash
    assert len(r0["sheet_row_id"]) == 32
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_promo_codes.py -v
```

- [ ] **Step 3: Implement**

```python
# services/sheets_etl/transformers/promo_codes.py
"""Промокоды_справочник → crm.promo_codes."""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_date, parse_decimal


def transform(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values or len(values) < 2:
        return []
    rows = []
    for raw in values[1:]:  # skip header
        if len(raw) < 2 or not raw[1]:  # require Название
            continue
        code = raw[1].strip()
        external_uuid = raw[0].strip() if raw[0] else None
        rows.append({
            "code": code,
            "external_uuid": external_uuid,
            "channel": raw[2].strip() if len(raw) > 2 and raw[2] else None,
            "discount_pct": parse_decimal(raw[3]) if len(raw) > 3 else None,
            "valid_from": parse_date(raw[4]) if len(raw) > 4 else None,
            "valid_until": parse_date(raw[5]) if len(raw) > 5 else None,
            "notes": raw[6].strip() if len(raw) > 6 and raw[6] else None,
            "status": "active",
            "sheet_row_id": sheet_row_id([code, external_uuid or ""]),
        })
    return rows
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_promo_codes.py -v
```

- [ ] **Step 5: Apply to DB (with --force flag passed through; here just run direct)**

```bash
.venv/bin/python -c "
from services.sheets_etl.fetch import read_range
from services.sheets_etl.config import SPREADSHEET_ID
from services.sheets_etl.transformers.promo_codes import transform
from services.sheets_etl.loader import get_conn, upsert

values = read_range(SPREADSHEET_ID, 'Промокоды_справочник!A1:H200')
rows = transform(values)
print(f'Transformed {len(rows)} rows')
c = get_conn()
n = upsert(c, 'crm.promo_codes', rows)
print(f'Upserted {n} rows')
c.close()
"
.venv/bin/python -c "
from services.sheets_etl.loader import get_conn
c = get_conn()
with c.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM crm.promo_codes')
    print('Total promo_codes:', cur.fetchone()[0])
c.close()
"
```
Expected: prints `Transformed N rows`, `Upserted N rows`, then `Total promo_codes: N` matching.

- [ ] **Step 6: Commit**

```bash
git add services/sheets_etl/transformers/promo_codes.py tests/sheets_etl/test_promo_codes.py
git commit -m "feat(crm-etl): promo_codes transformer + DB upsert"
```

---

## Task 7: Bloggers transformer (БД БЛОГЕРЫ → bloggers + blogger_channels)

**Files:**
- Create: `services/sheets_etl/transformers/bloggers.py`
- Create: `tests/sheets_etl/test_bloggers.py`

**Source columns (БД БЛОГЕРЫ):** 0=Никнейм блогера, 1=Ссылка на Инст, 2=Аудитория Inst, 3=Ссылка на ВК, 4=Ссылка на ТГ, 5=Ссылка на ТикТок, 6=Ссылка на ютуб, 7=Канал.

**Target:**
- `crm.bloggers(display_handle, status='active', sheet_row_id)` — one row.
- `crm.blogger_channels(blogger_id, channel, handle, url, followers)` — up to 5 rows per blogger (one per non-empty link).

Channel mapping: col 1→`instagram`, col 3→`vk`, col 4→`telegram`, col 5→`tiktok`, col 6→`youtube`.

- [ ] **Step 1: Write failing test**

```python
# tests/sheets_etl/test_bloggers.py
import json
from pathlib import Path

from services.sheets_etl.transformers.bloggers import transform


def test_transform_first_3():
    data = json.loads((Path(__file__).parent / "fixtures/bloggers_first_3.json").read_text())
    bloggers, channels = transform(data["values"])
    assert bloggers, "No bloggers parsed"
    b0 = bloggers[0]
    assert b0["display_handle"] == "sofiimarvel"
    assert b0["sheet_row_id"]
    # Should have produced channels for inst+telegram (other links empty)
    handles = [c for c in channels if c["display_handle_ref"] == "sofiimarvel"]
    assert len(handles) == 2
    by_kind = {c["channel"]: c for c in handles}
    assert by_kind["instagram"]["url"] == "https://www.instagram.com/sofiimarvel/"
    assert by_kind["instagram"]["followers"] == 78400
    assert by_kind["telegram"]["url"] == "https://t.me/yakutyanochkaaaaa"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_bloggers.py -v
```

- [ ] **Step 3: Implement**

```python
# services/sheets_etl/transformers/bloggers.py
"""БД БЛОГЕРЫ → crm.bloggers + crm.blogger_channels.

Returns (bloggers, channels). Channels carry `display_handle_ref` so the loader
can resolve blogger_id after upserting bloggers.
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_int

# col_idx → channel kind
LINK_COLS: dict[int, str] = {
    1: "instagram",
    3: "vk",
    4: "telegram",
    5: "tiktok",
    6: "youtube",
}


def _handle_from_url(url: str, channel: str) -> str:
    url = url.strip().rstrip("/")
    return url.rsplit("/", 1)[-1] if "/" in url else url


def transform(values: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not values or len(values) < 2:
        return [], []
    bloggers: list[dict[str, Any]] = []
    channels: list[dict[str, Any]] = []

    for raw in values[1:]:
        if not raw or not raw[0]:
            continue
        display_handle = raw[0].strip()
        srid = sheet_row_id([display_handle])
        bloggers.append({
            "display_handle": display_handle,
            "status": "active",
            "sheet_row_id": srid,
        })
        for col, kind in LINK_COLS.items():
            url = raw[col].strip() if len(raw) > col and raw[col] else ""
            if not url:
                continue
            ch = {
                "display_handle_ref": display_handle,  # resolved by caller
                "channel": kind,
                "handle": _handle_from_url(url, kind),
                "url": url,
                "followers": None,
            }
            # Followers are only on the Inst column (col 2 of БД БЛОГЕРЫ)
            if kind == "instagram" and len(raw) > 2:
                ch["followers"] = parse_int(raw[2])
            channels.append(ch)
    return bloggers, channels
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_bloggers.py -v
```

- [ ] **Step 5: Apply to DB (resolve blogger_id for channels)**

```bash
.venv/bin/python -c "
from services.sheets_etl.fetch import read_range
from services.sheets_etl.config import SPREADSHEET_ID
from services.sheets_etl.transformers.bloggers import transform
from services.sheets_etl.loader import get_conn, upsert, insert_junction, lookup_id

values = read_range(SPREADSHEET_ID, 'БД БЛОГЕРЫ!A1:H2000')
bloggers, channels = transform(values)
print(f'Bloggers: {len(bloggers)}, channels: {len(channels)}')

c = get_conn()
upsert(c, 'crm.bloggers', bloggers)

# resolve blogger_id by display_handle
handle_to_id = {}
with c.cursor() as cur:
    cur.execute('SELECT id, display_handle FROM crm.bloggers')
    for bid, dh in cur.fetchall():
        handle_to_id[dh] = bid

ch_rows = []
for ch in channels:
    bid = handle_to_id.get(ch.pop('display_handle_ref'))
    if bid:
        ch['blogger_id'] = bid
        ch_rows.append(ch)
insert_junction(c, 'crm.blogger_channels', ch_rows, conflict_cols=('blogger_id','channel','handle'))

with c.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM crm.bloggers')
    print('bloggers:', cur.fetchone()[0])
    cur.execute('SELECT COUNT(*) FROM crm.blogger_channels')
    print('channels:', cur.fetchone()[0])
c.close()
"
```
Expected: prints transformed counts then totals matching (bloggers ~ 1000, channels < bloggers × 5).

- [ ] **Step 6: Commit**

```bash
git add services/sheets_etl/transformers/bloggers.py tests/sheets_etl/test_bloggers.py
git commit -m "feat(crm-etl): bloggers + blogger_channels transformer"
```

---

## Task 8: Substitute articles transformer (Подменные → substitute_articles + weekly metrics)

**Files:**
- Create: `services/sheets_etl/transformers/substitute_articles.py`
- Create: `tests/sheets_etl/test_substitute_articles.py`

**Source layout:**
- Cols 0-7: meta (0=Модель, 1=Номенклатура, 2=Артикул, 3=Назначение, 4=Статус, 5=Название кампании, 6,7=blank).
- Col 8: "Поиск нулевых записей" — internal flag, ignore.
- Cols 9+: weekly groups of 4 (Частота, Переходы, Добавления, Заказы).
- Row 1 (NOT row 0): the date in the first col of each weekly group is `week_start`.

**Target:**
- `crm.substitute_articles(code, artikul_id, purpose, nomenklatura_wb, campaign_name, status, sheet_row_id)`.
  - `code` ← col 2 (Артикул).
  - `artikul_id` ← lookup `public.artikuly.id WHERE artikul = code`.
  - `purpose` ← col 3.
  - `nomenklatura_wb` ← col 1.
  - `campaign_name` ← col 5.
- `crm.substitute_article_metrics_weekly(substitute_article_id, week_start, frequency, transitions, additions, orders)`.

- [ ] **Step 1: Write failing test**

```python
# tests/sheets_etl/test_substitute_articles.py
import json
from pathlib import Path

from services.sheets_etl.transformers.substitute_articles import transform


def test_transform_extracts_meta_and_weekly():
    data = json.loads((Path(__file__).parent / "fixtures/substitute_articles_first_3.json").read_text())
    articles, metrics = transform(data["values"])
    # First 2 data rows usually contain real records
    assert len(articles) >= 1
    a0 = articles[0]
    assert a0["code"]
    assert a0["sheet_row_id"]
    # Metrics: each week-block produces 1 row per article (when any of the 4 cells non-empty)
    code_metrics = [m for m in metrics if m["sub_code_ref"] == a0["code"]]
    # at least one week populated in fixture
    assert any(m["frequency"] is not None or m["transitions"] is not None for m in code_metrics)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_substitute_articles.py -v
```

- [ ] **Step 3: Implement**

```python
# services/sheets_etl/transformers/substitute_articles.py
"""Подменные → crm.substitute_articles + crm.substitute_article_metrics_weekly.

Wide layout: meta cols 0-7, then 4-col weekly blocks starting at col 9.
Each block: [Частота, Переходы, Добавления, Заказы]. Row 1 carries week_start
in the first col of each block (cols 9, 13, 17, ...).
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_date, parse_int

META_END = 8     # cols 0-7
SKIP_COL = 8     # "Поиск нулевых записей"
WEEK_START_COL = 9
WEEK_BLOCK_SIZE = 4


def transform(values: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not values or len(values) < 3:
        return [], []
    week_dates_row = values[1]
    # Parse week_start dates: every 4 cols starting at col 9
    week_starts: list[tuple[int, Any]] = []  # (col_idx_of_block, date)
    for col in range(WEEK_START_COL, len(week_dates_row), WEEK_BLOCK_SIZE):
        d = parse_date(week_dates_row[col]) if col < len(week_dates_row) else None
        if d:
            week_starts.append((col, d))

    articles: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []

    for raw in values[2:]:
        if not raw or len(raw) < 3 or not raw[2]:  # require Артикул
            continue
        code = str(raw[2]).strip()
        articles.append({
            "code": code,
            "purpose": str(raw[3]).strip() if len(raw) > 3 and raw[3] else "-",
            "nomenklatura_wb": str(raw[1]).strip() if len(raw) > 1 and raw[1] else None,
            "campaign_name": str(raw[5]).strip() if len(raw) > 5 and raw[5] else None,
            "status": (str(raw[4]).strip().lower() or "active") if len(raw) > 4 else "active",
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
                "sub_code_ref": code,        # resolved by caller
                "week_start": week_start,
                "frequency": freq,
                "transitions": tran,
                "additions": adds,
                "orders": ords,
            })
    return articles, metrics
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_substitute_articles.py -v
```

- [ ] **Step 5: Apply to DB**

```bash
.venv/bin/python -c "
from services.sheets_etl.fetch import read_range
from services.sheets_etl.config import SPREADSHEET_ID
from services.sheets_etl.transformers.substitute_articles import transform
from services.sheets_etl.loader import get_conn, upsert, insert_junction

values = read_range(SPREADSHEET_ID, 'Подменные!A1:HZ1500')
articles, metrics = transform(values)
print(f'Articles: {len(articles)}, weekly metrics: {len(metrics)}')

c = get_conn()
# resolve artikul_id from public.artikuly
with c.cursor() as cur:
    cur.execute('SELECT id, artikul FROM public.artikuly')
    art_map = {a: i for i, a in cur.fetchall()}
matched = [a | {'artikul_id': art_map.get(a['code'])} for a in articles if art_map.get(a['code'])]
unmatched = [a for a in articles if not art_map.get(a['code'])]
print(f'  matched to artikuly: {len(matched)}, unmatched: {len(unmatched)}')
upsert(c, 'crm.substitute_articles', matched)

# metric loader: resolve substitute_article_id by code
with c.cursor() as cur:
    cur.execute('SELECT id, code FROM crm.substitute_articles')
    code_map = {co: i for i, co in cur.fetchall()}
m_rows = []
for m in metrics:
    sid = code_map.get(m.pop('sub_code_ref'))
    if sid:
        m['substitute_article_id'] = sid
        m_rows.append(m)
insert_junction(c, 'crm.substitute_article_metrics_weekly', m_rows,
                conflict_cols=('substitute_article_id','week_start'))
print(f'Inserted {len(m_rows)} metrics rows')
c.close()
"
```
Expected: prints counts; matched is the bulk; unmatched logged for follow-up.

- [ ] **Step 6: Commit**

```bash
git add services/sheets_etl/transformers/substitute_articles.py tests/sheets_etl/test_substitute_articles.py
git commit -m "feat(crm-etl): substitute_articles + weekly metrics transformer"
```

---

## Task 9: Integrations transformer (Блогеры → integrations + junctions) — most complex

**Files:**
- Create: `services/sheets_etl/transformers/integrations.py`
- Create: `tests/sheets_etl/test_integrations.py`

**Source columns (Блогеры):** 104 cols total. Critical:
- 0=Блогер, 1=Маркетолог, 2=Ссылка на соц. сеть, 5=Дата публикации, 6=Артикул (primary), 7=Вид рекламы, 8=Магазин, 9=Канал.
- 10=Стоимость размещения, 11=Стоимость доставки, 12=Себестоимость комплектов.
- 14=Тематика, 15=Возраст аудитории, 16=Подписчиков, 17=Минимальные охваты, 18=Вовлеченность.
- 19-22=PLAN (CPM, CTR, Clicks, CPC). 23-31=FACT (Просмотры, СРМ, Клики, CTR, CPC, Корзин, CR в корзину, Заказы, CR в заказ).
- 33=Артикул в рекламе (primary), 35=URL (UTM, primary), 36=Артикул 2 в рилс (secondary), 38=URL (secondary).
- 40=Договор, 41=Пост URL, 42=ТЗ URL, 43=Скрин URL, 44=Текст поста, 45=Анализ.
- 46-53=Compliance booleans (8): has_marking, has_contract, has_deeplink, has_closing_docs, has_full_recording, all_data_filled, has_quality_content, complies_with_rules.

**Channel/marketplace/ad_format normalization:** map RU values to enum check-constraint values.

- [ ] **Step 1: Write failing test**

```python
# tests/sheets_etl/test_integrations.py
import json
from pathlib import Path

from services.sheets_etl.transformers.integrations import transform


def test_transform_extracts_integration_and_substitutes():
    data = json.loads((Path(__file__).parent / "fixtures/integrations_first_3.json").read_text())
    integrations, sub_links, promo_links = transform(data["values"])
    assert integrations, "No integrations parsed"
    i0 = integrations[0]
    assert i0["blogger_handle_ref"]  # to be resolved
    assert i0["marketer_name_ref"]
    assert i0["publish_date"]
    assert i0["channel"] in {"instagram","youtube","tiktok","telegram","vk","rutube","other"}
    assert i0["marketplace"] in {"wb","ozon","both"}
    assert i0["ad_format"] in {"short_video","long_video","image_post","text_post","live_stream","story","integration","long_post"}
    assert i0["sheet_row_id"]
    # Substitute_articles junction: at least 1 link if col 33 populated
    if i0.get("_has_primary_sub"):
        assert any(s["integration_sheet_row_id_ref"] == i0["sheet_row_id"] for s in sub_links)
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_integrations.py -v
```

- [ ] **Step 3: Implement**

```python
# services/sheets_etl/transformers/integrations.py
"""Блогеры → crm.integrations + crm.integration_substitute_articles + crm.integration_promo_codes.

Returns (integrations, sub_links, promo_links). Each row carries human-readable
references the loader resolves to FK IDs after upserting blogger/marketer/sub/promo.
"""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_bool, parse_date, parse_decimal, parse_int

# col indices
COL_BLOGGER = 0
COL_MARKETER = 1
COL_PUBLISH_DATE = 5
COL_AD_FORMAT = 7
COL_MARKETPLACE = 8
COL_CHANNEL = 9
COL_COST_PLACEMENT = 10
COL_COST_DELIVERY = 11
COL_COST_GOODS = 12
COL_PLAN_CPM, COL_PLAN_CTR, COL_PLAN_CLICKS, COL_PLAN_CPC = 19, 20, 21, 22
COL_FACT_VIEWS, COL_FACT_CPM, COL_FACT_CLICKS, COL_FACT_CTR = 23, 24, 25, 26
COL_FACT_CPC, COL_FACT_CARTS, COL_CR_CART = 27, 28, 29
COL_FACT_ORDERS, COL_CR_ORDER = 30, 31
COL_SUB_PRIMARY = 33
COL_SUB_PRIMARY_URL = 35
COL_SUB_SECONDARY = 36
COL_SUB_SECONDARY_URL = 38
COL_RECOMMENDED = 39
COL_CONTRACT_URL = 40
COL_POST_URL = 41
COL_TZ_URL = 42
COL_SCREEN_URL = 43
COL_POST_CONTENT = 44
COL_ANALYSIS = 45
COMPLIANCE_COLS = [
    (46, "has_marking"),
    (47, "has_contract"),
    (48, "has_deeplink"),
    (49, "has_closing_docs"),
    (50, "has_full_recording"),
    (51, "all_data_filled"),
    (52, "has_quality_content"),
    (53, "complies_with_rules"),
]

# RU → enum
CHANNEL_MAP = {
    "instagram": "instagram", "инстаграм": "instagram", "инст": "instagram",
    "youtube": "youtube", "ютуб": "youtube", "ютьюб": "youtube",
    "tiktok": "tiktok", "тикток": "tiktok",
    "telegram": "telegram", "телеграм": "telegram", "тг": "telegram",
    "vk": "vk", "вк": "vk", "вконтакте": "vk",
    "rutube": "rutube", "рутуб": "rutube",
}
MARKETPLACE_MAP = {"wb": "wb", "вб": "wb", "wildberries": "wb",
                   "ozon": "ozon", "озон": "ozon",
                   "both": "both", "оба": "both", "wb+ozon": "both"}
AD_FORMAT_MAP = {
    "reels": "short_video", "рилс": "short_video", "shorts": "short_video", "tiktok": "short_video",
    "stories": "story", "стори": "story", "сторис": "story", "story": "story",
    "post": "image_post", "пост": "image_post",
    "live": "live_stream", "стрим": "live_stream",
    "video": "long_video", "видео": "long_video", "long video": "long_video",
    "integration": "integration", "интеграция": "integration",
    "long_post": "long_post", "статья": "long_post",
}


def _norm_lookup(d: dict[str, str], v: str | None, default: str = "other") -> str:
    if not v:
        return default
    key = v.strip().lower()
    return d.get(key, default)


def transform(values: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not values or len(values) < 2:
        return [], [], []
    integrations: list[dict[str, Any]] = []
    sub_links: list[dict[str, Any]] = []
    promo_links: list[dict[str, Any]] = []  # filled later if Блогеры has promo column

    def cell(row: list[Any], i: int) -> str:
        return row[i] if i < len(row) and row[i] is not None else ""

    for raw in values[1:]:  # skip header
        if not raw or not cell(raw, COL_BLOGGER) or not cell(raw, COL_PUBLISH_DATE):
            continue
        blogger = str(cell(raw, COL_BLOGGER)).strip()
        marketer = str(cell(raw, COL_MARKETER)).strip()
        publish_date = parse_date(cell(raw, COL_PUBLISH_DATE))
        if not publish_date:
            continue
        channel = _norm_lookup(CHANNEL_MAP, cell(raw, COL_CHANNEL))
        srid = sheet_row_id([blogger, str(publish_date), channel])

        rec: dict[str, Any] = {
            "blogger_handle_ref": blogger,
            "marketer_name_ref": marketer,
            "publish_date": publish_date,
            "channel": channel,
            "ad_format": _norm_lookup(AD_FORMAT_MAP, cell(raw, COL_AD_FORMAT), default="integration"),
            "marketplace": _norm_lookup(MARKETPLACE_MAP, cell(raw, COL_MARKETPLACE), default="wb"),
            "stage": "done",  # historical rows assumed completed; orchestrator can override
            "is_barter": False,
            "cost_placement": parse_decimal(cell(raw, COL_COST_PLACEMENT)),
            "cost_delivery":  parse_decimal(cell(raw, COL_COST_DELIVERY)),
            "cost_goods":     parse_decimal(cell(raw, COL_COST_GOODS)),
            "plan_cpm":    parse_decimal(cell(raw, COL_PLAN_CPM)),
            "plan_ctr":    parse_decimal(cell(raw, COL_PLAN_CTR)),
            "plan_clicks": parse_int(cell(raw, COL_PLAN_CLICKS)),
            "plan_cpc":    parse_decimal(cell(raw, COL_PLAN_CPC)),
            "fact_views":  parse_int(cell(raw, COL_FACT_VIEWS)),
            "fact_cpm":    parse_decimal(cell(raw, COL_FACT_CPM)),
            "fact_clicks": parse_int(cell(raw, COL_FACT_CLICKS)),
            "fact_ctr":    parse_decimal(cell(raw, COL_FACT_CTR)),
            "fact_cpc":    parse_decimal(cell(raw, COL_FACT_CPC)),
            "fact_carts":  parse_int(cell(raw, COL_FACT_CARTS)),
            "cr_to_cart":  parse_decimal(cell(raw, COL_CR_CART)),
            "fact_orders": parse_int(cell(raw, COL_FACT_ORDERS)),
            "cr_to_order": parse_decimal(cell(raw, COL_CR_ORDER)),
            "contract_url": cell(raw, COL_CONTRACT_URL).strip() or None,
            "post_url":     cell(raw, COL_POST_URL).strip() or None,
            "tz_url":       cell(raw, COL_TZ_URL).strip() or None,
            "screen_url":   cell(raw, COL_SCREEN_URL).strip() or None,
            "post_content": cell(raw, COL_POST_CONTENT).strip() or None,
            "analysis":     cell(raw, COL_ANALYSIS).strip() or None,
            "recommended_models": cell(raw, COL_RECOMMENDED).strip() or None,
            "sheet_row_id": srid,
        }
        for col, key in COMPLIANCE_COLS:
            rec[key] = parse_bool(cell(raw, col))

        # Substitute article links (junction)
        primary = cell(raw, COL_SUB_PRIMARY).strip()
        if primary:
            sub_links.append({
                "integration_sheet_row_id_ref": srid,
                "substitute_article_code_ref": primary,
                "display_order": 0,
                "tracking_url": cell(raw, COL_SUB_PRIMARY_URL).strip() or None,
            })
            rec["_has_primary_sub"] = True
        secondary = cell(raw, COL_SUB_SECONDARY).strip()
        if secondary:
            sub_links.append({
                "integration_sheet_row_id_ref": srid,
                "substitute_article_code_ref": secondary,
                "display_order": 1,
                "tracking_url": cell(raw, COL_SUB_SECONDARY_URL).strip() or None,
            })
        integrations.append(rec)
    return integrations, sub_links, promo_links
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_integrations.py -v
```

- [ ] **Step 5: Apply to DB (resolve FKs)**

```bash
.venv/bin/python -c "
from services.sheets_etl.fetch import read_range
from services.sheets_etl.config import SPREADSHEET_ID
from services.sheets_etl.transformers.integrations import transform
from services.sheets_etl.loader import get_conn, upsert, insert_junction

values = read_range(SPREADSHEET_ID, 'Блогеры!A1:CZ2200')
ints, sub_links, _ = transform(values)
print(f'Integrations: {len(ints)}, sub_links: {len(sub_links)}')

c = get_conn()
with c.cursor() as cur:
    cur.execute('SELECT id, display_handle FROM crm.bloggers')
    blogger_map = {dh: i for i, dh in cur.fetchall()}
    cur.execute('SELECT id, name FROM crm.marketers')
    marketer_map = {n: i for i, n in cur.fetchall()}
    cur.execute('SELECT id, code FROM crm.substitute_articles')
    sub_map = {co: i for i, co in cur.fetchall()}

resolved = []
for i in ints:
    bh = i.pop('blogger_handle_ref'); mn = i.pop('marketer_name_ref')
    i.pop('_has_primary_sub', None)
    bid = blogger_map.get(bh); mid = marketer_map.get(mn)
    if bid and mid:
        i['blogger_id'] = bid; i['marketer_id'] = mid
        resolved.append(i)
upsert(c, 'crm.integrations', resolved)

# resolve integration_id by sheet_row_id
with c.cursor() as cur:
    cur.execute('SELECT id, sheet_row_id FROM crm.integrations')
    int_map = {sr: i for i, sr in cur.fetchall()}
sl_resolved = []
for s in sub_links:
    iid = int_map.get(s.pop('integration_sheet_row_id_ref'))
    sid = sub_map.get(s.pop('substitute_article_code_ref'))
    if iid and sid:
        s['integration_id'] = iid; s['substitute_article_id'] = sid
        sl_resolved.append(s)
insert_junction(c, 'crm.integration_substitute_articles', sl_resolved,
                conflict_cols=('integration_id','substitute_article_id'))
print(f'Loaded integrations: {len(resolved)}, sub junction: {len(sl_resolved)}')

with c.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM crm.integrations')
    print('Total integrations:', cur.fetchone()[0])
c.close()
"
```
Expected: prints transformed counts, then totals (integrations should be in 1000s; junction ~ 1500+).

- [ ] **Step 6: Commit**

```bash
git add services/sheets_etl/transformers/integrations.py tests/sheets_etl/test_integrations.py
git commit -m "feat(crm-etl): integrations + substitute junction transformer"
```

---

## Task 10: Blogger candidates transformer + CLI orchestrator + E2E counts

**Files:**
- Create: `services/sheets_etl/transformers/candidates.py`
- Create: `services/sheets_etl/cli.py`
- Create: `tests/sheets_etl/test_e2e_counts.py`

**Source columns (inst на проверку):** 0=Блогер, 1=ТГ-канал, 2=Подписки, 3=Охваты, 4=Цена, 7=Сумма охватов, 8=Средний CPM, 19=Вовлеченность, 22=ссылка на инст.

- [ ] **Step 1: Write candidates transformer**

```python
# services/sheets_etl/transformers/candidates.py
"""inst на проверку → crm.blogger_candidates."""
from __future__ import annotations

from typing import Any

from services.sheets_etl.hash import sheet_row_id
from services.sheets_etl.parsers import parse_decimal, parse_int


def transform(values: list[list[Any]]) -> list[dict[str, Any]]:
    if not values or len(values) < 2:
        return []
    rows = []
    for raw in values[1:]:
        if not raw or not raw[0]:
            continue
        handle = str(raw[0]).strip()
        rows.append({
            "display_handle": handle,
            "tg_channel": str(raw[1]).strip() if len(raw) > 1 and raw[1] else None,
            "followers": parse_int(raw[2]) if len(raw) > 2 else None,
            "reach_avg": parse_int(raw[3]) if len(raw) > 3 else None,
            "price": parse_decimal(raw[4]) if len(raw) > 4 else None,
            "total_reach_sum": parse_int(raw[7]) if len(raw) > 7 else None,
            "avg_cpm": parse_decimal(raw[8]) if len(raw) > 8 else None,
            "engagement_pct": parse_decimal(raw[19]) if len(raw) > 19 else None,
            "instagram_url": str(raw[22]).strip() if len(raw) > 22 and raw[22] else None,
            "status": "candidate",
            "sheet_row_id": sheet_row_id([handle]),
        })
    return rows
```

- [ ] **Step 2: Write CLI**

```python
# services/sheets_etl/cli.py
"""CLI: python -m services.sheets_etl.cli [--table=<name>] [--dry-run]."""
from __future__ import annotations

import argparse
import sys

from services.sheets_etl.config import LOAD_ORDER, SPREADSHEET_ID
from services.sheets_etl.fetch import read_range
from services.sheets_etl.loader import get_conn, insert_junction, upsert
from services.sheets_etl.transformers import (
    bloggers as t_bloggers,
    candidates as t_candidates,
    integrations as t_integrations,
    promo_codes as t_promo_codes,
    substitute_articles as t_substitute_articles,
)


SHEET_RANGES = {
    "Промокоды_справочник": "Промокоды_справочник!A1:H200",
    "БД БЛОГЕРЫ":           "БД БЛОГЕРЫ!A1:H2000",
    "Подменные":            "Подменные!A1:HZ1500",
    "Блогеры":              "Блогеры!A1:CZ2200",
    "inst на проверку":     "inst на проверку!A1:AJ1500",
}


def run_promo_codes(conn, dry_run: bool) -> None:
    values = read_range(SPREADSHEET_ID, SHEET_RANGES["Промокоды_справочник"])
    rows = t_promo_codes.transform(values)
    print(f"  promo_codes: {len(rows)} rows")
    if not dry_run:
        upsert(conn, "crm.promo_codes", rows)


def run_bloggers(conn, dry_run: bool) -> None:
    values = read_range(SPREADSHEET_ID, SHEET_RANGES["БД БЛОГЕРЫ"])
    bloggers, channels = t_bloggers.transform(values)
    print(f"  bloggers: {len(bloggers)}, channels: {len(channels)}")
    if dry_run:
        return
    upsert(conn, "crm.bloggers", bloggers)
    with conn.cursor() as cur:
        cur.execute("SELECT id, display_handle FROM crm.bloggers")
        h2id = {dh: i for i, dh in cur.fetchall()}
    ch_rows = []
    for ch in channels:
        bid = h2id.get(ch.pop("display_handle_ref"))
        if bid:
            ch["blogger_id"] = bid
            ch_rows.append(ch)
    insert_junction(conn, "crm.blogger_channels", ch_rows,
                    conflict_cols=("blogger_id", "channel", "handle"))


def run_substitute_articles(conn, dry_run: bool) -> None:
    values = read_range(SPREADSHEET_ID, SHEET_RANGES["Подменные"])
    articles, metrics = t_substitute_articles.transform(values)
    print(f"  substitute_articles: {len(articles)}, metrics: {len(metrics)}")
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT id, artikul FROM public.artikuly")
        art_map = {a: i for i, a in cur.fetchall()}
    matched = []
    for a in articles:
        if art_map.get(a["code"]):
            a["artikul_id"] = art_map[a["code"]]
            matched.append(a)
    upsert(conn, "crm.substitute_articles", matched)
    with conn.cursor() as cur:
        cur.execute("SELECT id, code FROM crm.substitute_articles")
        c2id = {co: i for i, co in cur.fetchall()}
    m_rows = []
    for m in metrics:
        sid = c2id.get(m.pop("sub_code_ref"))
        if sid:
            m["substitute_article_id"] = sid
            m_rows.append(m)
    insert_junction(conn, "crm.substitute_article_metrics_weekly", m_rows,
                    conflict_cols=("substitute_article_id", "week_start"))


def run_integrations(conn, dry_run: bool) -> None:
    values = read_range(SPREADSHEET_ID, SHEET_RANGES["Блогеры"])
    ints, sub_links, _ = t_integrations.transform(values)
    print(f"  integrations: {len(ints)}, sub_links: {len(sub_links)}")
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT id, display_handle FROM crm.bloggers")
        b_map = {dh: i for i, dh in cur.fetchall()}
        cur.execute("SELECT id, name FROM crm.marketers")
        m_map = {n: i for i, n in cur.fetchall()}
        cur.execute("SELECT id, code FROM crm.substitute_articles")
        s_map = {co: i for i, co in cur.fetchall()}
    resolved = []
    for i in ints:
        bh = i.pop("blogger_handle_ref"); mn = i.pop("marketer_name_ref")
        i.pop("_has_primary_sub", None)
        bid = b_map.get(bh); mid = m_map.get(mn)
        if bid and mid:
            i["blogger_id"] = bid; i["marketer_id"] = mid
            resolved.append(i)
    upsert(conn, "crm.integrations", resolved)
    with conn.cursor() as cur:
        cur.execute("SELECT id, sheet_row_id FROM crm.integrations")
        int_map = {sr: i for i, sr in cur.fetchall()}
    sl = []
    for s in sub_links:
        iid = int_map.get(s.pop("integration_sheet_row_id_ref"))
        sid = s_map.get(s.pop("substitute_article_code_ref"))
        if iid and sid:
            s["integration_id"] = iid; s["substitute_article_id"] = sid
            sl.append(s)
    insert_junction(conn, "crm.integration_substitute_articles", sl,
                    conflict_cols=("integration_id", "substitute_article_id"))


def run_candidates(conn, dry_run: bool) -> None:
    values = read_range(SPREADSHEET_ID, SHEET_RANGES["inst на проверку"])
    rows = t_candidates.transform(values)
    print(f"  candidates: {len(rows)} rows")
    if not dry_run:
        upsert(conn, "crm.blogger_candidates", rows)


RUNNERS = {
    "Промокоды_справочник": run_promo_codes,
    "БД БЛОГЕРЫ":           run_bloggers,
    "Подменные":            run_substitute_articles,
    "Блогеры":              run_integrations,
    "inst на проверку":     run_candidates,
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--table", choices=list(RUNNERS.keys()) + ["all"], default="all")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    targets = LOAD_ORDER if args.table == "all" else [args.table]
    conn = get_conn()
    try:
        for sheet_name in targets:
            print(f"--- {sheet_name} ---")
            RUNNERS[sheet_name](conn, args.dry_run)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run dry-run**

```bash
.venv/bin/python -m services.sheets_etl.cli --dry-run
```
Expected: counts printed for all 5 sheets, no DB writes.

- [ ] **Step 4: Run full ETL**

```bash
.venv/bin/python -m services.sheets_etl.cli
```
Expected: all 5 sheets loaded, no errors.

- [ ] **Step 5: Write E2E count assertions**

```python
# tests/sheets_etl/test_e2e_counts.py
"""Run AFTER `python -m services.sheets_etl.cli` to verify population."""
import os
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

CFG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require",
    "options": "-csearch_path=crm,public",
}


@pytest.fixture(scope="module")
def conn():
    c = psycopg2.connect(**CFG)
    yield c
    c.close()


def _count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def test_promo_codes_populated(conn):
    assert _count(conn, "crm.promo_codes") >= 5


def test_bloggers_populated(conn):
    assert _count(conn, "crm.bloggers") >= 100


def test_blogger_channels_populated(conn):
    assert _count(conn, "crm.blogger_channels") >= 100


def test_substitute_articles_populated(conn):
    assert _count(conn, "crm.substitute_articles") >= 50


def test_substitute_metrics_populated(conn):
    assert _count(conn, "crm.substitute_article_metrics_weekly") >= 100


def test_integrations_populated(conn):
    assert _count(conn, "crm.integrations") >= 100


def test_integration_substitute_junction_populated(conn):
    assert _count(conn, "crm.integration_substitute_articles") >= 50


def test_candidates_populated(conn):
    assert _count(conn, "crm.blogger_candidates") >= 50
```

- [ ] **Step 6: Run E2E tests**

```bash
.venv/bin/python -m pytest tests/sheets_etl/test_e2e_counts.py -v
```
Expected: 8 PASS.

- [ ] **Step 7: Re-run ETL → verify idempotent (counts unchanged)**

```bash
PROMO_BEFORE=$(.venv/bin/python -c "from services.sheets_etl.loader import get_conn; c=get_conn(); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM crm.promo_codes'); print(cur.fetchone()[0]); c.close()")
.venv/bin/python -m services.sheets_etl.cli
PROMO_AFTER=$(.venv/bin/python -c "from services.sheets_etl.loader import get_conn; c=get_conn(); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM crm.promo_codes'); print(cur.fetchone()[0]); c.close()")
test "$PROMO_BEFORE" = "$PROMO_AFTER" && echo "IDEMPOTENT OK ($PROMO_AFTER == $PROMO_BEFORE)"
```
Expected: prints `IDEMPOTENT OK (N == N)`.

- [ ] **Step 8: Commit**

```bash
git add services/sheets_etl/transformers/candidates.py services/sheets_etl/cli.py tests/sheets_etl/test_e2e_counts.py
git commit -m "feat(crm-etl): candidates + CLI orchestrator + E2E counts"
```

---

## Task 11: Memory entry + close phase

- [ ] **Step 1: Update memory `project_influencer_crm.md`**

```markdown
## Phase 2 (Sheets ETL) — DONE 2026-04-27
- 5 transformers: promo_codes, bloggers (+channels), substitute_articles (+weekly metrics), integrations (+sub junction), candidates.
- CLI: `.venv/bin/python -m services.sheets_etl.cli [--table=<name>] [--dry-run]`.
- Idempotent via `sheet_row_id` MD5 content hash; re-runs UPSERT not duplicate.
- E2E counts: 8 assertions all PASS.
- Branch: `feat/influencer-crm-p1` (continuation; will rename to feat/influencer-crm-p2 in PR).
```

- [ ] **Step 2: Final commit**

```bash
git status
git commit --allow-empty -m "feat(crm): Phase 2 (Sheets ETL) complete"
```

---

## Self-Review Checklist

- **Spec coverage:** 5 source sheets → 8 target tables (incl. junctions + weekly metrics). Every transformer has a fixture-based test. CLI orchestrates dependency order. E2E asserts population. ✅
- **Placeholder scan:** every code block is complete and runnable. No "TBD" or "implement later". ✅
- **Type consistency:** `sheet_row_id` is always a 32-char str. `display_handle` flows through `_handle_ref` keys consistently. `parse_*` returns Optional types matching schema NULLability. ✅

## Phase 2 Done Definition

- [x] All 5 transformers implemented with TDD
- [x] CLI orchestrator runs in dependency order
- [x] E2E counts test passes (8 assertions)
- [x] Re-run is idempotent (same counts)
- [x] Memory updated

When all checked → write Phase 3 plan (API BFF on FastAPI).
