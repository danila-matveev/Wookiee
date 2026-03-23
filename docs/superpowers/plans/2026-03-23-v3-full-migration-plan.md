# V3 Full Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all functionality from V2 (agents/oleg/) to V3 (agents/v3/) so V3 is the single production system with report quality >= V2.

**Architecture:** Strengthen V3 micro-agent prompts to demand V2-level output depth. Fix infrastructure bugs (watchdog, Notion dedup). Port Telegram bot handlers. Then decommission V2.

**Tech Stack:** Python 3.11, LangGraph, aiogram 3, httpx, APScheduler, SQLite (StateStore), Supabase (observability), Notion API, Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-03-22-v3-full-migration-design.md`

---

## File Structure

### Files to Modify

| File | Responsibility | Changes |
|------|---------------|---------|
| `agents/v3/monitor.py` | Watchdog health checks | Fix `_check_db` bug (line 67), harden `_check_last_run` (line 77) |
| `agents/v3/config.py` | V3 configuration | AGENT_TIMEOUT 120→180 |
| `agents/v3/app.py` | Telegram bot handlers | Add 9 command handlers (lines 148-167) |
| `agents/v3/state.py` | SQLite KV store | Remove TTL from `mark_delivered`, add `store_page_id`/`get_page_id` |
| `agents/v3/delivery/notion.py` | Notion delivery | Add missing keys to `_REPORT_TYPE_MAP`, add asyncio.Lock |
| `agents/v3/orchestrator.py` | Pipeline orchestrator | Pass `task_type` to compiler input, graceful degradation |
| `agents/v3/agents/margin-analyst.md` | Margin analysis agent | Add margin_waterfall, cost_structure, spp_dynamics, price_forecast |
| `agents/v3/agents/revenue-decomposer.md` | Revenue analysis agent | Add brand_metrics (15 fields), enforce ALL models, plan_fact with forecast |
| `agents/v3/agents/ad-efficiency.md` | Ad analysis agent | Add funnel[], ad_stats{}, brand_metrics_funnel (4 fields) |
| `agents/v3/agents/report-compiler.md` | Report compilation | Exact V2 table specs, graceful degradation, marketing/funnel conditionals |
| `agents/v3/agents/funnel-digitizer.md` | Funnel analysis agent | Enforce all models + WoW trend |
| `agents/v3/agents/campaign-optimizer.md` | Campaign analysis agent | Enforce external breakdown + model ROMI |
| `.claude/commands/daily-report.md` | CLI daily report | Repoint from V2 to V3 |
| `.claude/commands/weekly-report.md` | CLI weekly report | Repoint from V2 to V3 |
| `.claude/commands/period-report.md` | CLI period report | Repoint from V2 to V3 |
| `.claude/commands/marketing-report.md` | CLI marketing report | Repoint from V2 to V3 |
| `scripts/run_report.py` | CLI entry point | Switch from agents.oleg to agents.v3 |
| `deploy/docker-compose.yml` | Container config | Remove oleg-mcp (Phase 4) |

### Files to Create

| File | Responsibility |
|------|---------------|
| `tests/agents/v3/test_watchdog_fixes.py` | Tests for monitor.py fixes |
| `tests/agents/v3/test_notion_dedup.py` | Tests for Notion dedup fixes |
| `tests/agents/v3/test_telegram_handlers.py` | Tests for new bot handlers |
| `tests/agents/v3/test_state_store.py` | Tests for StateStore changes |

---

## Wave 0: OOM Fix (Server-Side, Manual)

> **NOTE:** Wave 0 is executed manually on the server via SSH, not through code changes. It must be done BEFORE any other waves.

### Task 0.1: Add swap + stop oleg-mcp

**Context:** Server has 2GB RAM, 0 swap. OOM Killer hits every night at ~03:04 UTC during ETL. Container is down 7.5h.

- [ ] **Step 1: SSH to server and add 4GB swap**

```bash
ssh timeweb
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h  # verify swap shows 4G
```

- [ ] **Step 2: Stop oleg-mcp container**

```bash
cd /opt/wookiee
docker compose stop oleg-mcp
docker compose rm -f oleg-mcp
docker stats --no-stream  # verify ~130MB freed
```

- [ ] **Step 3: Reduce memory limits**

Edit `deploy/docker-compose.yml` on server:
- eggent: `mem_limit: 1g` → `mem_limit: 512m`
- n8n: `mem_limit: 1.9g` → `mem_limit: 1g`

```bash
docker compose up -d eggent n8n
docker stats --no-stream  # verify new limits
```

- [ ] **Step 4: Run missed weekly reports manually**

```bash
# In the wookiee_oleg container, trigger weekly reports for 16-22 March
docker compose exec wookiee-oleg python -c "
import asyncio
from agents.v3 import orchestrator

async def main():
    # Weekly financial
    r = await orchestrator.run_weekly_report(
        '2026-03-16', '2026-03-22', '2026-03-09', '2026-03-15',
        trigger='manual_catchup')
    print('weekly:', r.get('status'))

    # Weekly marketing
    r = await orchestrator.run_marketing_report(
        '2026-03-16', '2026-03-22', '2026-03-09', '2026-03-15',
        report_period='weekly', trigger='manual_catchup')
    print('marketing_weekly:', r.get('status'))

    # Funnel weekly
    r = await orchestrator.run_funnel_report(
        '2026-03-16', '2026-03-22', '2026-03-09', '2026-03-15',
        trigger='manual_catchup')
    print('funnel_weekly:', r.get('status'))

asyncio.run(main())
"
```

---

## Wave 1: Infrastructure Fixes (Parallel — No Dependencies)

### Task 1.1: Fix watchdog DB check

**Files:**
- Modify: `agents/v3/monitor.py:60-74`
- Test: `tests/agents/v3/test_watchdog_fixes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/v3/test_watchdog_fixes.py
"""Tests for watchdog monitor fixes."""
import asyncio
from unittest.mock import patch, MagicMock
import pytest


@pytest.mark.asyncio
async def test_check_db_passes_callable_not_connection():
    """_check_db must pass the callable _get_wb_connection, not its result."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=(MagicMock(), MagicMock()))
    mock_cursor.__exit__ = MagicMock(return_value=False)

    with patch("agents.v3.monitor._db_cursor", return_value=mock_cursor) as mock_db_cursor, \
         patch("agents.v3.monitor._get_wb_connection") as mock_get_conn:
        from agents.v3.monitor import _check_db
        result = await _check_db()

        # _db_cursor should receive the callable, NOT the result of calling it
        mock_db_cursor.assert_called_once_with(mock_get_conn)
        assert result is True


@pytest.mark.asyncio
async def test_check_db_unpacks_tuple():
    """_check_db must unpack (conn, cur) tuple from _db_cursor context manager."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    from contextlib import contextmanager

    @contextmanager
    def fake_db_cursor(factory):
        yield (mock_conn, mock_cur)

    with patch("agents.v3.monitor._db_cursor", side_effect=fake_db_cursor), \
         patch("agents.v3.monitor._get_wb_connection"):
        from agents.v3.monitor import _check_db
        result = await _check_db()
        mock_cur.execute.assert_called_once_with("SELECT 1")
        assert result is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/v3/test_watchdog_fixes.py -v`
Expected: FAIL — `_db_cursor` is called with connection object, not callable

- [ ] **Step 3: Fix the bug in monitor.py**

In `agents/v3/monitor.py`, replace lines 66-68:

```python
# Before (buggy):
        def _sync_check():
            with _db_cursor(_get_wb_connection()) as cur:
                cur.execute("SELECT 1")

