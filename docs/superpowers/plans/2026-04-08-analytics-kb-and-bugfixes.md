# Analytics Knowledge Base + Bug Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create unified Analytics Knowledge Base (merging Oleg v2 playbooks) and fix 4 known bugs in the data collector — foundation for all analytics modules.

**Architecture:** Single `analytics-kb.md` reference file (merged from 5 Oleg playbooks + v1 rules) shared by all subagents. Bug fixes in collector Python code. All existing tests must continue to pass.

**Tech Stack:** Markdown (KB), Python 3.9+ (bug fixes)

**Spec:** `docs/superpowers/specs/2026-04-08-modular-analytics-v2-design.md` (section 1.3)

---

## File Map

| File | Responsibility | Action |
|---|---|---|
| `.claude/skills/analytics-report/references/analytics-kb.md` | Unified knowledge base for all agents | Create (merge from Oleg) |
| `scripts/analytics_report/utils.py:55` | `month_start` computation bug | Fix |
| `scripts/analytics_report/collectors/inventory.py` | LOWER() deduplication missing | Fix |
| `scripts/analytics_report/collectors/plan_fact.py:44-48` | MTD uses wrong month | Fix |
| `scripts/analytics_report/collect_all.py:1-8` | PYTHONPATH not set for `__main__` | Fix |
| `tests/analytics_report/test_utils.py` | Test for month_start fix | Add test |
| `.claude/skills/analytics-report/references/analytics-rules.md` | Old rules file | Delete (replaced by KB) |
| `.claude/skills/analytics-report/references/data-sources.md` | Keep as-is | No change |

---

## Task 1: Create Analytics Knowledge Base

**Files:**
- Create: `.claude/skills/analytics-report/references/analytics-kb.md`
- Delete: `.claude/skills/analytics-report/references/analytics-rules.md` (replaced)

- [ ] **Step 1: Read all Oleg playbooks**

Read these files to understand the full knowledge base:
- `agents/oleg/playbooks/core.md` (493 lines — business context, 5 margin levers, KPIs, formulas)
- `agents/oleg/playbooks/rules.md` (342 lines — ad analysis, causal patterns, benchmarks)
- `agents/oleg/marketing_playbook.md` (270 lines — DRR targets, funnel norms, attribution)
- `agents/oleg/funnel_playbook.md` (194 lines — funnel metrics dictionary, benchmarks, formulas)
- `agents/oleg/playbook.md` (1474 lines — master reference, price strategy, cost structure, unit economics)

Also read the current v1 rules:
- `.claude/skills/analytics-report/references/analytics-rules.md`

- [ ] **Step 2: Create unified analytics-kb.md**

Create `.claude/skills/analytics-report/references/analytics-kb.md` by merging the best content from all sources into a single structured document. The file should be organized into these sections:

**Section structure:**
1. **Бизнес-контекст и цели** — from core.md: company focus, 3 key metrics, targets, main rule
2. **5 рычагов маржи** — from core.md: price, SPP, DRR, logistics, COGS — with detailed explanations
3. **Жёсткие правила аналитики** — merged from rules.md + v1: GROUP BY LOWER(), weighted averages, DRR split, margin formulas (WB/OZON), organic+paid never sum, number format, date format
4. **Особенности WB** — from playbook.md: skleikas, content_analysis gap, fan-out JOIN, retention==deduction, SPP dynamics, commission structure
5. **Особенности OZON** — organic unavailable, 34 commission types, adv in marga
6. **Лаговые показатели** — buyout % (3-21d), bloggers (3-7d), price orders vs sales
7. **Ценовая стратегия** — from core.md: SPP reaction strategies (A: margin, B: growth), price change rules (max 1-2/week), attack strategy conditions
8. **ДРР и реклама** — from rules.md + marketing_playbook: DRR targets by channel (WB 5-8%, OZON 8-12%, bloggers 15-25%), double KPI (DRR sales + DRR orders), decision matrix, causal patterns (traffic↓+DRR↓, ad↓→orders↓)
9. **Маркетинговые бенчмарки** — from rules.md: CTR/CPC/CPM/CPL/CPO/CR benchmarks with interpretation rules
10. **Воронка продаж** — from funnel_playbook: metrics dictionary (CRO, CRP, etc.), funnel stages, what affects each stage, conversion benchmarks (WB and OZON separately), formulas
11. **Матрица эффективности рекламы** — Growth(>1000%)/Harvest(300-1000%)/Optimize(100-300%)/Cut(<100%)
12. **Внешняя реклама** — from rules.md: systematicity matrix (bloggers=random, VK=systematic), attribution windows, forbidden phrases
13. **Юнит-экономика** — annual ROI formula and categories, per-status targets (Продается ≥20-25%, Выводим = speed, Запуск ≥15%), COGS baseline ~350₽
14. **Остатки и оборачиваемость** — thresholds (DEFICIT<14d, OK 14-60, WARNING 60-90, OVERSTOCK 90-250, DEAD>250), price constraints by stock level
15. **Ценовая логика (decision tree)** — 5 rules from spec
16. **Диагностика аномалий** — from rules.md: hypothesis triggers (margin Δ>10%, DRR Δ>30%, CRO decline>5pp, traffic>20%), drill-down sequence (brand→MP→model→article), anomaly diagnostics table
17. **Data Quality** — from core.md + rules.md: margin tolerance <1% (OZON ~7%), retention==deduction, fan-out JOIN, traffic PowerBI gap, OZON organic unavailable
18. **Запрещённые формулировки** — complete list from rules.md
19. **Глоссарий** — key terms with Russian names (from funnel_playbook)

