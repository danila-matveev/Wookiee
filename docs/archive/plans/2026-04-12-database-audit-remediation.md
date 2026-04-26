# Database Audit Remediation — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply all approved fixes from the 2026-04-11 database audit: clean up PIM junk, fix sync bugs, add missing statuses, implement OZON gluing sync, move infra tables to separate schema.

**Architecture:** 8 tasks in 3 waves. Wave 1 = safe DB cleanups (DELETE junk, ADD statuses). Wave 2 = fix sync script (col C→A bug, add skleyki_ozon sync). Wave 3 = schema reorganization (CREATE SCHEMA infra, migrate tables, update code refs).

**Spec:** `docs/reports/database-audit-2026-04-11.md`

**Key context:**
- Supabase connection: `scripts/sync_sheets_to_supabase.py:48-56` (env vars from .env)
- Sync script: `scripts/sync_sheets_to_supabase.py` (1053 lines)
- DB schema DDL: `sku_database/database/schema.sql`
- Triggers: `sku_database/database/triggers.sql`
- Logger: `services/observability/logger.py`
- Color_code = главный ID цвета. Разные color_code с одинаковым названием — НЕ дубли (разные коллекции: сингвер, Audrey, Wendy и т.д.)

---

## Task 1: DELETE junk from modeli_osnova and modeli (Wave 1)

**Purpose:** Remove zombie/ghost records with 0 FK dependencies (verified by spot-checks).

**Files:**
- Create: `scripts/audit_remediation/wave1_cleanup.py`
- Reference: `docs/reports/database-audit-2026-04-11.md`

- [ ] **Step 1: Write cleanup script**

```python
"""Wave 1: Delete verified junk records from PIM tables.

Records verified to have 0 FK dependencies (spot-checked 2026-04-11).
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", ""),
    )


def verify_no_fk(conn, table: str, id_val: int, fk_table: str, fk_col: str) -> bool:
    """Safety check: ensure no FK references exist before DELETE."""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {fk_table} WHERE {fk_col} = %s", (id_val,))
    count = cur.fetchone()[0]
    return count == 0


def main():
    conn = get_conn()
    cur = conn.cursor()

    # 1. DELETE modeli_osnova id=24 (компбел-ж-бесшов) — zombie, artikul in osnova table
    if verify_no_fk(conn, "modeli_osnova", 24, "modeli", "model_osnova_id"):
        cur.execute("DELETE FROM modeli_osnova WHERE id = 24")
        print("✓ Deleted modeli_osnova id=24 (компбел-ж-бесшов)")
    else:
        print("✗ SKIPPED modeli_osnova id=24 — has FK references!")

    # 2. DELETE 16 ghost models with 0 artikuly
    ghost_ids = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 58]
    deleted = 0
    for mid in ghost_ids:
        if verify_no_fk(conn, "modeli", mid, "artikuly", "model_id"):
            cur.execute("DELETE FROM modeli WHERE id = %s", (mid,))
            deleted += 1
        else:
            print(f"✗ SKIPPED modeli id={mid} — has FK references!")
    print(f"✓ Deleted {deleted}/{len(ghost_ids)} ghost models")

    conn.commit()
    conn.close()
    print("Done. Wave 1 cleanup complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify current state before running**

Run:
```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT id, kod FROM modeli_osnova WHERE id = 24')
print('modeli_osnova id=24:', cur.fetchone())
cur.execute('SELECT COUNT(*) FROM modeli WHERE id IN (42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,58)')
print('ghost models count:', cur.fetchone()[0])
conn.close()
"
```

Expected: modeli_osnova id=24 exists, ghost models count = 16

- [ ] **Step 3: Run cleanup**

```bash
python scripts/audit_remediation/wave1_cleanup.py
```

Expected: "Deleted modeli_osnova id=24" + "Deleted 16/16 ghost models"

- [ ] **Step 4: Verify deletion**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM modeli_osnova WHERE id = 24')
print('modeli_osnova id=24 exists:', cur.fetchone()[0] > 0)
cur.execute('SELECT COUNT(*) FROM modeli WHERE id IN (42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,58)')
print('remaining ghost models:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM modeli_osnova')
print('total modeli_osnova:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM modeli')
print('total modeli:', cur.fetchone()[0])
conn.close()
"
```