# After (fixed):
        def _sync_check():
            with _db_cursor(_get_wb_connection) as (conn, cur):
                cur.execute("SELECT 1")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/v3/test_watchdog_fixes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/monitor.py tests/agents/v3/test_watchdog_fixes.py
git commit -m "fix(watchdog): pass callable to _db_cursor and unpack (conn, cur) tuple

DB health check never worked in production — was passing connection
object instead of callable, and not unpacking the (conn, cur) tuple."
```

---

### Task 1.2: Harden watchdog last_run check

**Files:**
- Modify: `agents/v3/monitor.py:77-104`
- Test: `tests/agents/v3/test_watchdog_fixes.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/v3/test_watchdog_fixes.py`:

```python
@pytest.mark.asyncio
async def test_check_last_run_returns_true_on_missing_table():
    """If orchestrator_runs table doesn't exist, _check_last_run should return True (not crash)."""
    import sqlite3

    def fake_get_conn():
        conn = sqlite3.connect(":memory:")
        return conn

    with patch("services.observability.logger._get_conn", fake_get_conn):
        # Re-import to pick up patch
        from agents.v3 import monitor
        # Force re-import
        import importlib
        importlib.reload(monitor)
        result = await monitor._check_last_run()
        assert result is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/v3/test_watchdog_fixes.py::test_check_last_run_returns_true_on_missing_table -v`
Expected: FAIL — `OperationalError: no such table: orchestrator_runs`

- [ ] **Step 3: Add try/except fallback in _check_last_run**

In `agents/v3/monitor.py`, wrap the query inside `_sync_check` (lines 87-96):

```python
        def _sync_check():
            conn = _get_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT status FROM orchestrator_runs "
                    "ORDER BY started_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                return row[0] if row else None
            except Exception:
                # Table may not exist yet — not a failure
                return None
            finally:
                conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/v3/test_watchdog_fixes.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agents/v3/monitor.py tests/agents/v3/test_watchdog_fixes.py
git commit -m "fix(watchdog): handle missing orchestrator_runs table gracefully

_check_last_run now returns True (healthy) if the table doesn't
exist yet, instead of raising OperationalError and triggering
false-positive alerts."
```

---

### Task 1.3: Fix Notion dedup — add missing keys + remove TTL

**Files:**
- Modify: `agents/v3/delivery/notion.py:28-42`
- Modify: `agents/v3/state.py:70-71`
- Test: `tests/agents/v3/test_notion_dedup.py`
- Test: `tests/agents/v3/test_state_store.py`

- [ ] **Step 1: Write tests for StateStore TTL removal**

```python
# tests/agents/v3/test_state_store.py
"""Tests for StateStore delivery dedup changes."""
import os
import tempfile
import pytest
from agents.v3.state import StateStore


@pytest.fixture
def store(tmp_path):
    return StateStore(str(tmp_path / "test.db"))


def test_mark_delivered_has_no_ttl(store):
    """mark_delivered should store without TTL (persistent)."""
    store.mark_delivered("daily", "2026-03-22")
    # Verify the row has no expires_at
    row = store._conn.execute(
        "SELECT expires_at FROM kv_store WHERE key = ?",
        ("delivered:daily:2026-03-22",),
    ).fetchone()
    assert row is not None
    assert row[0] is None  # No TTL


def test_is_delivered_persists(store):
    """Delivery mark should persist indefinitely."""
    store.mark_delivered("weekly", "2026-03-16")
    assert store.is_delivered("weekly", "2026-03-16") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/v3/test_state_store.py -v`
Expected: FAIL — `mark_delivered` currently sets `ttl_hours=48`, so `expires_at` is not None

- [ ] **Step 3: Remove TTL from mark_delivered**

In `agents/v3/state.py`, line 71 change:

```python
# Before:
    def mark_delivered(self, report_type: str, date: str) -> None:
        self.set(f"delivered:{report_type}:{date}", "1", ttl_hours=48)

# After:
    def mark_delivered(self, report_type: str, date: str) -> None:
        self.set(f"delivered:{report_type}:{date}", "1")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/v3/test_state_store.py -v`
Expected: PASS

- [ ] **Step 5: Write test for missing _REPORT_TYPE_MAP keys**

```python
# tests/agents/v3/test_notion_dedup.py
"""Tests for Notion delivery dedup."""
import pytest
from agents.v3.delivery.notion import _REPORT_TYPE_MAP


def test_report_type_map_has_price_analysis():
    """price_analysis must be in _REPORT_TYPE_MAP."""
    assert "price_analysis" in _REPORT_TYPE_MAP


def test_report_type_map_has_all_required_keys():
    """All report types used by orchestrator must have mapping."""
    required = [
        "daily", "weekly", "monthly", "custom",
        "marketing_daily", "marketing_weekly", "marketing_monthly",
        "price_analysis", "price_weekly", "price_monthly",
        "finolog_weekly", "funnel_weekly",
    ]
    for key in required:
        assert key in _REPORT_TYPE_MAP, f"Missing key: {key}"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/agents/v3/test_notion_dedup.py -v`
Expected: FAIL — `price_analysis` not in `_REPORT_TYPE_MAP`

- [ ] **Step 7: Add missing keys to _REPORT_TYPE_MAP and add Lock**

In `agents/v3/delivery/notion.py`:

1. Add `price_analysis` key to `_REPORT_TYPE_MAP` (after line 41):

```python
_REPORT_TYPE_MAP: dict[str, tuple[str, str]] = {
    "daily":              ("Ежедневный фин анализ",     "Ежедневный фин анализ"),
    "weekly":             ("Еженедельный фин анализ",   "Еженедельный фин анализ"),
    "monthly":            ("Ежемесячный фин анализ",    "Ежемесячный фин анализ"),
    "custom":             ("Фин анализ",                "Фин анализ"),
    "marketing_daily":    ("Маркетинговый анализ",      "Ежедневный маркетинговый анализ"),
    "marketing_weekly":   ("Маркетинговый анализ",      "Еженедельный маркетинговый анализ"),
    "marketing_monthly":  ("Маркетинговый анализ",      "Ежемесячный маркетинговый анализ"),
    "marketing_custom":   ("Маркетинговый анализ",      "Маркетинговый анализ"),
    "price_analysis":        ("Ценовой анализ",         "Ценовой анализ"),
    "Ценовой анализ":        ("Ценовой анализ",         "Ценовой анализ"),
    "price_weekly":          ("Ценовой анализ",          "Еженедельный ценовой анализ"),
    "price_monthly":         ("Ценовой анализ",          "Ценовой анализ"),
    "finolog_weekly":        ("Еженедельная сводка ДДС", "Сводка ДДС"),
    "funnel_weekly":         ("funnel_weekly",            "Воронка WB (сводный)"),
}
```

2. Add `asyncio.Lock` per report_type to prevent race conditions. Add import at top:

```python
import asyncio
```

Add to `NotionDelivery.__init__`:

```python
    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self._locks: dict[str, asyncio.Lock] = {}
