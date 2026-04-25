# Oleg V2 — Architecture Notes (archived)

> Retired in refactor v3 phase 1, PR #5 (2026-04-25). This document captures the architectural decisions and patterns from Oleg V2 for historical reference. The actual code lived in `agents/oleg/` and is removed; analytical knowledge has been extracted into discrete skills (finolog-dds-report, daily-brief, finance-report, marketing-report, abc-audit).

## Roles (5)
- **Advisor** — pattern detection on KPI deltas, recommendations
- **Marketer** — campaign efficiency analysis (DRR breakdown, CRO funnel)
- **Reporter** — narrative generation for daily/weekly reports
- **Funnel** — per-model funnel analysis (transitions → cart → orders → buyouts)
- **Validator** — sanity-check direction signals (margin, ad spend, returns)

## ReAct loop
Each role used a ReAct (reason-act) loop with tool calls to:
- `shared/data_layer/*` for SQL aggregations
- `shared/signals/*` for pattern detection
- LLM (OpenRouter) for narrative synthesis

## Circuit breaker
Three-tier fallback chain to prevent runaway costs:
1. MAIN tier (`google/gemini-3-flash-preview`)
2. Retry once on parse failure
3. HEAVY tier (`anthropic/claude-sonnet-4-6`)
4. FREE tier as last resort

Confidence threshold > 0.8 on MAIN — do not escalate.

## Orchestrator decision flow
The `agents/oleg/orchestrator/` selected which role(s) to invoke based on the daily KPI delta:
- Margin drop > 5% → Advisor + Validator
- DRR spike > 20% → Marketer + Funnel
- Plan-fact divergence > 10% → Reporter + Advisor

## Why retired
Oleg V2 conflated five analytical concerns into one pipeline. The phase-2 architecture splits each concern into a standalone skill (finolog-dds-report, daily-brief, finance-report, marketing-report, abc-audit) that is independently triggerable, testable, and reportable. This eliminated the orchestrator's coordination overhead and made each report's logic visible at the skill level.

## Migration map
| Old role | New skill |
|---|---|
| Advisor | analytics-report (Pattern Brief) |
| Marketer | marketing-report |
| Reporter | daily-brief, finance-report |
| Funnel | funnel-report |
| Validator | (signals removed; data-layer validations are now inline in each skill) |
