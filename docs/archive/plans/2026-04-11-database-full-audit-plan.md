# Database & Sheet Full Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a full audit of Supabase DB + Google Sheet spec table, find all data errors, analyze infra tables, and produce a structured report with actionable recommendations.

**Architecture:** 3-wave subagent pipeline (Data Collection → Analysis → Verification) orchestrated from main context. Each wave runs agents in parallel. Verifier agent checks all results before final report assembly.

**Spec:** `docs/superpowers/specs/2026-04-11-database-full-audit-design.md`

**Key context:**
- Google Sheet ID: `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`
- Supabase connection: `scripts/sync_sheets_to_supabase.py:48-56` (env vars: SUPABASE_HOST, SUPABASE_PORT, SUPABASE_DB, SUPABASE_USER, SUPABASE_PASSWORD)
- Sync script: `scripts/sync_sheets_to_supabase.py` (1053 lines)
- DB schema DDL: `sku_database/database/schema.sql`
- Data layer: `shared/data_layer/sku_mapping.py`
- Last sync log: `docs/reports/sync-log-2026-04-07.json`
- Sheet reader via `gws sheets get <id> --range '<sheet>!<range>'`

---

## Task 1: Wave 1a — DB Reader (subagent)

**Purpose:** Snapshot all Supabase tables — full data for PIM, stats for infra.

- [ ] **Step 1: Connect to Supabase and dump PIM tables**

Run Python via Bash to connect to Supabase (using env vars from `.env`) and dump all PIM tables to JSON:

```python
import psycopg2, psycopg2.extras, json, os
from pathlib import Path
from dotenv import load_dotenv

# Load env from project root
load_dotenv(Path(__file__).parent.parent / '.env')
# Also try sku_database/.env
load_dotenv(Path(__file__).parent.parent / 'sku_database' / '.env')

conn = psycopg2.connect(
    host=os.getenv("SUPABASE_HOST", "aws-1-ap-northeast-2.pooler.supabase.com"),
    port=int(os.getenv("SUPABASE_PORT", "5432")),
    database=os.getenv("SUPABASE_DB", "postgres"),
    user=os.getenv("SUPABASE_USER", "postgres"),
    password=os.getenv("SUPABASE_PASSWORD", ""),
)

PIM_TABLES = [
    "modeli_osnova", "modeli", "artikuly", "tovary",
    "cveta", "kategorii", "kollekcii", "statusy",
    "importery", "fabriki", "razmery",
    "skleyki_wb", "skleyki_ozon",
    "tovary_skleyki_wb", "tovary_skleyki_ozon",
    "sertifikaty", "modeli_osnova_sertifikaty",
]

INFRA_TABLES = [
    "agent_runs", "orchestrator_runs", "report_runs",
    "kb_chunks", "content_assets", "analytics_rules",
    "notification_log", "archive_records", "field_definitions",
    "istoriya_izmeneniy",
]

result = {"pim": {}, "infra": {}}

cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# PIM: full dump
for t in PIM_TABLES:
    try:
        cur.execute(f"SELECT * FROM {t}")
        rows = [dict(r) for r in cur.fetchall()]
        result["pim"][t] = {"count": len(rows), "data": rows}
    except Exception as e:
        result["pim"][t] = {"count": 0, "data": [], "error": str(e)}
        conn.rollback()

# Infra: stats + sample
for t in INFRA_TABLES:
    try:
        cur.execute(f"SELECT COUNT(*) as cnt FROM {t}")
        cnt = cur.fetchone()["cnt"]
        cur.execute(f"SELECT * FROM {t} ORDER BY created_at DESC LIMIT 5")
        sample = [dict(r) for r in cur.fetchall()]
        # Get max date
        cur.execute(f"SELECT MAX(created_at) as last_date FROM {t}")
        last = cur.fetchone()["last_date"]
        result["infra"][t] = {
            "count": cnt,
            "last_date": str(last) if last else None,
            "sample": sample,
        }
    except Exception as e:
        result["infra"][t] = {"count": 0, "error": str(e)}
        conn.rollback()

conn.close()
```

