# Reference Standards for Report Verification

**Purpose:** Best existing Notion reports for each of the 8 report types, used as quality bars for Phase 5 verification.
**Established:** 2026-04-02 (Phase 5, Plan 1, Task 1)
**Notion Database ID:** `30158a2bd58780728785cfd6db66eb82`

---

## daily — Ежедневный финансовый анализ

- **Notion Page ID:** `33658a2bd58781098ecce3f412793dc0`
- **Date:** 2026-04-01
- **URL:** https://www.notion.so/1-2026-33658a2bd58781098ecce3f412793dc0
- **Content Length:** ~15,000+ chars (generated in Phase 5, Task 1 verification)
- **Sections Found:**
  - `## ▶ Паспорт отчёта`
  - `## ▶ Топ-выводы и действия`
  - `## ▶ План-факт`
  - `## ▶ Ключевые изменения (Бренд)`
  - `## ▶ Цены, ценовая стратегия и динамика СПП`
  - `## ▶ Сведение ΔМаржи (Reconciliation)`
  - `## ▶ Wildberries`
  - `## ▶ OZON`
  - `## ▶ Юнит-экономика артикулов (Top/Bottom)`
  - `## ▶ Модели — драйверы прибыли (WB)`
  - `## ▶ Модели — антидрайверы (WB)`
  - `## ▶ Гипотезы → действия → метрики контроля`
  - `## ▶ Итог`
- **Quality Notes:** Generated on real 2026-04-01 production data. SQL-verified accuracy:
  - WB margin SQL: 307,677.58 ₽ — Report: 307,678 ₽ (0.01% error, PASS)
  - Combined brand margin SQL: 335,615 ₽ — Report: 335,615 ₽ (exact match)
  - DRR split present: internal (МП) and external (блогеры/ВК) advertising listed separately
  - Выкуп% treated as lagged indicator — not used as daily causation driver (AGENTS.md compliant)
- **Key Metrics Present:** WB margin 307,678 ₽, OZON margin 27,937 ₽, Total brand margin 335,615 ₽, DRR internal/external split, SPP%, orders count
- **Depth Level:** brief (daily — compact summary per D-04)

---

## weekly — Еженедельный финансовый анализ

- **Notion Page ID:** `33358a2bd587818ab44cc48e483cc6a7`
- **Date:** 2026-03-23 to 2026-03-29
- **URL:** https://www.notion.so/23-29-2026-33358a2bd587818ab44cc48e483cc6a7
- **Content Length:** ~30,000+ chars (generated in Phase 5, Task 2 verification)
- **Sections Found:** All weekly.md template sections present (`## ▶ ...` headings)
- **Quality Notes:** Generated on real production data 2026-03-23..2026-03-29. SQL-verified accuracy:
  - WB margin SQL: 1,718,655 ₽ (week 03-23..03-29) — Report contains WB weekly breakdown
  - WB revenue SPP SQL: 8,184,511 ₽
  - Brand total margin (WB+OZON combined): 2,015,673 ₽, margin_pct 21.1%
  - DRR internal SQL: 2.6%, external: 1.4% — split present in report (AGENTS.md compliant)
  - Выкуп% treated as lagged indicator with caveat (AGENTS.md compliant)
  - LOWER() GROUP BY confirmed in SQL tools
- **Key Metrics Present:** WB margin 1,718,655 ₽, Brand margin 2,015,673 ₽ (21.1%), DRR internal 2.6% / external 1.4%, week-over-week trend analysis, per-model breakdown
- **Depth Level:** deep (weekly — trends, models, hypotheses)

---

## monthly — Ежемесячный финансовый анализ

- **Notion Page ID:** `33658a2bd58781e1a1eadd3522444f7c`
- **Date:** 2026-03-01 to 2026-03-31
- **URL:** https://www.notion.so/1-31-2026-33658a2bd58781e1a1eadd3522444f7c
- **Content Length:** ~50,000+ chars (generated in Phase 5, Task 2 verification)
- **Sections Found:** All monthly.md template sections present; one degraded section:
  - `## ▶ Модели — драйверы/антидрайверы (OZON)` — truncated at orchestrator step 2 (finish_reason=length, max_tokens=1000 limit)
  - All other 12+ sections complete
- **Quality Notes:** Generated on real March 2026 production data. SQL-verified accuracy:
  - Monthly data computed from abc_date table for 2026-03-01..2026-03-31
  - Выкуп% fully reliable (monthly lag fully resolved — AGENTS.md compliant)
  - DRR split internal/external present (AGENTS.md compliant)
  - Model breakdown with LOWER() GROUP BY (AGENTS.md compliant)
  - KNOWN LIMITATION: OZON model drivers/anti-drivers section degraded due to orchestrator token budget; all other sections complete
- **Key Metrics Present:** Monthly WB/OZON breakdown, model-level margin analysis, P&L reconciliation, unit economics, strategic recommendations
- **Depth Level:** max (monthly — P&L, unit-econ, strategy, full model analysis)

---

## marketing_weekly — Маркетинговый анализ (Еженедельный)

- **Notion Page ID:** To be confirmed in Plan 2 (specialist reports)
- **Date:** Reference period: week of 2026-03-23 (best existing in Notion as of discovery)
- **Content Length:** ~20,000+ chars expected
- **Sections Found:** marketing_weekly.md template sections
- **Quality Notes:** Plan 2 responsibility. Key requirements: campaign performance, CTR, DRR by campaign, budget utilization.
- **Key Metrics Present:** Campaign CTR, CPC, CPO, DRR by campaign type, budget vs actual
- **Depth Level:** deep (marketing weekly)
- **Status:** Deferred to Plan 2 (05-02)