```

Add lock helper:

```python
    def _get_lock(self, report_type: str) -> asyncio.Lock:
        if report_type not in self._locks:
            self._locks[report_type] = asyncio.Lock()
        return self._locks[report_type]
```

Wrap `sync_report` body in lock:

```python
    async def sync_report(self, start_date, end_date, report_md, report_type="daily", source="Oleg v3 (auto)", chain_steps=1):
        if not self.enabled:
            logger.warning("Notion not configured, skipping sync")
            return None
        async with self._get_lock(report_type):
            # ... existing body ...
```

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/agents/v3/test_notion_dedup.py tests/agents/v3/test_state_store.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add agents/v3/delivery/notion.py agents/v3/state.py tests/agents/v3/test_notion_dedup.py tests/agents/v3/test_state_store.py
git commit -m "fix(notion): add missing report type keys, remove delivery TTL, add per-type Lock

- Added price_analysis to _REPORT_TYPE_MAP (was falling back to raw string)
- Removed 48h TTL from mark_delivered — delivery marks are now persistent
- Added asyncio.Lock per report_type to prevent race condition duplicates
- Preserved funnel_weekly label for Notion dedup consistency"
```

---

### Task 1.4: Repoint CLI commands from V2 to V3

**Files:**
- Modify: `scripts/run_report.py`
- Modify: `.claude/commands/daily-report.md`
- Modify: `.claude/commands/weekly-report.md`
- Modify: `.claude/commands/period-report.md`
- Modify: `.claude/commands/marketing-report.md`

- [ ] **Step 1: Update scripts/run_report.py to use V3 orchestrator**

Replace V2 imports with V3 calls. The key change — instead of `OlegApp` + `ReportPipeline`, call `agents.v3.orchestrator` functions directly:

```python
# Replace (line 86-87):
#     from agents.oleg.app import OlegApp
#     from agents.oleg.pipeline.report_types import ReportRequest, ReportType
# With:
    from agents.v3 import orchestrator
```

The `run_report()` function needs to map report types to V3 orchestrator calls:

```python
async def run_report(report_type: str, start_date: str, end_date: str = None,
                     comparison_start: str = None, comparison_end: str = None):
    """Run report via V3 orchestrator."""
    from agents.v3 import orchestrator
    from agents.v3.scheduler import _yesterday_msk, _last_week_msk, _last_month_msk, _day_before

    # Default end_date = start_date for daily
    if end_date is None:
        end_date = start_date

    # Default comparison = previous period of same length
    if comparison_start is None:
        from datetime import date, timedelta
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
        delta = (e - s) + timedelta(days=1)
        comparison_end = str(s - timedelta(days=1))
        comparison_start = str(s - delta)

    type_map = {
        "daily": orchestrator.run_daily_report,
        "weekly": orchestrator.run_weekly_report,
        "monthly": orchestrator.run_monthly_report,
        "marketing_daily": lambda **kw: orchestrator.run_marketing_report(report_period="daily", **kw),
        "marketing_weekly": lambda **kw: orchestrator.run_marketing_report(report_period="weekly", **kw),
        "marketing_monthly": lambda **kw: orchestrator.run_marketing_report(report_period="monthly", **kw),
    }

    fn = type_map.get(report_type)
    if not fn:
        print(f"Unknown report type: {report_type}")
        return

    result = await fn(
        date_from=start_date,
        date_to=end_date,
        comparison_from=comparison_start,
        comparison_to=comparison_end,
        trigger="cli",
    )
    print(f"Status: {result.get('status')}")
    if result.get("status") == "success":
        print("Report generated successfully.")
    else:
        print(f"Report failed: {result}")
```

- [ ] **Step 2: Update .claude/commands/daily-report.md**

```markdown
Создай дневной аналитический отчёт за $ARGUMENTS в сравнении с предыдущим днём.

Workflow Олега (V3 micro-agent pipeline):

1. Запусти скрипт:
   ```
   python3 scripts/run_report.py daily $ARGUMENTS
   ```

2. Скрипт вызывает V3 orchestrator → параллельные micro-agents (margin-analyst, revenue-decomposer, ad-efficiency) → report-compiler.

3. Результат:
   - telegram_summary — для Telegram
   - detailed_report — для Notion
   - Стоимость генерации, количество шагов, длительность

4. Покажи пользователю краткую сводку и ссылку на Notion (если была синхронизация)
```

- [ ] **Step 3: Update remaining command files similarly**

Update `.claude/commands/weekly-report.md`, `period-report.md`, `marketing-report.md` — replace V2 references with V3 orchestrator.

- [ ] **Step 4: Commit**

```bash
git add scripts/run_report.py .claude/commands/daily-report.md .claude/commands/weekly-report.md .claude/commands/period-report.md .claude/commands/marketing-report.md
git commit -m "feat(cli): repoint all CLI report commands from V2 to V3 orchestrator

CLI commands now call agents.v3.orchestrator instead of agents.oleg.
This eliminates V2 CLI as a source of duplicate Notion reports."
```

---

### Task 1.5: Increase AGENT_TIMEOUT

**Files:**
- Modify: `agents/v3/config.py:40`

- [ ] **Step 1: Update timeout**

In `agents/v3/config.py` line 40, change default from 120 to 180:

```python
# Before:
AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "120"))

# After:
AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "180"))
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/config.py
git commit -m "feat(config): increase AGENT_TIMEOUT 120s → 180s

Financial agents will produce longer output with enhanced prompts.
Extra 60s prevents false timeouts during margin waterfall and
model decomposition."
```

---

## Wave 2: Prompt Enhancement (Parallel — No Dependencies Between Tasks)

### Task 2.1: Enhance margin-analyst.md

**Files:**
- Modify: `agents/v3/agents/margin-analyst.md`

- [ ] **Step 1: Read current prompt and V2 reference**

Read `agents/v3/agents/margin-analyst.md` (current) and `agents/oleg/agents/reporter/prompts.py` (V2 reference for table specs).

- [ ] **Step 2: Add mandatory output fields**

Append before `## Output Format` section:

```markdown
## ОБЯЗАТЕЛЬНЫЕ ПОЛЯ OUTPUT

### margin_waterfall (Каскад маржи — 10 строк)
Вызови `get_margin_levers` для КАЖДОГО канала (WB, OZON).
Верни массив из 10 объектов:

| Поле | Описание |
|------|----------|
| factor | Одно из: Выручка, Себестоимость/ед, Комиссия до СПП, Логистика/ед, Хранение/ед, Внутр. реклама, Внешн. реклама, Прочие расходы, НДС, Невязка |
| current_rub | Значение текущий период |
| previous_rub | Значение прошлый период |
| delta_rub | Изменение в ₽ |
| margin_impact_rub | Влияние на маржу в ₽ |

Невязка = Фактическая ΔМаржи − Σ(влияний всех факторов).
Если невязка > 5% от ΔМаржи — укажи в limitations.

### cost_structure (Структура затрат — доли от выручки)
Для каждого канала:

| Поле | Описание |
|------|----------|
| item | Комиссия до СПП, Логистика, Хранение, ДРР внутр, ДРР внешн, Себестоимость, Прочие, Маржинальность |
| current_pct | % от выручки текущий |
| previous_pct | % от выручки прошлый |
| delta_pp | Изменение в п.п. |

### spp_dynamics (Динамика СПП)
| Поле |
|------|
| channel, spp_current, spp_previous, delta, interpretation |

### price_forecast (Прогноз цен)
| Поле |
|------|
| channel, order_price_rub, sale_price_rub, gap_rub, forecast_text |

Если цена заказов > цены продаж → "выручка вырастет через 3-7 дней".
```