Write the result dict as JSON. Due to size, serialize datetime/date objects with `default=str`.

- [ ] **Step 2: Save output**

Save to `/tmp/db-audit-snapshot.json`. Report summary: table name → row count for each table.

---

## Task 2: Wave 1b — Sheet Reader (subagent, parallel with Task 1)

**Purpose:** Read all relevant sheets from the Google Sheets specification table.

- [ ] **Step 1: Read all sheet tabs**

Use `gws sheets get` to read each tab. The spreadsheet ID is `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`.

Tabs to read:
```bash
# "Все модели" — main spec, 314 rows, cols A-CM (91 cols)
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Все модели'!A1:CM320" --output json

# "Все товары"
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Все товары'!A1:Z5" --output json
# Then full range based on discovered dimensions

# "Все артикулы"
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Все артикулы'!A1:Z5" --output json

# "Аналитики цветов"  
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Аналитики цветов'!A1:Z5" --output json

# "Склейки WB"
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Склейки WB'!A1:Z5" --output json

# "Склейки Озон"
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Склейки Озон'!A1:Z5" --output json

# "Упаковки"
gws sheets get 19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg --range "'Упаковки'!A1:Z5" --output json
```

For each tab: first read headers + 5 rows to discover structure, then read full range.

- [ ] **Step 2: Parse and normalize**

For "Все модели": the sheet has hierarchical structure — model row (col A filled) followed by size sub-rows (col A empty). Parse into flat list of model-level records.

Extract key fields per model:
- Col A: Модель (model name, only on parent row)
- Col B: Модель основа (base model)
- Col C: Название модели (model name — may differ from A)
- Col D: Название RU
- Col G: Статус
- Col H: Артикул модели
- Col I: Категория
- Col AM: SKU CHINA

- [ ] **Step 3: Save output**

Save to `/tmp/sheet-audit-snapshot.json`. Report summary: tab name → row count, column count.

---

## Task 3: Wave 1c — Code Scanner (subagent, parallel with Tasks 1-2)

**Purpose:** Map which DB tables are referenced in which code files.

- [ ] **Step 1: Grep for each table name across the codebase**

For each table (PIM + infra), grep the codebase:

```bash
# Example for one table — repeat for all
grep -rn "modeli_osnova" --include="*.py" --include="*.sql" --include="*.md" . | grep -v node_modules | grep -v __pycache__
```

Tables to scan (all 27):
```
modeli_osnova, modeli, artikuly, tovary, cveta, kategorii, kollekcii, 
statusy, importery, fabriki, razmery, skleyki_wb, skleyki_ozon,
tovary_skleyki_wb, tovary_skleyki_ozon, sertifikaty, 
modeli_osnova_sertifikaty, istoriya_izmeneniy,
agent_runs, orchestrator_runs, report_runs, kb_chunks, 
content_assets, analytics_rules, notification_log, 
archive_records, field_definitions
```

- [ ] **Step 2: Classify usage**

For each table, classify:
- **READ**: appears in SELECT / .select() / fetch queries
- **WRITE**: appears in INSERT / UPDATE / .upsert() / .insert()
- **REFERENCE**: appears only in docs, schema, comments
- **UNUSED**: not found anywhere in .py files

- [ ] **Step 3: Save output**

Save to `/tmp/code-usage-snapshot.json`:
```json
{
  "modeli_osnova": {
    "usage": "READ+WRITE",
    "files": [
      {"path": "scripts/sync_sheets_to_supabase.py", "lines": [245, 301, 350], "type": "WRITE"},
      {"path": "shared/data_layer/sku_mapping.py", "lines": [45, 67], "type": "READ"}
    ]
  }
}
```

---

## Task 4: Wave 2a — PIM Auditor (subagent, after Tasks 1-3)

**Purpose:** Find all data errors in PIM tables by cross-referencing DB with Sheet.

**Inputs:** Read `/tmp/db-audit-snapshot.json` and `/tmp/sheet-audit-snapshot.json`.

- [ ] **Step 1: Audit modeli_osnova**