**Key principles for merging:**
- Keep ALL specific numbers (benchmarks, thresholds, DRR targets)
- Keep ALL formulas (margin, DRR, ROI, CRO, CRP)
- Keep ALL causal patterns (traffic↓+DRR↓, etc.)
- Remove duplicates — if both core.md and rules.md say the same thing, keep the more detailed version
- Use Russian section headers
- Format: clean markdown with tables

- [ ] **Step 3: Delete old analytics-rules.md**

```bash
rm .claude/skills/analytics-report/references/analytics-rules.md
```

- [ ] **Step 4: Verify KB is comprehensive**

Check that the new KB covers:
- [ ] All 5 margin levers from core.md
- [ ] All DRR targets from marketing_playbook.md
- [ ] All funnel benchmarks from funnel_playbook.md
- [ ] All causal patterns from rules.md
- [ ] All forbidden phrases from rules.md
- [ ] WB margin formula: `marga - nds - reclama_vn - reclama_vn_vk - reclama_vn_creators`
- [ ] OZON margin formula: `marga - nds`
- [ ] GROUP BY LOWER() rule
- [ ] Annual ROI formula and categories

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/analytics-report/references/analytics-kb.md
git rm .claude/skills/analytics-report/references/analytics-rules.md
git commit -m "feat(analytics): create unified Knowledge Base from Oleg v2 playbooks"
```

---

## Task 2: Fix month_start Bug in utils.py

**Files:**
- Modify: `scripts/analytics_report/utils.py:55`
- Modify: `tests/analytics_report/test_utils.py`

**Bug:** `month_start = start.replace(day=1)` uses the start date's month. For cross-month periods (e.g., start=March 30, end=April 5), this gives March 1 instead of April 1. MTD calculation then computes `days_elapsed = 36` instead of `5`.

- [ ] **Step 1: Add failing test**

Add to `tests/analytics_report/test_utils.py`:

```python
class TestMonthStartCrossMonth:
    def test_cross_month_uses_end_date(self):
        """month_start should be first day of END date's month, not start."""
        p = compute_date_params("2026-03-30", "2026-04-05")
        assert p["month_start"] == "2026-04-01"  # April, not March

    def test_same_month_unchanged(self):
        """When start and end in same month, month_start = first of that month."""
        p = compute_date_params("2026-04-01", "2026-04-07")
        assert p["month_start"] == "2026-04-01"
```

- [ ] **Step 2: Run test — should fail**

```bash
PYTHONPATH=. python3 -m pytest tests/analytics_report/test_utils.py::TestMonthStartCrossMonth -v
```
Expected: FAIL — `month_start` is `2026-03-01` not `2026-04-01`

- [ ] **Step 3: Fix utils.py line 55**

Change line 55 in `scripts/analytics_report/utils.py` from:
```python
        "month_start": start.replace(day=1).isoformat(),