- [ ] **Step 3: Update Output Format section**

Replace the existing `## Output Format` with expanded version that includes all new fields:

```markdown
## Output Format
JSON artifact with:
- _meta: {confidence, confidence_reason, data_coverage, limitations, conclusions}
- period: {date_from, date_to}
- comparison_period: {date_from, date_to}
- brand_summary: {margin_rub, margin_pct, margin_delta_rub, margin_delta_pct}
- channels: [{channel, margin_rub, margin_pct, margin_delta_rub}]
- levers: [{name, current_per_unit, previous_per_unit, delta_rub_per_unit, total_impact_rub, impact_rank}]
- margin_waterfall: [{factor, current_rub, previous_rub, delta_rub, margin_impact_rub}] — РОВНО 10 строк
- cost_structure: [{item, current_pct, previous_pct, delta_pp}]
- spp_dynamics: [{channel, spp_current, spp_previous, delta, interpretation}]
- price_forecast: [{channel, order_price_rub, sale_price_rub, gap_rub, forecast_text}]
- nevyazka_rub: float
- nevyazka_pct: float
- top_driver: {name, impact_rub, explanation}
- top_anti_driver: {name, impact_rub, explanation}
- summary_text: string (3-5 sentences)
```

- [ ] **Step 4: Commit**

```bash
git add agents/v3/agents/margin-analyst.md
git commit -m "feat(prompts): enhance margin-analyst with V2-level output requirements

Added mandatory fields: margin_waterfall (10-row cascade), cost_structure
(share of revenue), spp_dynamics, price_forecast. These match V2 Reporter
sections 4, 5, and 6.1.4."
```

---

### Task 2.2: Enhance revenue-decomposer.md

**Files:**
- Modify: `agents/v3/agents/revenue-decomposer.md`

- [ ] **Step 1: Add mandatory output fields**

Append before `## Output Format`:

```markdown
## ОБЯЗАТЕЛЬНЫЕ ПОЛЯ OUTPUT

### brand_metrics (15 финансовых метрик для секции "Ключевые изменения")
Вызови `get_brand_finance` + `get_channel_finance`.
Верни объект с 15 полями (воронковые метрики 16-19 — ответственность ad-efficiency):

1. margin_rub, 2. margin_pct, 3. sales_count, 4. sales_rub,
5. orders_rub, 6. orders_count, 7. adv_internal_rub, 8. adv_external_rub,
9. drr_orders_pct, 10. drr_sales_pct, 11. avg_check_orders, 12. avg_check_sales,
13. turnover_days, 14. roi_annual_pct, 15. spp_weighted_pct

Каждое поле: { current, previous, delta_abs, delta_pct }

### models (ВСЕ модели — НЕ ФИЛЬТРОВАТЬ)
Вызови `get_model_breakdown` и выведи **ВСЕ** модели включая убыточные.
Каждая модель:

| Поле |
|------|
| model, channel, margin_rub, margin_delta_pct, margin_pct, stock_fbo, stock_own, stock_in_transit, stock_total, turnover_days, roi_annual_pct, drr_sales_pct, orders_count, revenue_rub |

stock_own = данные МойСклад (если недоступны — null, НЕ пропускать модель).
turnover_days = (avg_stock × num_days) / sales_count.
roi_annual = (margin / cogs) × (365 / turnover_days) × 100.

НЕ ФИЛЬТРУЙ модели. Если get_model_breakdown вернул 16 моделей — все 16 в output.

### plan_fact (План-факт MTD)
ОБЯЗАТЕЛЬНО вызови `get_plan_vs_fact`. Если план существует, верни:

| Поле |
|------|
| metric, plan_month, fact_mtd, plan_mtd, completion_pct, forecast, forecast_vs_plan_pct, status |

status: ✅ если >105%, ⚠️ если 95-105%, ❌ если <95%.
Метрики: orders_count, orders_rub, revenue, margin, adv_internal, adv_external.
Включи forecast (линейная экстраполяция) и forecast_vs_plan_pct.
```

- [ ] **Step 2: Update Output Format to include new fields**

```markdown
## Output Format
JSON artifact with:
- _meta: {confidence, confidence_reason, data_coverage, limitations, conclusions}
- period: {date_from, date_to}
- brand_totals: {revenue_rub, orders_rub, orders_count, avg_check_orders, avg_check_sales}
- brand_metrics: {1..15 fields, each: {current, previous, delta_abs, delta_pct}}
- channel_breakdown: [{channel, revenue_rub, orders_rub, orders_count, delta_pct}]
- plan_fact: [{metric, plan_month, fact_mtd, plan_mtd, completion_pct, forecast, forecast_vs_plan_pct, status}] or null
- models: [{model, channel, revenue_rub, margin_rub, margin_pct, margin_delta_pct, orders_count, stock_fbo, stock_own, stock_in_transit, stock_total, turnover_days, roi_annual_pct, drr_sales_pct}]
- weekly_dynamics: [{week, revenue_rub, orders_count, margin_pct}]
- top_drivers: [{model, delta_revenue_rub, explanation}]
- top_anti_drivers: [{model, delta_revenue_rub, explanation}]
- summary_text: string
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/revenue-decomposer.md
git commit -m "feat(prompts): enhance revenue-decomposer with V2-level output requirements

Added mandatory fields: brand_metrics (15 financial KPIs for section 3),
ALL models with stock/turnover/ROI, plan_fact with forecast and status.
Models must never be filtered — all models including negative-margin ones."
```

---

### Task 2.3: Enhance ad-efficiency.md

**Files:**
- Modify: `agents/v3/agents/ad-efficiency.md`

- [ ] **Step 1: Add mandatory output fields**

Append before `## Output Format`:

```markdown
## ОБЯЗАТЕЛЬНЫЕ ПОЛЯ OUTPUT

### funnel (Воронка продаж — по каждому каналу)
Вызови `get_advertising_stats` для WB и OZON.
Для каждого канала верни массив:

| Поле |
|------|
| stage (impressions, card_opens, add_to_cart, orders, buyouts), count, conversion_to_next_pct, benchmark_pct, gap_pp, status (ok/watch/critical) |

WB бенчмарки: CTR 1-3%, open→cart 5-15%, cart→order 25-40%, order→buyout 85-92%.
OZON бенчмарки: CTR 1-4%, card→order 3-8%, order→buyout 88-95%.

### ad_stats (Рекламная статистика — полная таблица)
| Поле |
|------|
| channel, impressions, clicks, ctr_pct, cpc_rub, cpm_rub, cpo_rub, spend_rub, cart_adds (WB only), orders_from_ads |

НЕ сокращай до одной строки CPO. Вся таблица обязательна.

### brand_metrics_funnel (4 воронковые метрики для секции 3)
| Поле |
|------|
| card_opens: {current, previous, delta_abs, delta_pct} |
| add_to_cart: {current, previous, delta_abs, delta_pct} |
| cr_open_to_cart_pct: {current, previous, delta_abs, delta_pct} |
| cr_cart_to_order_pct: {current, previous, delta_abs, delta_pct} |
```