Compare DB `modeli_osnova` records against Sheet "Все модели" column B (Модель основа).

Checks:
1. Records in DB not in Sheet → flag as ORPHAN (e.g., `компбел-ж-бесшов` id=24)
2. Records in Sheet not in DB → flag as MISSING
3. Records where `kod` looks like an artikul (contains `-`, `ж`, `бесшов`) → flag as WRONG_TYPE
4. Duplicate records by LOWER(kod) → flag as DUPLICATE

- [ ] **Step 2: Audit modeli**

Compare DB `modeli` records against expected model list from Sheet.

Checks:
1. `kod` values that are Russian transliterations of existing English models:
   - Pattern: if `nazvanie` == `nazvanie_en` == `kod` and no English equivalent exists → OK
   - Pattern: if `nazvanie` contains Cyrillic and matches another model's meaning → DUPLICATE
   - Known issues: `Vuki animal`, `Vuki выстиранки`, `VukiN animal`, `VukiW выстиранки`, `Moon выстиранки`, `Moon трусы`, etc.
2. `RubyPT` → should be `Ruby P` (PT is "Print+text", should be just "P" for Print)
3. Records where `nazvanie_en` is NULL → list for review (may be OK for Russian-only models)
4. FK check: every `model_osnova_id` must exist in `modeli_osnova`
5. Duplicate records by LOWER(kod)

- [ ] **Step 3: Audit artikuly**

Checks:
1. FK: every `model_id` references existing `modeli` record
2. FK: every `cvet_id` references existing `cveta` record  
3. FK: every `status_id` references existing `statusy` record
4. Orphan artikuly: records with no tovary pointing to them
5. Cross-reference with Sheet "Все артикулы" if available

- [ ] **Step 4: Audit tovary**

Checks:
1. FK: every `artikul_id` references existing `artikuly` record
2. Barcodes: format validation (10-13 digits), duplicates, empty values
3. Status consistency: if artikul is "Архив", all its tovary should be "Архив" too
4. Cross-reference with Sheet "Все товары"

- [ ] **Step 5: Audit reference tables**

Checks for cveta, kategorii, kollekcii, statusy, importery, fabriki, razmery:
1. Unused records (not referenced by any PIM table)
2. Cross-reference with relevant Sheet tabs
3. Duplicates by LOWER(nazvanie)

- [ ] **Step 6: Write PIM audit section**

Save findings to `/tmp/audit-pim-results.md` in this format:

```markdown
## PIM Audit Results

### modeli_osnova (N issues)
| # | ID | kod | Problem | Recommendation | Confidence |
|---|-----|-----|---------|----------------|------------|

### modeli (N issues)
| # | ID | kod | nazvanie | Problem | Recommendation | Confidence |
|---|-----|-----|----------|---------|----------------|------------|

### artikuly (N issues)
...
```

Confidence levels:
- **HIGH**: clear error, safe to fix (e.g., artikul in modeli_osnova)
- **MEDIUM**: likely error, needs confirmation (e.g., RubyPT → Ruby P)
- **LOW**: uncertain, requires manual review (e.g., NULL nazvanie_en)

---

## Task 5: Wave 2b — Sheet Analyst (subagent, parallel with Task 4)

**Purpose:** Analyze Google Sheet structure, find data quality issues, propose improvements.

**Inputs:** Read `/tmp/sheet-audit-snapshot.json`.

- [ ] **Step 1: Analyze column overlap in "Все модели"**

Compare columns:
- Col A (Модель) vs Col B (Модель основа) vs Col C (Название модели)
  - Count how many rows where A == B, A == C, B == C
  - If >90% identical → recommend removing the duplicate
- Col H (Артикул модели) — what values does it contain? Is it always `<model_kod>/`?

- [ ] **Step 2: Find data quality issues**

Scan for:
1. Empty cells in required columns (A, B, G=Статус, I=Категория for model rows)
2. Inconsistent statuses (typos, non-standard values)
3. Columns marked "не нужно" (AH-AJ) — confirm they should be removed
4. Columns with >80% empty values — candidates for removal
5. Non-model rows (size sub-rows) with conflicting data vs parent