```
to:
```python
        "month_start": end.replace(day=1).isoformat(),
```

- [ ] **Step 4: Run all tests**

```bash
PYTHONPATH=. python3 -m pytest tests/analytics_report/ -v
```
Expected: ALL pass (including new tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/analytics_report/utils.py tests/analytics_report/test_utils.py
git commit -m "fix(analytics): month_start uses end date for cross-month MTD calculation"
```

---

## Task 3: Fix Inventory LOWER() Deduplication

**Files:**
- Modify: `scripts/analytics_report/collectors/inventory.py`

**Bug:** Stock aggregation creates duplicate entries for models with different capitalization (e.g., "Wendy" from turnover + "wendy" from FBO stocks). The `model_from_article()` returns lowercase, but turnover functions return Title Case.

- [ ] **Step 1: Fix stock aggregation to normalize model names**

In `scripts/analytics_report/collectors/inventory.py`, the `collect_inventory` function aggregates WB/OZON stocks using `model_from_article()` which returns lowercase. But `get_wb_turnover_by_model()` and other functions return Title Case model names.

Add normalization after getting turnover data. Find the section where turnover data is processed and add `.lower()` normalization to model keys. Also merge the stock data (lowercase from FBO) with turnover data (Title Case from data_layer) by normalizing both to lowercase.

The fix should ensure that the output `by_model` list has exactly ONE entry per model (lowercase), with all data (stocks, turnover, moysklad) merged correctly.

- [ ] **Step 2: Verify fix**

```bash
PYTHONPATH=. python3 -c "
from scripts.analytics_report.collectors.inventory import collect_inventory
result = collect_inventory('2026-03-30', '2026-04-06')
inv = result['inventory']
models = [m.get('model', '') for m in inv.get('by_model', [])]
dupes = [m for m in set(models) if models.count(m) > 1]
print(f'Total models: {len(models)}, Duplicates: {dupes}')
assert len(dupes) == 0, f'Found duplicates: {dupes}'
print('OK - no duplicates')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collectors/inventory.py
git commit -m "fix(analytics): normalize model names to lowercase in inventory collector"
```

---

## Task 4: Fix collect_all.py PYTHONPATH

**Files:**
- Modify: `scripts/analytics_report/collect_all.py`

**Bug:** Running `python3 scripts/analytics_report/collect_all.py` fails with `ModuleNotFoundError: No module named 'scripts'` because PYTHONPATH doesn't include the project root.

- [ ] **Step 1: Add sys.path fix at top of collect_all.py**

Add after the imports comment, before the first import:

```python
import sys
from pathlib import Path

# Ensure project root is in sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
```

This adds the project root (2 levels up from `scripts/analytics_report/collect_all.py`) to sys.path.

- [ ] **Step 2: Test direct execution**

```bash
python3 scripts/analytics_report/collect_all.py --start 2026-04-05 --output /tmp/test-pythonpath.json 2>&1 | head -5
```
Expected: No `ModuleNotFoundError`. Either success or DB connection error (acceptable — means imports worked).

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collect_all.py
git commit -m "fix(analytics): add sys.path for direct script execution without PYTHONPATH"
```

---

## Task 5: Update All Prompt Files to Reference KB

**Files:**
- Modify: All prompt files in `.claude/skills/analytics-report/prompts/` that reference `analytics-rules.md`

- [ ] **Step 1: Find and replace references**

In all prompt files under `.claude/skills/analytics-report/prompts/`, replace any reference to:
```
.claude/skills/analytics-report/references/analytics-rules.md
```
with:
```
.claude/skills/analytics-report/references/analytics-kb.md
```

Also in SKILL.md, update the reference table.

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/analytics-report/
git commit -m "refactor(analytics): update all prompts to reference unified analytics-kb.md"
```

---

## Summary

| Task | What | Files | Commits |
|---|---|---|---|
| 1 | Create unified Knowledge Base | 1 create, 1 delete | 1 |
| 2 | Fix month_start bug | 2 modify | 1 |
| 3 | Fix inventory LOWER() | 1 modify | 1 |
| 4 | Fix PYTHONPATH | 1 modify | 1 |
| 5 | Update prompt references | ~12 modify | 1 |
| **Total** | | **~16 files** | **5 commits** |