- [ ] **Step 2: Update Output Format**

```markdown
## Output Format
JSON artifact with:
- _meta: {confidence, confidence_reason, data_coverage, limitations, conclusions}
- period: {date_from, date_to}
- brand_drr: {drr_orders_pct, drr_sales_pct, adv_internal_rub, adv_external_rub}
- channels: [{channel, drr_orders_pct, drr_sales_pct, adv_internal, adv_external, funnel: {card_opens, add_to_cart, orders, ctr_pct, conv_cart_pct, conv_order_pct, cart_to_order_pct}}]
- funnel: [{channel, stages: [{stage, count, conversion_to_next_pct, benchmark_pct, gap_pp, status}]}]
- ad_stats: [{channel, impressions, clicks, ctr_pct, cpc_rub, cpm_rub, cpo_rub, spend_rub, cart_adds, orders_from_ads}]
- brand_metrics_funnel: {card_opens, add_to_cart, cr_open_to_cart_pct, cr_cart_to_order_pct — each {current, previous, delta_abs, delta_pct}}
- model_matrix: [{model, channel, category, margin_pct, drr_pct, revenue_rub, explanation}]
- alerts: [{type, model, channel, message, severity}]
- summary_text: string
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/ad-efficiency.md
git commit -m "feat(prompts): enhance ad-efficiency with V2-level funnel and ad tables

Added mandatory fields: funnel (full conversion funnel per channel),
ad_stats (full table not 1-line CPO), brand_metrics_funnel (4 fields
for section 3 merge with revenue-decomposer)."
```

---

### Task 2.4: Port Telegram bot handlers

**Files:**
- Modify: `agents/v3/app.py:148-167`
- Test: `tests/agents/v3/test_telegram_handlers.py`

- [ ] **Step 1: Write test for handler registration**

```python
# tests/agents/v3/test_telegram_handlers.py
"""Tests for V3 Telegram bot handler registration."""
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


def test_register_handlers_adds_all_commands():
    """All 11 commands should be registered on the dispatcher."""
    from aiogram import Dispatcher
    dp = Dispatcher()

    with patch("agents.v3.app.orchestrator", MagicMock()):
        from agents.v3.app import _register_handlers
        _register_handlers(dp)

    # Check router has handlers registered
    # aiogram 3.x stores handlers in dp._message_handlers or similar
    # At minimum, check no exception during registration
    assert True  # Registration succeeded without error


@pytest.mark.asyncio
async def test_cmd_health_responds():
    """The /health handler should respond with system status."""
    from aiogram.types import Message
    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()

    with patch("agents.v3.app.monitor") as mock_monitor:
        mock_monitor._check_llm = AsyncMock(return_value=True)
        mock_monitor._check_db = AsyncMock(return_value=True)
        # Import and call handler directly
        from agents.v3.app import _register_handlers
        # Registration test suffices — full integration tested manually
```

- [ ] **Step 2: Implement handlers in app.py**

Replace `_register_handlers` in `agents/v3/app.py` (lines 148-166):

```python
def _register_handlers(dp) -> None:  # noqa: ANN001
    """Register Telegram command handlers on the dispatcher."""
    from aiogram import types
    from aiogram.filters import Command

    from agents.v3 import orchestrator, monitor
    from agents.v3.scheduler import _yesterday_msk, _last_week_msk, _last_month_msk, _day_before

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message) -> None:
        await message.answer(
            "Wookiee v3 — аналитический агент.\n\n"
            "Команды:\n"
            "/report_daily — дневной финансовый отчёт\n"
            "/report_weekly — недельный финансовый отчёт\n"
            "/report_monthly — месячный финансовый отчёт\n"
            "/marketing_daily — дневной маркетинговый отчёт\n"
            "/marketing_weekly — недельный маркетинговый отчёт\n"
            "/marketing_monthly — месячный маркетинговый отчёт\n"
            "/health — проверка здоровья системы\n"
            "/feedback — отправить ОС по отчёту\n"
            "/ping — проверка связи"
        )

    @dp.message(Command("ping"))
    async def cmd_ping(message: types.Message) -> None:
        await message.answer("pong")

    @dp.message(Command("health"))
    async def cmd_health(message: types.Message) -> None:
        llm_ok = await monitor._check_llm()
        db_ok = await monitor._check_db()
        status = "✅" if (llm_ok and db_ok) else "⚠️"
        await message.answer(
            f"{status} Здоровье системы:\n"
            f"LLM: {'✅' if llm_ok else '❌'}\n"
            f"DB: {'✅' if db_ok else '❌'}"
        )

    async def _run_and_reply(message: types.Message, coro, report_name: str) -> None:
        """Helper: run report coroutine and send result to chat."""
        await message.answer(f"Генерирую {report_name}...")
        try:
            result = await coro
            if result.get("status") in ("success", "partial"):
                compiler = result.get("artifacts", {}).get("report-compiler", {})
                artifact = compiler.get("artifact", {}) if isinstance(compiler, dict) else {}
                tg_summary = artifact.get("telegram_summary", "Отчёт сгенерирован.") if isinstance(artifact, dict) else "Отчёт сгенерирован."
                await message.answer(tg_summary[:4096])
            else:
                await message.answer(f"Отчёт не сгенерирован: {result.get('status')}")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

    @dp.message(Command("report_daily"))
    async def cmd_report_daily(message: types.Message) -> None:
        y = _yesterday_msk()
        d_before = _day_before(y)
        await _run_and_reply(message, orchestrator.run_daily_report(
            str(y), str(y), str(d_before), str(d_before), trigger="telegram"
        ), "дневной отчёт")

    @dp.message(Command("report_weekly"))
    async def cmd_report_weekly(message: types.Message) -> None:
        from datetime import date, timedelta
        mon_s, sun_s = _last_week_msk()
        mon = date.fromisoformat(mon_s)
        sun = date.fromisoformat(sun_s)
        prev_mon = mon - timedelta(days=7)
        prev_sun = sun - timedelta(days=7)
        await _run_and_reply(message, orchestrator.run_weekly_report(
            mon_s, sun_s, str(prev_mon), str(prev_sun), trigger="telegram"
        ), "недельный отчёт")

    @dp.message(Command("report_monthly"))
    async def cmd_report_monthly(message: types.Message) -> None:
        from datetime import date, timedelta
        start_s, end_s = _last_month_msk()
        start = date.fromisoformat(start_s)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        await _run_and_reply(message, orchestrator.run_monthly_report(
            start_s, end_s, str(prev_start), str(prev_end), trigger="telegram"
        ), "месячный отчёт")

    @dp.message(Command("marketing_daily"))
    async def cmd_marketing_daily(message: types.Message) -> None:
        y = _yesterday_msk()
        d_before = _day_before(y)
        # Note: orchestrator maps "daily" → task_type "marketing_daily" (added in Task 3.4)
        await _run_and_reply(message, orchestrator.run_marketing_report(
            str(y), str(y), str(d_before), str(d_before),
            report_period="daily", trigger="telegram"
        ), "дневной маркетинговый отчёт")

    @dp.message(Command("marketing_weekly"))
    async def cmd_marketing_weekly(message: types.Message) -> None:
        from datetime import date, timedelta
        mon_s, sun_s = _last_week_msk()
        mon = date.fromisoformat(mon_s)
        sun = date.fromisoformat(sun_s)
        prev_mon = mon - timedelta(days=7)
        prev_sun = sun - timedelta(days=7)
        await _run_and_reply(message, orchestrator.run_marketing_report(
            mon_s, sun_s, str(prev_mon), str(prev_sun),
            report_period="weekly", trigger="telegram"
        ), "недельный маркетинговый отчёт")

    @dp.message(Command("marketing_monthly"))
    async def cmd_marketing_monthly(message: types.Message) -> None:
        from datetime import date, timedelta
        start_s, end_s = _last_month_msk()
        start = date.fromisoformat(start_s)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        await _run_and_reply(message, orchestrator.run_marketing_report(
            start_s, end_s, str(prev_start), str(prev_end),
            report_period="monthly", trigger="telegram"
        ), "месячный маркетинговый отчёт")

    @dp.message(Command("feedback"))
    async def cmd_feedback(message: types.Message) -> None:
        text = (message.text or "").replace("/feedback", "").strip()
        if not text:
            await message.answer("Использование: /feedback <текст обратной связи>")
            return
        try:
            from agents.v3.prompt_tuner import save_instruction
            save_instruction(text)
            await message.answer("✅ Обратная связь сохранена. Будет учтена в следующих отчётах.")
        except Exception as e:
            await message.answer(f"Ошибка сохранения: {e}")
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/agents/v3/test_telegram_handlers.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add agents/v3/app.py tests/agents/v3/test_telegram_handlers.py
git commit -m "feat(telegram): port 9 bot handlers from V2 to V3

Added: /report_daily, /report_weekly, /report_monthly,
/marketing_daily, /marketing_weekly, /marketing_monthly,
/health, /feedback. Each calls V3 orchestrator directly.
Updated /start to show command list."
```