Expected: id=24 exists = False, remaining = 0, total modeli_osnova = 25, total modeli = 96

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_remediation/wave1_cleanup.py
git commit -m "fix(pim): delete zombie modeli_osnova id=24 and 16 ghost models with 0 FK deps"
```

---

## Task 2: Add missing statuses "Запуск" and "Выводим" (Wave 1)

**Purpose:** Sync script doesn't know these statuses → models get NULL status_id in DB.

**Files:**
- Modify: `scripts/sync_sheets_to_supabase.py` (status mapping section)

- [ ] **Step 1: Find current status mapping**

Read `scripts/sync_sheets_to_supabase.py` and search for where statuses are resolved. The sync_modeli function resolves status via `get_archive_status_id()` and status name matching. Find the statusy table contents.

```bash
python -c "
import os, psycopg2, psycopg2.extras
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute('SELECT * FROM statusy ORDER BY id')
for r in cur.fetchall(): print(r)
conn.close()
"
```

- [ ] **Step 2: Insert new statuses**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute(\"\"\"
    INSERT INTO statusy (nazvanie) VALUES ('Запуск')
    ON CONFLICT (nazvanie) DO NOTHING
    RETURNING id, nazvanie
\"\"\")
r1 = cur.fetchone()
cur.execute(\"\"\"
    INSERT INTO statusy (nazvanie) VALUES ('Выводим')
    ON CONFLICT (nazvanie) DO NOTHING
    RETURNING id, nazvanie
\"\"\")
r2 = cur.fetchone()
conn.commit()
print(f'Inserted: {r1}, {r2}')
cur.execute('SELECT * FROM statusy ORDER BY id')
for r in cur.fetchall(): print(r)
conn.close()
"
```

