---
phase: 5
slug: verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — uses pytest auto-discovery |
| **Quick run command** | `python3 -m pytest tests/agents/oleg/playbooks/ tests/agents/oleg/runner/ -q --tb=short` |
| **Full suite command** | `python3 -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/agents/oleg/playbooks/ tests/agents/oleg/runner/ -q --tb=short`
- **After every plan wave:** Run `python3 -m pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | VER-02 | manual | Notion MCP search | N/A | ⬜ pending |
| 05-01-02 | 01 | 1 | RPT-01 | manual+smoke | `python3 scripts/run_report.py --type daily --date <date>` | N/A | ⬜ pending |
| 05-01-03 | 01 | 1 | RPT-02 | manual+smoke | `python3 scripts/run_report.py --type weekly --date <date>` | N/A | ⬜ pending |
| 05-01-04 | 01 | 1 | RPT-03 | manual+smoke | `python3 scripts/run_report.py --type monthly --date <date>` | N/A | ⬜ pending |
| 05-02-01 | 02 | 2 | RPT-04 | manual+smoke | `python3 scripts/run_report.py --type marketing_weekly --date <date>` | N/A | ⬜ pending |
| 05-02-02 | 02 | 2 | RPT-05 | manual+smoke | `python3 scripts/run_report.py --type marketing_monthly --date <date>` | N/A | ⬜ pending |
| 05-02-03 | 02 | 2 | RPT-06 | manual+smoke | `python3 scripts/run_report.py --type funnel_weekly --date <date>` | N/A | ⬜ pending |
| 05-02-04 | 02 | 2 | RPT-07 | manual+smoke | `python3 scripts/run_report.py --type finolog_weekly --date <date>` | N/A | ⬜ pending |
| 05-02-05 | 02 | 2 | RPT-08 | manual+smoke | `python3 scripts/run_report.py --type localization_weekly --date <date>` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- No new test framework installation needed
- 479 existing tests provide regression coverage for any code/template fixes
- LLM output quality is manually verified via Notion inspection + SQL metric comparison

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Report quality meets 4 criteria (completeness, depth, accuracy, format) | RPT-01..08 | LLM output is non-deterministic; quality cannot be asserted with unit tests | Inspect Notion output, check all sections filled, verify key metrics via SQL, check formatting |
| Reference reports identified from Notion | VER-02 | Requires human judgment on what constitutes "best" report | Search Notion by type, rank by content length and section completeness |
| ДРР split present in financial reports | RPT-01..03 | LLM may omit split despite template instructions | Scan report for "ДРР внутренняя" and "ДРР внешняя" presence |
| Выкуп% not used as daily causation driver | RPT-01 | LLM may use as causal factor despite prohibition | Check daily report does not attribute margin changes to выкуп% |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