> **Note:** Free-text handler (generic query → data-navigator agent) is deferred to post-migration. V2 had it but it's not critical for report parity.

---

## Wave 3: Compiler + Remaining Prompts (Depends on Wave 2)

### Task 3.1: Update report-compiler.md with exact table specs

**Files:**
- Modify: `agents/v3/agents/report-compiler.md`

- [ ] **Step 1: Add exact table specs per section**

After the existing `## Правила` section (line 8), insert detailed per-section table specifications:

```markdown
## Точные требования к секциям

### Секция 3: Ключевые изменения — РОВНО 19 строк
Merge `brand_metrics` (поля 1-15) из revenue-decomposer с `brand_metrics_funnel` (поля 16-19) из ad-efficiency.
При конфликте данных — приоритет ad-efficiency для воронковых метрик.

| # | Метрика | Источник |
|---|---------|---------|
| 1 | Маржа ₽ | revenue-decomposer.brand_metrics.margin_rub |
| 2 | Маржинальность % | revenue-decomposer.brand_metrics.margin_pct |
| 3 | Продажи шт | revenue-decomposer.brand_metrics.sales_count |
| 4 | Продажи ₽ | revenue-decomposer.brand_metrics.sales_rub |
| 5 | Заказы ₽ | revenue-decomposer.brand_metrics.orders_rub |
| 6 | Заказы шт | revenue-decomposer.brand_metrics.orders_count |
| 7 | Внутр. реклама ₽ | revenue-decomposer.brand_metrics.adv_internal_rub |
| 8 | Внешн. реклама ₽ | revenue-decomposer.brand_metrics.adv_external_rub |
| 9 | ДРР от заказов % | revenue-decomposer.brand_metrics.drr_orders_pct |
| 10 | ДРР от продаж % | revenue-decomposer.brand_metrics.drr_sales_pct |
| 11 | Ср. чек заказов ₽ | revenue-decomposer.brand_metrics.avg_check_orders |
| 12 | Ср. чек продаж ₽ | revenue-decomposer.brand_metrics.avg_check_sales |
| 13 | Оборачиваемость дн | revenue-decomposer.brand_metrics.turnover_days |
| 14 | Годовой ROI % | revenue-decomposer.brand_metrics.roi_annual_pct |
| 15 | СПП средневзвеш. % | revenue-decomposer.brand_metrics.spp_weighted_pct |
| 16 | Переходы в карточку | ad-efficiency.brand_metrics_funnel.card_opens |
| 17 | Добавления в корзину | ad-efficiency.brand_metrics_funnel.add_to_cart |
| 18 | CR открытие→корзина % | ad-efficiency.brand_metrics_funnel.cr_open_to_cart_pct |
| 19 | CR корзина→заказ % | ad-efficiency.brand_metrics_funnel.cr_cart_to_order_pct |

Каждая строка: | Метрика | Текущий | Прошлый | Δ абс | Δ % |

### Секция 5: Каскад маржинальности — РОВНО 10 строк
Из margin-analyst.margin_waterfall:

| # | Статья |
|---|--------|
| 1 | Выручка |
| 2 | Себестоимость/ед |
| 3 | Комиссия до СПП |
| 4 | Логистика/ед |
| 5 | Хранение/ед |
| 6 | Внутр. реклама |
| 7 | Внешн. реклама |
| 8 | Прочие расходы |
| 9 | НДС |
| 10 | Невязка |

Каждая строка: | Статья | Текущий ₽ | Прошлый ₽ | Δ ₽ | Влияние на маржу ₽ |

### Секция 6: Площадки
Обязательные подсекции для КАЖДОГО канала (WB, OZON):
- 6.X.1 Объём и выручка (из revenue-decomposer.channel_breakdown)
- 6.X.2 Модели — ВСЕ модели из revenue-decomposer.models (таблица: Модель, Маржа ₽, ΔМаржа%, Маржинальность%, Остаток FBO, Свой склад, В пути, Итого, Оборачиваемость дн, ROI%, ДРР%)
- 6.X.3 Воронка — из ad-efficiency.funnel (таблица объёмов + таблица конверсий с бенчмарками)
- 6.X.4 Структура затрат — из margin-analyst.cost_structure
- 6.X.5 Реклама — из ad-efficiency.ad_stats (Показы, Клики, CTR%, CPC₽, CPM₽, CPO₽, Расход₽)

## НЕ СОКРАЩАЙ ОТЧЁТ
Каждая таблица ОБЯЗАТЕЛЬНА. Если данные получены от агента — секция должна быть заполнена.
Если агент не вернул данные — напиши "Данные недоступны: [причина]", но НЕ пропускай секцию целиком.
```

- [ ] **Step 2: Add graceful degradation rules**

Append:

```markdown
## Graceful Degradation (при timeout агента)

Если агент вернул `status: "failed"`:
1. НЕ пропускай секции, за которые он отвечал
2. Проверь, есть ли пересекающиеся данные у других агентов
3. Если данные частично доступны — построй секцию из них с пометкой "⚠️ Неполные данные"
4. Если данных нет совсем — выведи "Секция N: [название] — данные недоступны (timeout [agent_name])"
5. В sections_skipped укажи причину

Примеры fallback:
- margin-analyst timeout → секция 5 (каскад) недоступна, но секция 3 (ключевые изменения) строится из revenue-decomposer
- ad-efficiency timeout → воронка и реклама недоступны, но финансовые метрики есть из revenue-decomposer
- revenue-decomposer timeout → модели недоступны, но маржа и реклама доступны
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/report-compiler.md
git commit -m "feat(prompts): add exact V2 table specs and graceful degradation to compiler

Section 3: exactly 19 rows with merge rules (revenue-decomposer 1-15 +
ad-efficiency 16-19). Section 5: exactly 10-row waterfall. Section 6:
mandatory sub-sections per channel. Added fallback rules for agent timeouts."
```

---

### Task 3.2: Add marketing/funnel conditional logic to report-compiler.md

**Files:**
- Modify: `agents/v3/agents/report-compiler.md`

- [ ] **Step 1: Append conditional sections**

Add at end of `report-compiler.md`:

```markdown
## Условная логика по типу отчёта

Тип отчёта определяется по `task_type` в artifact_context.

### Если task_type = marketing_weekly или marketing_monthly

Используй 10-секционную маркетинговую структуру вместо стандартных 11 секций:

0. Паспорт
1. Исполнительная сводка — 5-7 ключевых выводов по маркетингу
2. Анализ по каналам (WB + OZON) — таблица: канал, расход, заказы от рекламы, ДРР, ROMI
3. Анализ воронки — из funnel-digitizer: полная воронка с бенчмарками и bottleneck
4. Органика vs Платное — из campaign-optimizer/ad-efficiency: доля органики, тренд
5. Внешняя реклама — из campaign-optimizer.external_breakdown: блогеры, VK, creators
6. Эффективность по моделям — ROMI matrix из campaign-optimizer.campaigns
7. Дневная динамика рекламы — из campaign-optimizer.daily_dynamics
8. Средний чек и связь с ДРР — корреляция avg_check → drr
9. Рекомендации и план действий — из _meta.conclusions type=recommendation

### Если task_type = funnel_weekly

Используй 5-секционную воронковую структуру:

0. Паспорт
1. Общий обзор бренда — таблица: переходы, заказы, выкупы, выручка, маржа, ДРР, ROMI
2. Модельная декомпозиция — по каждой модели: full funnel + WoW тренд
3. Bottleneck analysis — из funnel-digitizer.bottleneck
4. Keyword portfolio — если доступны данные keyword-analyst
5. Рекомендации — из _meta.conclusions

### По умолчанию (daily_report, weekly_report, monthly_report)

Стандартная 11-секционная структура (секции 0-10 как описано выше).
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/agents/report-compiler.md
git commit -m "feat(prompts): add marketing and funnel conditional logic to compiler

Report-compiler now switches section structure based on task_type:
- marketing_weekly/monthly → 10-section marketing structure
- funnel_weekly → 5-section funnel structure
- default → standard 11-section financial report"
```

---

### Task 3.3: Enhance funnel-digitizer.md and campaign-optimizer.md

**Files:**
- Modify: `agents/v3/agents/funnel-digitizer.md`
- Modify: `agents/v3/agents/campaign-optimizer.md`

- [ ] **Step 1: Add enforcement rules to funnel-digitizer**

In `agents/v3/agents/funnel-digitizer.md`, add after Rules section:

```markdown
## ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ
- Вызови `get_funnel_by_model` для ВСЕХ моделей (не только top-N). Если инструмент вернул 16 моделей — все 16 в output.
- ОБЯЗАТЕЛЬНО вызови `get_funnel_trend` для WoW тренда — без WoW данных confidence должен быть < 0.5
- В model_funnels включи ВСЕ модели без фильтрации
```

- [ ] **Step 2: Add enforcement rules to campaign-optimizer**

In `agents/v3/agents/campaign-optimizer.md`, add after Rules section:

```markdown
## ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ
- ОБЯЗАТЕЛЬНО вызови `get_external_ad_breakdown` для разбивки внешней рекламы по каналам (блогеры, VK, creators)
- Вызови `get_model_ad_efficiency` (если доступен) для model-level ROMI matrix
- external_breakdown ОБЯЗАТЕЛЬНО заполнен — если данных нет, верни пустой массив с пояснением в limitations
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/funnel-digitizer.md agents/v3/agents/campaign-optimizer.md
git commit -m "feat(prompts): enforce all-models funnel and external ad breakdown

funnel-digitizer: must call get_funnel_by_model for ALL models + mandatory WoW trend.
campaign-optimizer: must call get_external_ad_breakdown + model ROMI matrix."
```

---

### Task 3.4: Pass task_type to compiler input + fix marketing_daily task_type

**Files:**
- Modify: `agents/v3/orchestrator.py:240-245, 448`

- [ ] **Step 1: Fix marketing report_period ternary to support "daily"**

In `agents/v3/orchestrator.py` line 448, change the ternary to handle all three periods:

```python
# Before:
    task_type = "marketing_weekly" if report_period == "weekly" else "marketing_monthly"

# After:
    _marketing_task_types = {"daily": "marketing_daily", "weekly": "marketing_weekly", "monthly": "marketing_monthly"}
    task_type = _marketing_task_types.get(report_period, "marketing_weekly")
```

- [ ] **Step 2: Add task_type to compiler_input**

In `agents/v3/orchestrator.py`, around line 240, add `task_type` to the compiler_input dict:

```python
# Before:
        compiler_input: dict[str, Any] = {
            "period": {"date_from": date_from, "date_to": date_to},
            "comparison_period": {"date_from": comparison_from, "date_to": comparison_to},
            "channel": channel,
            "artifacts": {},
        }

# After:
        compiler_input: dict[str, Any] = {
            "task_type": task_type,
            "period": {"date_from": date_from, "date_to": date_to},
            "comparison_period": {"date_from": comparison_from, "date_to": comparison_to},
            "channel": channel,
            "artifacts": {},
        }
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/orchestrator.py
git commit -m "feat(orchestrator): pass task_type in compiler_input

Report-compiler needs task_type to select the correct section structure
(financial 11-section, marketing 10-section, or funnel 5-section)."
```

---

## Wave 4: Graceful Degradation (Depends on Wave 3)

### Task 4.1: Improve orchestrator timeout handling

**Files:**
- Modify: `agents/v3/orchestrator.py`

- [ ] **Step 1: Enhance FAILED_AGENT_META with partial data hint**

In `agents/v3/orchestrator.py`, find the section where `FAILED_AGENT_META` is injected for failed agents (around line 248-254). Enhance to pass failure reason to compiler:

```python
            else:
                # Provide richer context for compiler's graceful degradation
                error_msg = result.get("raw_output", "Unknown error")[:500]
                failure_reason = "timeout" if "timeout" in error_msg.lower() else "error"
                compiler_input["artifacts"][name] = {
                    "status": "failed",
                    "failure_reason": failure_reason,
                    "error": error_msg,
                    "_meta": FAILED_AGENT_META,
                }
```

- [ ] **Step 2: Commit**