- [ ] **Step 3: Analyze which columns the sync script uses**

Cross-reference with `scripts/sync_sheets_to_supabase.py` to identify:
- Which of the 91 columns are actually read by the sync script
- Which are never used → informational only, could be marked as such
- Are there columns the sync should be reading but isn't?

Read the sync script mapping sections (around lines 100-300) to find column name references.

- [ ] **Step 4: Propose Sheet improvements**

Based on findings, write specific recommendations:
1. Columns to remove/merge
2. Data validation rules to add
3. Structure changes (e.g., separate tabs for different data types)
4. Naming consistency

- [ ] **Step 5: Write Sheet audit section**

Save to `/tmp/audit-sheet-results.md`:

```markdown
## Sheet Analysis Results

### Column Overlap Analysis
| Col A (Модель) | Col B (Модель основа) | Col C (Название модели) | Match % |

### Data Quality Issues
| # | Sheet | Row | Column | Value | Problem | Recommendation |

### Unused Columns (not read by sync script)
| Column | Header | % Filled | Recommendation |

### Improvement Proposals
1. ...
```

---

## Task 6: Wave 2c — Infra Auditor (subagent, parallel with Tasks 4-5)

**Purpose:** Audit infrastructure tables — usage, necessity, descriptions, schema recommendation.

**Inputs:** Read `/tmp/db-audit-snapshot.json` and `/tmp/code-usage-snapshot.json`.

- [ ] **Step 1: Classify each infra table**

For each of the 10 infra tables, compile:

```markdown
| Table | Records | Last Write | Read in Code | Write in Code | Verdict |
```

Verdict logic:
- **KEEP**: actively read AND written in code, recent data
- **ARCHIVE**: written but not read (or last write >30 days ago)
- **DELETE**: not referenced in any .py file, or 0 records
- **REVIEW**: referenced in code but unclear if needed

- [ ] **Step 2: Write descriptions for KEEP tables**

For each KEEP table, write:
- Purpose (1 sentence)
- Who writes to it (which script/service)
- Who reads from it (which script/service)
- Recommended retention policy (e.g., "keep last 90 days, auto-delete older")
- Recommended schema: `pim` or `infra`

- [ ] **Step 3: Analyze schema reorganization**

Propose schema split:
- `pim` schema: all product/SKU tables (modeli_osnova, modeli, artikuly, tovary, cveta, etc.)
- `infra` schema: all infrastructure tables (agent_runs, report_runs, etc.)

Explain:
- How to create schemas in Supabase
- Migration path (ALTER TABLE ... SET SCHEMA ...)
- Impact on existing code (need to update table references or use search_path)
- RLS implications

- [ ] **Step 4: Write Infra audit section**

Save to `/tmp/audit-infra-results.md`:

```markdown
## Infrastructure Tables Audit

### Table Classification
| Table | Records | Last Write | Code Usage | Verdict | Target Schema |
|-------|---------|------------|------------|---------|---------------|

### Table Descriptions (KEEP)
#### agent_runs
- Purpose: ...
- Writers: ...
- Readers: ...
- Retention: ...

### Schema Reorganization Proposal
...

### DELETE Candidates
| Table | Reason | Risk |
```

---

## Task 7: Wave 3 — Verifier (subagent, after Tasks 4-6)

**Purpose:** Cross-check all audit results, resolve contradictions, assign confidence, assemble final report.

**Inputs:** Read all three result files:
- `/tmp/audit-pim-results.md`
- `/tmp/audit-sheet-results.md`
- `/tmp/audit-infra-results.md`

Also read original data: `/tmp/db-audit-snapshot.json`, `/tmp/sheet-audit-snapshot.json`, `/tmp/code-usage-snapshot.json`.

- [ ] **Step 1: Check for contradictions**

Specific checks:
1. If PIM Auditor says "delete model X" — verify X is NOT in Sheet data
2. If Sheet Analyst says "column Y is unused" — verify sync script doesn't reference it
3. If Infra Auditor says "delete table Z" — verify no code references it
4. If PIM Auditor flags a model as "duplicate" — check if artikuly/tovary reference both copies

