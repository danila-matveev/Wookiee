# Advisor Phase 3 — Observability, KB Integration & Self-Learning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить observability (логирование каждого прогона advisor chain), подключить KB-паттерны из Supabase к signal detection и validator, реализовать механизм предложения новых паттернов advisor'ом.

**Architecture:** recommendation_log в SQLite (через StateStore, как все другие логи агентов) | kb_patterns в Supabase (конфигурационные данные) | Self-Learning через new_patterns в advisor output.

**Tech Stack:** Python 3.11, SQLite (StateStore), Supabase (kb_patterns), existing BaseAgent/ReactLoop.

**Spec:** `docs/superpowers/specs/2026-03-21-advisor-phase3-observability-design.md`

---

## File Structure (what we're building)

```
# MODIFY
agents/oleg/storage/state_store.py         # + recommendation_log table + log_recommendation()
agents/oleg/orchestrator/orchestrator.py   # _log_recommendation(), kb_patterns wiring
agents/oleg/agents/advisor/prompts.py      # new_patterns в output schema

# CREATE
shared/signals/kb_patterns.py             # load_kb_patterns(), save_proposed_patterns()

# TESTS
tests/agents/oleg/storage/test_recommendation_log.py
tests/shared/signals/test_kb_patterns.py
tests/agents/oleg/orchestrator/test_advisor_logging.py
```

---

## Batch A: Observability (no external dependencies)

### Task 1: Add recommendation_log table to StateStore

**Files:**
- Modify: `agents/oleg/storage/state_store.py`