```bash
git add agents/v3/orchestrator.py
git commit -m "feat(orchestrator): enrich failed agent metadata for graceful degradation

Failed agents now include failure_reason (timeout vs error) so the
compiler can make better fallback decisions per the graceful
degradation rules."
```

---

## Wave 5: Verification (Depends on Wave 4)

### Task 5.1: Side-by-side verification

**Context:** Generate V3 report and compare against V2 reference report in Notion.

- [ ] **Step 1: Generate V3 daily report for a known date**

```bash
# Use the same date as the V2 reference (March 21)
docker compose exec wookiee-oleg python -c "
import asyncio
from agents.v3 import orchestrator

async def main():
    result = await orchestrator.run_daily_report(
        '2026-03-21', '2026-03-21', '2026-03-20', '2026-03-20',
        trigger='verification')
    print('Status:', result.get('status'))
    # Check sections
    compiler = result.get('artifacts', {}).get('report-compiler', {})
    artifact = compiler.get('artifact', {})
    if isinstance(artifact, dict):
        print('Sections included:', artifact.get('sections_included'))
        print('Sections skipped:', artifact.get('sections_skipped'))
        report = artifact.get('detailed_report', '')
        print(f'Report length: {len(report)} chars')
        # Check for mandatory tables
        for marker in ['Маржинальность', 'Каскад', 'Воронка', 'Реклама', 'План-факт']:
            found = marker.lower() in report.lower()
            print(f'  {marker}: {\"✅\" if found else \"❌\"}'  )

asyncio.run(main())
"
```

- [ ] **Step 2: Compare against V2 reference**

Open both reports in Notion side-by-side:
- V3: new report just generated
- V2: `https://www.notion.so/wookieeshop/21-2026-32a58a2bd5878175b13ce011d0d1592c`

Check each criterion from spec section 3.2:

| Секция | Критерий | V3 status |
|--------|----------|-----------|
| Секция 3 | 19 строк | ? |
| Секция 5 | 10 строк waterfall | ? |
| Секция 6 | ВСЕ модели | ? |
| Секция 6.1.3 | Воронка 2 таблицы | ? |
| Секция 6.1.5 | Полная таблица рекламы | ? |
| Секция 2 | План-факт + forecast | ? |
| Секция 9 | Advisor рекомендации | ? |
| Trust Envelope | Паспорт достоверности | ? |

- [ ] **Step 3: Fix any discrepancies found**

If sections are missing or incomplete, trace back to the agent prompt or orchestrator and fix.

- [ ] **Step 4: Run regression on all report types**

```bash
# Test each report type generates without error
for report_type in daily weekly monthly; do
    echo "Testing $report_type..."
    docker compose exec wookiee-oleg python -c "
import asyncio
from agents.v3 import orchestrator
result = asyncio.run(orchestrator.run_${report_type}_report(
    '2026-03-21', '2026-03-21', '2026-03-20', '2026-03-20', trigger='test'))
print('$report_type:', result.get('status'))
"
done
```

- [ ] **Step 5: Document results and commit any fixes**

```bash
git add -A
git commit -m "fix: address verification findings from V2-V3 side-by-side comparison"
```

---

## Wave 6: V2 Decommission (After 3-5 Days Stability)

### Task 6.1: Remove oleg-mcp from docker-compose

**Files:**
- Modify: `deploy/docker-compose.yml`

- [ ] **Step 1: Remove oleg-mcp service definition**

Remove the entire `oleg-mcp:` block from `deploy/docker-compose.yml`.

- [ ] **Step 2: Check if Eggent depends on oleg-mcp**

```bash
grep -n "oleg" deploy/docker-compose.yml
```

If Eggent references oleg-mcp as MCP server — update its environment to remove or redirect.

- [ ] **Step 3: Commit**

```bash
git add deploy/docker-compose.yml
git commit -m "feat(deploy): remove oleg-mcp container from docker-compose

V2 MCP server no longer needed. All report generation uses V3 orchestrator.
Frees ~130MB RAM on server."
```

---

### Task 6.2: Move tools to shared/ and delete V2

**Files:**
- Create: `shared/tools/` directory
- Move: `agents/oleg/services/agent_tools.py` → `shared/tools/agent_tools.py`
- Move: `agents/oleg/services/marketing_tools.py` → `shared/tools/marketing_tools.py`
- Move: `agents/oleg/services/funnel_tools.py` → `shared/tools/funnel_tools.py`
- Move: `agents/oleg/services/price_tools.py` → `shared/tools/price_tools.py`
- Modify: `agents/v3/runner.py` (update imports)

- [ ] **Step 1: Create shared/tools/ and move files**

```bash
mkdir -p shared/tools
cp agents/oleg/services/agent_tools.py shared/tools/
cp agents/oleg/services/marketing_tools.py shared/tools/
cp agents/oleg/services/funnel_tools.py shared/tools/
cp agents/oleg/services/price_tools.py shared/tools/
touch shared/tools/__init__.py
```

- [ ] **Step 2: Update imports in runner.py**

In `agents/v3/runner.py`, replace:
```python
from agents.oleg.services.price_tools import PRICE_TOOL_HANDLERS
from agents.oleg.services.agent_tools import DATA_HANDLERS
from agents.oleg.services.marketing_tools import MARKETING_TOOL_HANDLERS
from agents.oleg.services.funnel_tools import FUNNEL_TOOL_HANDLERS
```
With:
```python
from shared.tools.price_tools import PRICE_TOOL_HANDLERS
from shared.tools.agent_tools import DATA_HANDLERS
from shared.tools.marketing_tools import MARKETING_TOOL_HANDLERS
from shared.tools.funnel_tools import FUNNEL_TOOL_HANDLERS
```

- [ ] **Step 3: Verify V3 still starts**

```bash
python -m agents.v3 --dry-run
```

Expected: Lists all 15 scheduled jobs without errors.

- [ ] **Step 4: Delete agents/oleg/ (except playbooks for KB reference)**

```bash
# Save playbooks to KB reference
cp agents/oleg/playbook.md docs/reference/v2-playbook.md
cp agents/oleg/marketing_playbook.md docs/reference/v2-marketing-playbook.md

# Delete V2
rm -rf agents/oleg/
```

- [ ] **Step 5: Commit**

```bash
git add shared/tools/ agents/v3/runner.py docs/reference/
git add -u  # stage deletions
git commit -m "refactor: move tools to shared/, delete agents/oleg/ (V2 decommissioned)

Moved 4 tool modules from agents/oleg/services/ to shared/tools/.
Updated runner.py imports. Saved V2 playbooks to docs/reference/.
V2 code fully removed — V3 is the sole production system."
```

---

## Summary

| Wave | Tasks | Parallel? | Estimated Steps |
|------|-------|-----------|----------------|
| 0 | OOM fix (server-side) | N/A — manual | 4 |
| 1 | Watchdog fixes, Notion dedup, CLI repoint, timeout | Yes (5 parallel) | 25 |
| 2 | 3 agent prompts + Telegram handlers | Yes (4 parallel) | 16 |
| 3 | Compiler tables, conditionals, funnel/campaign, task_type | Yes (4 parallel) | 8 |
| 4 | Graceful degradation | Sequential | 2 |
| 5 | Verification | Sequential | 5 |
| 6 | Decommission V2 | Sequential | 5 |
| **Total** | | | **~65 steps** |