- [ ] **Step 2: Completeness check**

Verify all tables are covered:
- All 17 PIM tables mentioned in PIM audit
- All 10 infra tables mentioned in Infra audit
- All Sheet tabs analyzed

List any gaps.

- [ ] **Step 3: Spot-check 5 DELETE/RENAME recommendations**

For the 5 highest-impact recommendations (DELETE or RENAME), verify by running direct SQL:

```python
# Example spot-check: verify kompbel-zh-besshov has no FK references
SELECT COUNT(*) FROM modeli WHERE model_osnova_id = 24;
SELECT COUNT(*) FROM artikuly a JOIN modeli m ON a.model_id = m.id WHERE m.model_osnova_id = 24;
```

If a spot-check fails (FK references exist), downgrade confidence to LOW and add note.

- [ ] **Step 4: Classify all recommendations**

Assign final confidence (HIGH / MEDIUM / LOW) to every recommendation. Criteria:
- **HIGH**: confirmed error, no FK dependencies, safe to fix
- **MEDIUM**: likely error, some dependencies exist, needs care
- **LOW**: uncertain, may be intentional, requires owner input

- [ ] **Step 5: Check sync script for root causes**

Read `scripts/sync_sheets_to_supabase.py` (key sections: normalization ~100-150, diff engine ~150-300, level handlers ~300-900) to identify:
1. Why `компбел-ж-бесшов` entered modeli_osnova (which column mapping?)
2. Why Russian model names (Vuki animal etc.) were created
3. Any other mapping bugs

Document findings for Section 4 of report.

---

## Task 8: Assemble Final Report (orchestrator)

**Purpose:** I (orchestrator) merge all verified results into the final report.

- [ ] **Step 1: Compile report**

Merge `/tmp/audit-pim-results.md`, `/tmp/audit-sheet-results.md`, `/tmp/audit-infra-results.md` plus Verifier corrections into `docs/reports/database-audit-2026-04-11.md`.

Structure:
```markdown
# Database & Sheet Full Audit — 2026-04-11

## Сводка
- Всего проблем: N
- HIGH: N | MEDIUM: N | LOW: N
- Таблиц проверено: N из 27

## 1. PIM — Товарная матрица
[from PIM Auditor, with Verifier corrections]

## 2. Google Sheet — анализ структуры
[from Sheet Analyst, with Verifier corrections]

## 3. Инфраструктурные таблицы
[from Infra Auditor, with Verifier corrections]

## 4. Sync-скрипт — выявленные баги
[from Verifier root cause analysis]

## 5. Сводка действий (чеклист для утверждения)
- [ ] HIGH: DELETE modeli_osnova id=24 ...
- [ ] MEDIUM: RENAME modeli id=40 RubyPT → Ruby P ...
- [ ] ...
```

- [ ] **Step 2: Commit report**

```bash
git add docs/reports/database-audit-2026-04-11.md
git commit -m "docs: add database & sheet full audit report 2026-04-11"
```

- [ ] **Step 3: Present to user for review**

Show summary of findings and ask user to approve/reject each recommendation in Section 5.

---

## Execution Order

```
Wave 1 (parallel):  Task 1 (DB Reader) | Task 2 (Sheet Reader) | Task 3 (Code Scanner)
                              ↓                    ↓                     ↓
                    Save /tmp/*.json       Save /tmp/*.json      Save /tmp/*.json
                              ↓                    ↓                     ↓
Wave 2 (parallel):  Task 4 (PIM Auditor) | Task 5 (Sheet Analyst) | Task 6 (Infra Auditor)
                              ↓                    ↓                     ↓
                    Save /tmp/*-results.md  Save /tmp/*-results.md  Save /tmp/*-results.md
                              ↓                    ↓                     ↓
Wave 3 (single):              └──────── Task 7 (Verifier) ────────────┘
                                              ↓
                                  Verified + classified results
                                              ↓
Final:                            Task 8 (Orchestrator assembles report)
```

**Total agents:** 7 (3 + 3 + 1), plus orchestrator (main context).