**What to do:**
- [ ] Add `CREATE TABLE IF NOT EXISTS recommendation_log (...)` to `init_db()` method, after existing tables
- [ ] Schema (SQLite):
  ```sql
  CREATE TABLE IF NOT EXISTS recommendation_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      report_date TEXT NOT NULL,
      report_type TEXT NOT NULL,
      context TEXT NOT NULL DEFAULT 'financial',
      channel TEXT,
      signals_count INTEGER DEFAULT 0,
      recommendations_count INTEGER DEFAULT 0,
      validation_verdict TEXT DEFAULT 'skipped',
      validation_attempts INTEGER DEFAULT 1,
      signals TEXT,
      recommendations TEXT,
      validation_details TEXT,
      new_patterns TEXT,
      advisor_cost_usd REAL DEFAULT 0,
      validator_cost_usd REAL DEFAULT 0,
      total_duration_ms INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- [ ] Add `import json` to state_store.py if not already present
- [ ] Add `log_recommendation()` method following same pattern as `log_report()`:
  ```python
  def log_recommendation(
      self, report_date: str, report_type: str, context: str = "financial",
      channel: str = None, signals_count: int = 0,
      recommendations_count: int = 0, validation_verdict: str = "skipped",
      validation_attempts: int = 1, signals: list = None,
      recommendations: list = None, validation_details: dict = None,
      new_patterns: list = None, advisor_cost_usd: float = 0.0,
      validator_cost_usd: float = 0.0, total_duration_ms: int = 0,
  ) -> int:
  ```
- [ ] JSON-encode `signals`, `recommendations`, `validation_details`, `new_patterns` before INSERT
- [ ] Add `get_recommendation_stats(days: int = 7) -> dict` method — returns basic stats (count, avg signals, pass rate)

**Acceptance:**
- `StateStore.init_db()` creates `recommendation_log` table
- `log_recommendation()` inserts row, returns row id
- `get_recommendation_stats()` returns dict with counts

---

### Task 2: Tests for recommendation_log

**Files:**
- Create: `tests/agents/oleg/storage/test_recommendation_log.py`

**What to do:**
- [ ] Test `log_recommendation()` inserts and returns id
- [ ] Test `log_recommendation()` serializes JSON fields correctly
- [ ] Test `get_recommendation_stats()` returns correct counts
- [ ] Test graceful handling of empty/None JSON fields
- [ ] Use tmp_path fixture for SQLite DB (not production path)

**Acceptance:**
- All tests pass with `python3 -m pytest tests/agents/oleg/storage/test_recommendation_log.py -v`

---

### Task 3: Wire _log_recommendation into orchestrator

**Files:**
- Modify: `agents/oleg/orchestrator/orchestrator.py`

**What to do:**
- [ ] Add `from datetime import date` import if not present
- [ ] Add `_log_recommendation(self, result, report_type, duration_ms)` method to `OlegOrchestrator`
- [ ] Method uses `StateStore` to log recommendation (see spec for exact parameters)
- [ ] Wrap in try/except — logging failure MUST NOT break the chain
- [ ] Call `_log_recommendation()` at end of `_run_advisor_chain()`, before return, for ALL branches (pass, fail, retry fallback)
- [ ] Track duration: `advisor_start = time.time()` at start of `_run_advisor_chain()`, calculate `duration_ms` at end

**Key constraint:** `_run_advisor_chain()` is async but `StateStore` is sync — call directly (SQLite is fast, no need for `asyncio.to_thread`)

**Acceptance:**
- Every `_run_advisor_chain()` call creates a `recommendation_log` entry
- If StateStore fails, chain still returns normally (graceful degradation)

---

## Batch B: KB Patterns (depends on Supabase)

### Task 4: Create kb_patterns table in Supabase

**Files:**
- Create: `migrations/004_kb_patterns.sql` (manual apply)

**What to do:**
- [ ] SQL migration:
  ```sql
  CREATE TABLE IF NOT EXISTS hub.kb_patterns (
      id SERIAL PRIMARY KEY,
      pattern_name VARCHAR(200) NOT NULL UNIQUE,
      description TEXT NOT NULL,
      category VARCHAR(50) NOT NULL,
      source_tag VARCHAR(50) NOT NULL,
      trigger_condition JSONB NOT NULL,
      severity VARCHAR(10) DEFAULT 'info',
      hint_template TEXT,
      verified BOOLEAN DEFAULT false,
      created_by VARCHAR(50) DEFAULT 'system',
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
  );
  ALTER TABLE hub.kb_patterns ENABLE ROW LEVEL SECURITY;
  CREATE POLICY service_full ON hub.kb_patterns FOR ALL TO postgres USING (true) WITH CHECK (true);
  CREATE INDEX idx_kb_patterns_source ON hub.kb_patterns(source_tag);
  CREATE INDEX idx_kb_patterns_verified ON hub.kb_patterns(verified);
  ```
- [ ] Seed script: INSERT all BASE_PATTERNS from `shared/signals/patterns.py` that have `trigger_condition` with `verified=true, created_by='system'`

**Acceptance:**
- Table exists in Supabase with RLS
- Seed data matches BASE_PATTERNS count

---

### Task 5: KB pattern loader

**Files:**
- Create: `shared/signals/kb_patterns.py`

**What to do:**
- [ ] `load_kb_patterns(verified_only: bool = True) -> list[dict]` — loads from Supabase `hub.kb_patterns`
- [ ] Use `shared/config.py` for Supabase connection (same as other data_layer modules)
- [ ] Return list of dicts: `{name, description, category, source_tag, trigger_condition, severity, hint_template}`
- [ ] Graceful: if Supabase unavailable, log warning and return `[]`
- [ ] `save_proposed_patterns(patterns: list[dict]) -> int` — inserts with `verified=false, created_by='advisor'`
- [ ] Upsert by `pattern_name` — if pattern exists, skip (don't overwrite)

**Acceptance:**
- `load_kb_patterns()` returns seeded patterns
- `save_proposed_patterns()` inserts new patterns with verified=false
- Network failure → returns empty list, no exception

---

### Task 6: Wire kb_patterns into signal detection

**Files:**
- Modify: `agents/oleg/orchestrator/orchestrator.py`

**What to do:**
- [ ] In `_run_signal_detection()`, replace TODO with actual KB loading:
  ```python
  from shared.signals.kb_patterns import load_kb_patterns
  kb_patterns = load_kb_patterns(verified_only=True)
  ```
- [ ] Filter kb_patterns by source_tag before passing to `detect_signals()`:
  ```python
  relevant_kb = [p for p in kb_patterns if p["source_tag"] == source_tag]
  detect_signals(data=item, kb_patterns=relevant_kb)
  ```
- [ ] Store `kb_patterns` as return value from `_run_signal_detection()` (or instance var) so it's available for validator
- [ ] Graceful: if `load_kb_patterns()` fails, use `kb_patterns=[]` (existing behavior)

**Acceptance:**
- `detect_signals()` receives `kb_patterns` parameter
- KB patterns are filtered by `source_tag`
- Failure doesn't break signal detection

---

### Task 7: Wire kb_patterns into Validator instruction

**Files:**
- Modify: `agents/oleg/orchestrator/orchestrator.py`

**What to do:**
- [ ] In `_run_advisor_chain()`, pass `kb_patterns` to validator instruction:
  ```python
  validator_instruction = (
      f"Проверь рекомендации от Advisor.\n\n"
      f"recommendations = {json.dumps(recommendations)}\n\n"
      f"signals = {json.dumps(signals)}\n\n"
      f"structured_data = {json.dumps(structured_data)}\n\n"
      f"kb_patterns = {json.dumps(kb_patterns)}"  # НОВОЕ
  )
  ```
- [ ] Also pass to retry revalidation instruction

**Acceptance:**
- Validator instruction includes `kb_patterns` JSON
- Validator can call `validate_kb_rules` with actual patterns

---

### Task 8: Tests for KB integration

**Files:**
- Create: `tests/shared/signals/test_kb_patterns.py`

**What to do:**
- [ ] Test `load_kb_patterns()` returns list (mock Supabase)
- [ ] Test `save_proposed_patterns()` inserts correctly (mock Supabase)
- [ ] Test graceful failure when Supabase unavailable
- [ ] Test kb_pattern filtering by source_tag logic

**Acceptance:**
- All tests pass

---

## Batch C: Self-Learning (depends on B)

### Task 9: Update Advisor prompt for new_patterns output

**Files:**
- Modify: `agents/oleg/agents/advisor/prompts.py`

**What to do:**
- [ ] Add instruction for weekly/monthly reports to propose new patterns when anomalies aren't covered by existing signals
- [ ] Format section (already in prompt, verify it matches spec):
  ```
  ## ФОРМАТ НОВОГО ПАТТЕРНА (только weekly/monthly)
  {
      "pattern_name": "snake_case_name",
      "description": "Описание на русском",
      "evidence": "На чём основано наблюдение",
      "category": "margin|turnover|funnel|adv|price|model",
      "confidence": "high|medium|low"
  }
  ```

**Acceptance:**
- Advisor prompt instructs to output `new_patterns` field
- Only for weekly/monthly reports

---

### Task 10: Save proposed patterns in orchestrator

**Files:**
- Modify: `agents/oleg/orchestrator/orchestrator.py`

**What to do:**
- [ ] After parsing advisor output, extract `new_patterns`:
  ```python
  new_patterns = advisor_output.get("new_patterns", [])
  if new_patterns:
      from shared.signals.kb_patterns import save_proposed_patterns
      save_proposed_patterns(new_patterns)
  ```
- [ ] Include `new_patterns` in the result dict returned by `_run_advisor_chain()`
- [ ] Include in `_log_recommendation()` call

**Acceptance:**
- Advisor-proposed patterns saved to Supabase with `verified=false`
- Patterns included in recommendation_log entry

---

## Verification

After all tasks:
- [ ] Run full test suite: `python3 -m pytest tests/ -v`
- [ ] Verify no regressions in existing 57 tests
- [ ] Manual test: run a daily report, verify recommendation_log entry created in SQLite
- [ ] Verify chain works normally when KB/observability components unavailable (graceful degradation)