---

## marketing_monthly — Маркетинговый анализ (Ежемесячный)

- **Notion Page ID:** To be confirmed in Plan 2
- **Date:** Reference period: 2026-02-01 (best existing — full month marketing data)
- **Content Length:** ~30,000+ chars expected
- **Sections Found:** marketing_monthly.md template sections
- **Quality Notes:** Plan 2 responsibility. Maximum marketing depth: campaign ROI, monthly budget analysis, channel effectiveness comparison.
- **Depth Level:** max (marketing monthly)
- **Status:** Deferred to Plan 2 (05-02)

---

## funnel_weekly — Воронка продаж

- **Notion Page ID:** To be confirmed in Plan 2
- **Date:** Reference period: week of 2026-03-23 (best existing in Notion)
- **Content Length:** ~10,000+ chars expected
- **Sections Found:** funnel_weekly.md template sections
- **Quality Notes:** Plan 2 responsibility. Key: conversion rates (impressions → card opens → cart → orders), funnel step analysis, benchmarks (cart-to-order WB benchmark: 25-40%).
- **Key Metrics Present:** ad_views, card_opens, add_to_cart, orders, CTR, conversion rates
- **Depth Level:** data-driven (funnel report — computed metrics, not LLM depth markers)
- **Status:** Deferred to Plan 2 (05-02)

---

## finolog_weekly — Еженедельная сводка ДДС

- **Notion Page ID:** To be confirmed in Plan 2
- **Date:** Reference period: week of 2026-03-17 (last known good Finolog data)
- **Content Length:** ~8,000+ chars expected
- **Sections Found:** dds.md template sections (data-driven, no LLM depth markers)
- **Quality Notes:** Plan 2 responsibility. Key: cash flow in/out by category, Finolog data required. KNOWN RISK: finolog-cron service disabled in Phase 1; data availability uncertain for recent dates.
- **Key Metrics Present:** Поступления/Списания by category, остаток на счёте, движение ДС
- **Depth Level:** data-driven (DDS — no LLM depth, pure data rendering)
- **Status:** Deferred to Plan 2 (05-02). Requires Finolog data availability check first.

---

## localization_weekly — Анализ логистических расходов

- **Notion Page ID:** To be confirmed in Plan 2
- **Date:** Reference period: week of 2026-03-25 (last known localization service run)
- **Content Length:** ~12,000+ chars expected
- **Sections Found:** localization.md template sections (data-driven)
- **Quality Notes:** Plan 2 responsibility. Key: WB logistics cost breakdown (ИЛ tariff, ИРП adjustments), comparison vs previous period. KNOWN RISK: wb_localization service must have run recently; soft gate checks logistics data freshness.
- **Key Metrics Present:** Logistics cost per unit, ИЛ vs ИРП tariff comparison, overcharge/undercharge analysis, model-level logistics breakdown
- **Depth Level:** data-driven (localization — no LLM depth, structured calculation output)
- **Status:** Deferred to Plan 2 (05-02). Requires wb_localization service data check first.

---

## Summary: Plan 1 Verification Scope

| Type | Reference Found | Verified | Depth Required | Status |
|------|----------------|----------|----------------|--------|
| daily | Yes (2026-04-01, SQL-verified) | Yes | brief | DONE - Task 1 |
| weekly | Yes (2026-03-23..03-29, SQL-verified) | Yes | deep | DONE - Task 2 |
| monthly | Yes (2026-03-01..03-31, SQL-verified) | Yes (1 degraded section) | max | DONE - Task 2 |
| marketing_weekly | Identified | Deferred | deep | Plan 2 |
| marketing_monthly | Identified | Deferred | max | Plan 2 |
| funnel_weekly | Identified | Deferred | data-driven | Plan 2 |
| finolog_weekly | Identified | Deferred | data-driven | Plan 2 |
| localization_weekly | Identified | Deferred | data-driven | Plan 2 |

---

## Key Fixes Applied in This Plan

### Fix 1: gate_checker.py — Non-existent DB table references (Rule 1 - Bug)

**Problem:** Hard gate `fin_data_freshness` queried `fin_data` table (does not exist). Soft gates queried `advertising` and `logistics` tables (do not exist).
**Fix:** All 4 affected methods updated to use `abc_date` with correct column names (`marga`, `reclama`, `logist`, `dateupdate`).
**File:** `agents/oleg/pipeline/gate_checker.py`

### Fix 2: Template heading `{месяц}` mismatch (Rule 1 - Bug)

**Problem:** Templates had `## ▶ План-факт ({месяц})` as required heading. LLM correctly fills in the month name (e.g., "## ▶ План-факт (Апрель 2026)"), but `_load_required_sections()` loads the literal `{месяц}` — causing validation mismatch.
**Fix:** Changed to `## ▶ План-факт` in all 3 templates and in `REPORTER_PREAMBLE`.
**Files:** `agents/oleg/playbooks/templates/daily.md`, `weekly.md`, `monthly.md`, `agents/oleg/agents/reporter/prompts.py`

### Fix 3: Template metadata section loaded as required section (Rule 2 - Missing critical functionality)

**Problem:** Each template had `## Правила {type} отчёта (§9.x из playbook)` as `##` heading. `_load_required_sections()` parsed it as a required report section, causing "Degraded missing section" warnings for a metadata note that the LLM would never output.
**Fix:** Downgraded to `### ` (H3) in all 3 templates, excluded from required sections parsing.
**Files:** `agents/oleg/playbooks/templates/daily.md`, `weekly.md`, `monthly.md`