- [ ] **Step 3: Verify statuses exist**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute(\"SELECT id, nazvanie FROM statusy WHERE nazvanie IN ('Запуск', 'Выводим')\")
for r in cur.fetchall(): print(r)
conn.close()
"
```

Expected: 2 rows returned

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "fix(pim): add statuses 'Запуск' and 'Выводим' to statusy table"
```

---

## Task 3: Fix 10 bad barcodes in DB (Wave 1)

**Purpose:** 10 товаров have barcodes like "7", "9", "18" — row numbers from bad import. Real barcodes exist in Sheet.

**Files:**
- Create: `scripts/audit_remediation/fix_barcodes.py`

- [ ] **Step 1: Write barcode fix script**

Script should: read Sheet "Все товары" col E (Артикул) to find the real barcodes for these 10 товаров, then UPDATE in DB. The bad barcodes are for artikuly `компбел-ж-бесшов/*` (ids 112,115,121,124,127) and `Joy/*` (ids 637,640,643,653,695).

```python
"""Fix 10 bad barcodes by looking up real values from Google Sheet.

Bad barcodes in DB: "7","9","10","18","21","23","24","25","26","27"
These are row numbers, not barcodes. The real barcodes (13-digit GS1)
exist in the Sheet for the same artikuly.
"""
import json
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
    )


def main():
    # Load Sheet snapshot (has all 3499 rows with real barcodes)
    with open("/tmp/sheet-audit-snapshot.json") as f:
        snapshot = json.load(f)

    # Build artikul → list of barcodes from Sheet
    tovary_rows = snapshot["vse_tovary"]["rows"]
    headers = snapshot["vse_tovary"]["headers"]
    barkod_idx = headers.index("БАРКОД ") if "БАРКОД " in headers else 0
    artikul_idx = headers.index("Артикул") if "Артикул" in headers else 4

    sheet_barcodes = {}  # artikul → [barcodes]
    for row in tovary_rows:
        if len(row) > max(barkod_idx, artikul_idx):
            barkod = str(row[barkod_idx]).strip() if row[barkod_idx] else ""
            artikul = str(row[artikul_idx]).strip() if row[artikul_idx] else ""
            if artikul and barkod and len(barkod) >= 10 and barkod.isdigit():
                sheet_barcodes.setdefault(artikul, []).append(barkod)

    # Get bad barcodes from DB
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.id, t.barkod, a.artikul
        FROM tovary t
        JOIN artikuly a ON t.artikul_id = a.id
        WHERE LENGTH(t.barkod) < 5
    """)
    bad_rows = cur.fetchall()
    print(f"Found {len(bad_rows)} bad barcodes in DB")

    fixed = 0
    for row in bad_rows:
        art = row["artikul"]
        if art in sheet_barcodes:
            # Find a barcode from Sheet that isn't already in DB
            for real_barkod in sheet_barcodes[art]:
                cur.execute("SELECT COUNT(*) FROM tovary WHERE barkod = %s", (real_barkod,))
                if cur.fetchone()["count"] == 0:
                    cur.execute(
                        "UPDATE tovary SET barkod = %s WHERE id = %s",
                        (real_barkod, row["id"]),
                    )
                    print(f"  ✓ id={row['id']}: '{row['barkod']}' → '{real_barkod}' ({art})")
                    fixed += 1
                    break
            else:
                print(f"  ✗ id={row['id']}: no unused barcode found for {art}")
        else:
            print(f"  ✗ id={row['id']}: artikul '{art}' not found in Sheet")

    conn.commit()
    conn.close()
    print(f"\nFixed {fixed}/{len(bad_rows)} barcodes")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run fix script**

```bash
python scripts/audit_remediation/fix_barcodes.py
```

Expected: "Fixed N/10 barcodes" (some may not have Sheet matches if компбел-ж-бесшов has been archived)

- [ ] **Step 3: Verify**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM tovary WHERE LENGTH(barkod) < 5')
print('Remaining bad barcodes:', cur.fetchone()[0])
conn.close()
"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/audit_remediation/fix_barcodes.py
git commit -m "fix(pim): replace 10 placeholder barcodes with real GS1 values from Sheet"
```

---

## Task 4: Fix sync bug — col C → col A for modeli.kod (Wave 2)

**Purpose:** `sync_modeli()` reads col C ("Название модели" = "Vuki animal") as kod instead of col A ("Модель" = "VukiN"). This creates ghost models with Russian names.

**Files:**
- Modify: `scripts/sync_sheets_to_supabase.py:505-510` (sync_modeli function)

- [ ] **Step 1: Read the current mapping code**

Read `scripts/sync_sheets_to_supabase.py` lines 498-525 to understand the full context.

- [ ] **Step 2: Fix the mapping — use col A ("Модель") as kod, col C ("Название модели") as nazvanie**

Change line 506 from:
```python
        nazvanie = clean_string(row.get("Название модели", ""))
        if not nazvanie:
            continue
        kod = normalize_key(nazvanie)
```

To:
```python
        model_code = clean_string(row.get("Модель", ""))  # Col A — short code (VukiN)
        nazvanie = clean_string(row.get("Название модели", ""))  # Col C — display name
        if not model_code and not nazvanie:
            continue
        # Use col A as kod (short code), fall back to col C if col A is empty
        kod_source = model_code or nazvanie
        kod = normalize_key(kod_source)
```

And update line 515-516:
```python
        model_data[kod] = {
            "kod_raw": (model_code or nazvanie).strip(),
            "nazvanie": nazvanie or model_code,
```

- [ ] **Step 3: Run sync in dry-run mode to verify**

```bash
python scripts/sync_sheets_to_supabase.py --level modeli --dry-run
```

Expected: dry-run should show it would create models with codes like "VukiN", "VukiW", "MoonW" instead of "Vuki animal", "Vuki выстиранки", "Moon выстиранки".

- [ ] **Step 4: Commit**

```bash
git add scripts/sync_sheets_to_supabase.py
git commit -m "fix(sync): use col A (Модель) as modeli.kod instead of col C (Название модели)

Previously sync_modeli() read col C which contains Russian display names
like 'Vuki animal', creating ghost records. Now uses col A ('VukiN') as
the short code, col C remains as nazvanie for display."
```

---

## Task 5: Implement sync for "Склейки Озон" (Wave 2)

**Purpose:** Sheet has 1405 rows of OZON gluing data, DB has 0. Table `skleyki_ozon` exists but no sync function.

**Files:**
- Modify: `scripts/sync_sheets_to_supabase.py` (add sync_skleyki_ozon function + wire it up)

- [ ] **Step 1: Read the Sheet "Склейки Озон" structure**

First, understand the data shape by reading from the snapshot:
```bash
python -c "
import json
with open('/tmp/sheet-audit-snapshot.json') as f:
    data = json.load(f)
tab = data.get('sklejki_ozon', data.get('skleyki_ozon', {}))
print('Headers:', tab.get('headers', [])[:10])
print('Row count:', tab.get('row_count', 0))
if tab.get('rows'):
    for r in tab['rows'][:5]:
        print(r[:5])
"
```

- [ ] **Step 2: Add sync_skleyki_ozon function**

Add a new function after `sync_tovary()` in `scripts/sync_sheets_to_supabase.py`. Follow the same pattern as existing sync functions:

1. Load sheet tab "Склейки Озон" via `load_sheet_as_dicts()`
2. Parse unique skleyki names
3. Upsert into `skleyki_ozon` table
4. Then populate `tovary_skleyki_ozon` junction table mapping товары to their OZON gluing groups

This requires reading the actual Sheet structure first (Step 1) to know the column layout.

- [ ] **Step 3: Wire into main sync flow**

In the main `sync_all()` function (around line 960-990), add:
```python
    # Load Склейки Озон sheet
    sheets_skleyki_ozon = load_sheet_as_dicts(gs_client, sid, "Склейки Озон")
    logger.info(f"  Склейки Озон: {len(sheets_skleyki_ozon)} rows")
```

And add the sync call after existing sync levels.

- [ ] **Step 4: Test dry-run**

```bash
python scripts/sync_sheets_to_supabase.py --dry-run 2>&1 | grep -i "склейки\|ozon\|skleyki"
```

- [ ] **Step 5: Run actual sync**

```bash
python scripts/sync_sheets_to_supabase.py --level all
```

- [ ] **Step 6: Verify data in DB**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM skleyki_ozon')
print('skleyki_ozon:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM tovary_skleyki_ozon')
print('tovary_skleyki_ozon:', cur.fetchone()[0])
conn.close()
"
```

Expected: skleyki_ozon > 0, tovary_skleyki_ozon > 0

- [ ] **Step 7: Commit**

```bash
git add scripts/sync_sheets_to_supabase.py
git commit -m "feat(sync): implement sync for Склейки Озон sheet → skleyki_ozon table

1405 rows in Sheet, table existed but had no sync function.
Syncs both skleyki_ozon (names) and tovary_skleyki_ozon (junction)."
```

---

## Task 6: DROP 3 dead infra tables (Wave 3)

**Purpose:** report_runs, analytics_rules, notification_log — 0 code references, never implemented.

**Files:**
- Create: `scripts/audit_remediation/wave3_drop_tables.sql`

- [ ] **Step 1: Backup before dropping**

```bash
python -c "
import os, psycopg2, psycopg2.extras, json
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
backup = {}
for t in ['report_runs', 'analytics_rules', 'notification_log']:
    cur.execute(f'SELECT * FROM {t}')
    backup[t] = [dict(r) for r in cur.fetchall()]
    print(f'{t}: {len(backup[t])} rows backed up')
conn.close()
with open('/tmp/infra-tables-backup.json', 'w') as f:
    json.dump(backup, f, default=str, indent=2)
print('Backup saved to /tmp/infra-tables-backup.json')
"
```

- [ ] **Step 2: Drop tables**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
for t in ['report_runs', 'analytics_rules', 'notification_log']:
    cur.execute(f'DROP TABLE IF EXISTS {t} CASCADE')
    print(f'✓ Dropped {t}')
conn.commit()
conn.close()
"
```

- [ ] **Step 3: Verify**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute(\"\"\"SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name IN ('report_runs','analytics_rules','notification_log')\"\"\")
remaining = cur.fetchall()
print('Remaining (should be empty):', remaining)
conn.close()
"
```

- [ ] **Step 4: Commit**

```bash
git commit --allow-empty -m "chore(infra): drop dead tables report_runs, analytics_rules, notification_log

0 code references, created for reporter-v4 spec but never implemented.
Backup saved to /tmp/infra-tables-backup.json."
```

---

## Task 7: CREATE SCHEMA infra + migrate tables (Wave 3)

**Purpose:** Separate infra tables from PIM tables into their own schema.

**Files:**
- Create: `scripts/audit_remediation/wave3_schema_migration.py`
- Modify: `services/knowledge_base/store.py` — update table refs
- Modify: `services/content_kb/store.py` — update table refs
- Modify: `services/product_matrix_api/routes/schema.py` — update table refs
- Modify: `services/product_matrix_api/services/archive_service.py` — update table refs
- Modify: `services/product_matrix_api/models/database.py` — update __tablename__ or __table_args__
- Modify: `services/observability/logger.py` — update table refs
- Modify: `sku_database/database/triggers.sql` — update istoriya_izmeneniy refs

- [ ] **Step 1: Create schema and migrate tables**

```python
"""Wave 3: Create infra schema and migrate tables."""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    conn = psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
    )
    cur = conn.cursor()

    # Create schema
    cur.execute("CREATE SCHEMA IF NOT EXISTS infra")
    cur.execute("GRANT USAGE ON SCHEMA infra TO authenticated")
    cur.execute("GRANT USAGE ON SCHEMA infra TO service_role")
    cur.execute("""ALTER DEFAULT PRIVILEGES IN SCHEMA infra
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role""")
    cur.execute("""ALTER DEFAULT PRIVILEGES IN SCHEMA infra
        GRANT SELECT ON TABLES TO authenticated""")
    print("✓ Created schema infra")

    # Migrate tables
    tables = [
        "kb_chunks", "content_assets", "field_definitions",
        "istoriya_izmeneniy", "archive_records",
        "agent_runs", "orchestrator_runs",
    ]
    for t in tables:
        try:
            cur.execute(f"ALTER TABLE public.{t} SET SCHEMA infra")
            print(f"  ✓ Moved {t} → infra.{t}")
        except Exception as e:
            print(f"  ✗ Failed to move {t}: {e}")
            conn.rollback()
            # Re-run remaining
            continue

    # Set search_path so existing code works without immediate changes
    cur.execute("ALTER ROLE service_role SET search_path TO public, infra")
    print("✓ Set search_path for service_role: public, infra")

    conn.commit()
    conn.close()
    print("Done. Schema migration complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run migration**

```bash
python scripts/audit_remediation/wave3_schema_migration.py
```

- [ ] **Step 3: Verify tables moved**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute(\"\"\"SELECT table_schema, table_name FROM information_schema.tables
    WHERE table_name IN ('kb_chunks','content_assets','field_definitions','istoriya_izmeneniy','archive_records','agent_runs','orchestrator_runs')
    ORDER BY table_schema, table_name\"\"\")
for r in cur.fetchall(): print(f'{r[0]}.{r[1]}')
conn.close()
"
```

Expected: all 7 tables show `infra.table_name`

- [ ] **Step 4: Verify search_path makes existing code work**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
# Test that unqualified names still resolve via search_path
cur.execute('SELECT COUNT(*) FROM kb_chunks')
print('kb_chunks accessible:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM content_assets')
print('content_assets accessible:', cur.fetchone()[0])
conn.close()
"
```

Expected: both return counts > 0 (search_path resolves `infra` schema)

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_remediation/wave3_schema_migration.py
git commit -m "chore(infra): create schema infra and migrate 7 tables from public

Moved: kb_chunks, content_assets, field_definitions, istoriya_izmeneniy,
archive_records, agent_runs, orchestrator_runs → infra schema.
Set search_path = public, infra for service_role — existing code works
without immediate changes."
```

---

## Task 8: Run full sync to populate missing data (Wave 3 — final)

**Purpose:** After all fixes, run sync to create 30 missing modeli_osnova, fill 54 NULL FK, and add new models.

**Prerequisite:** User must first fill Sheet Col B = "Evelyn" for row 165. Also remove 7 junk columns from Sheet (cols 34-36 "не нужно" + cols 37,71,77,89 empty).

- [ ] **Step 1: Confirm Sheet edits are done**

Ask user to confirm:
1. Col B filled for Evelyn (row 165)
2. 7 junk columns removed from "Все модели"

- [ ] **Step 2: Run full sync in dry-run**

```bash
python scripts/sync_sheets_to_supabase.py --level all --dry-run 2>&1 | tail -30
```

Review output for expected inserts (30 modeli_osnova, ~6 new modeli, etc.)

- [ ] **Step 3: Run actual sync**

```bash
python scripts/sync_sheets_to_supabase.py --level all
```

- [ ] **Step 4: Verify results**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM modeli_osnova')
print('modeli_osnova:', cur.fetchone()[0], '(was 25, expect ~55)')
cur.execute('SELECT COUNT(*) FROM modeli WHERE model_osnova_id IS NULL')
print('modeli with NULL osnova:', cur.fetchone()[0], '(was 54, expect ~0)')
cur.execute('SELECT COUNT(*) FROM modeli WHERE status_id IS NULL')
print('modeli with NULL status:', cur.fetchone()[0], '(was ~7, expect 0)')
cur.execute('SELECT COUNT(*) FROM skleyki_ozon')
print('skleyki_ozon:', cur.fetchone()[0], '(was 0, expect >0)')
conn.close()
"
```

- [ ] **Step 5: Commit verification**

```bash
git commit --allow-empty -m "chore: run full sync after audit remediation

Post-remediation sync results:
- modeli_osnova: +30 new records
- modeli NULL FK: resolved
- statuses: Запуск and Выводим now mapped
- skleyki_ozon: populated from Sheet"
```

---

## Execution Order

```
Wave 1 (safe DB cleanup):
  Task 1: DELETE junk records
  Task 2: ADD missing statuses
  Task 3: FIX bad barcodes
          ↓
Wave 2 (sync script fixes):
  Task 4: FIX col C → col A mapping
  Task 5: ADD skleyki_ozon sync
          ↓
Wave 3 (infra + final sync):
  Task 6: DROP 3 dead tables
  Task 7: CREATE SCHEMA infra + migrate
  Task 8: RUN full sync (after user edits Sheet)
```

**Total: 8 tasks, 3 waves.**
**Prerequisite for Task 8:** User edits Sheet (fill Evelyn Col B, remove junk columns).
