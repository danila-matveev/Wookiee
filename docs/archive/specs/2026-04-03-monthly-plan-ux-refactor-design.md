# Monthly Plan UX Refactor: From Analytics to Management Tool

**Date:** 2026-04-03
**Status:** Approved
**Trigger:** Analyst feedback on April 2026 business plan (Notion comments)

## Problem

The monthly business plan is analytically strong but overloaded with detail. It reads as a report, not as a management tool. Key issues:
- Too many hypotheses, not enough prioritization
- Raw statistical metrics (elasticity E, correlation r, confidence) are not actionable
- Hard to extract "what must be done" from the document
- Margin split (M-1/M-2) causes confusion — the DB already has margin inclusive of all ads

## Decision Summary

| Feedback item | Decision | Rationale |
|---|---|---|
| Hypotheses overloaded (D.1-D.16) | Merge into action table + toggle details | 16 expanded hypotheses are unreadable |
| Elasticity — remove coefficients | Keep computation internally, show only action + 1-line reason | Business reads "what to do with price", not r and E |
| Inventory — move up | Position #1 after summary | Frozen capital = first thing to see |
| Summary — cut to 5-7 actions | Remove explanations from summary | Summary is a checklist, not a mini-report |
| Price decisions via turnover + margin | Reframe: "Deficit -> raise, Overstock -> lower" | Business logic > statistics |
| Weekly plan — remove weeks | Prioritized action list without deadlines | Weekly KPI alarms are unrealistic |
| Scenarios (E) | Keep 1 recommended, second in toggle | Scenarios useful but 2 expanded tables = too much |
| P&L by models | Keep but simplify: remove M-2, show M-1 + Plan + delta | User confirmed this stays |
| Reference blocks (L, M) | Move to toggle "Reference" at bottom | Needed for verification, not for reading |
| Remove detailed P&L tables | REJECTED — P&L is the plan's core | |
| Remove elasticity entirely | REJECTED — agents compute it for recommendation quality | Hidden from output |
| Remove verification (K) | REJECTED — quality guarantee, collapsed in toggle | |
| M-1 / M-2 margin split | Single margin inclusive of all ads (internal + external) | Analyst confirmed DB margin already includes everything |
| Toggle headings | ALL sections use toggle headings at every level | User requirement: H1/H2/H3/H4 all toggleable |
| April report | Regenerate with new structure | User approved |

## New Document Structure

Every block is a toggle heading at the appropriate level.

```
toggle H1: 0. Rezume plana
  Targets: orders / revenue / margin / margin%
  5-7 actions (no explanations):
  * Action 1 — model
  * Action 2 — model
  ...
  Ad budget: X (internal) + Y (external) = Z

toggle H1: 1. Ostatki i oborachivaemost
  Table: Model | Qty | Turnover days | Problem | Action
  Problems: DEFICIT / OK / OVERSTOCK / DEAD STOCK
  Color coding: red/green/yellow

toggle H1: 2. P&L Brand
  Plan (1 recommended scenario) + M-1 fact
  Funnel: orders -> revenue -> SPP -> COGS -> logistics ->
          storage -> commission -> NDS -> ads -> margin -> margin%
  Single margin (includes all ads)
  toggle H2: Channel breakdown (WB / OZON separately)

toggle H1: 3. P&L po modelyam
  Table: Model | Revenue plan | Revenue M-1 | delta% | Ads | Margin | Margin% | Key decision
  Sorted by revenue desc
  toggle H2: Exiting models (Valery, Alice, etc.)

toggle H1: 4. Rekomendatsii po modelyam
  Table: Model | Price action | Ad action | Inventory action | Effect RUB
  Each action = 1 line, clear ("lower by 5%", "stop ads")
  toggle H2: Rationale (per model — why this action)
    Hidden: turnover, margin, sales trend —
    what used to be in hypotheses and elasticity

toggle H1: 5. Reklama
  Table: Model | Revenue | Ads internal | Ads external | DRR internal | DRR external | Margin% | Action
  Recommended budget (1 scenario)
  toggle H2: Aggressive scenario (alternative)

toggle H1: 6. Plan deistviy
  Prioritized list:
  1. [CRITICAL] Action — model — expected effect
  2. [IMPORTANT] ...
  3. [NICE TO HAVE] ...
  No deadlines, no weekly breakdown

toggle H1: Spravochno
  toggle H2: M-1 fact (full P&L, models, DRR)
  toggle H2: ABC analysis + financier reconciliation
  toggle H2: Verification (critics, corrector, CFO verdict)
  toggle H2: Context and data limitations
  toggle H2: Methodology
```

## Agent Changes

### P&L Analyst
- **Remove M-2** from output. Single margin = final (after all ads)
- Plan: only 1 recommended scenario (not A/B in main view)
- M-1 fact alongside for comparison. M-2 fact -> toggle "Reference"
- Break-even DRR calculation remains internal (for critics), not shown

### Pricing Analyst
- **Continues computing elasticity internally** (for recommendation quality)
- Output format changes: "Model -> Price action -> Reason (1 line)"
- Reason via turnover + margin: "Overstock 95d, margin 28% -> lower by 5%"
- **Remove from visible output:** E, r, confidence, data days
- Confidence used as internal guard (LOW -> HOLD only, unchanged)
- CUT guard unchanged: only HIGH confidence + overstock > 150d

### Ad Analyst
- DRR **keeps internal/external split** (analyst requirement)
- Single efficiency table + 1 recommended budget
- Aggressive scenario -> toggle
- Break-even DRR = margin% (single margin now, i.e. revenue breakeven point where ads = remaining margin after all costs)

### Inventory Analyst
- No calculation changes
- Output: simplified table with "Action" column
- **Promoted to position #1** after summary

### Traffic Analyst
- Results integrated into "Rationale" toggle of section 4
- **No separate section** in final document

### DQ Critic
- No changes (internal quality check)
- Adapt checks: no M-2 validation needed, single margin check

### Strategy Critic
- No changes (internal contradiction check)

### Corrector
- No changes

### CFO
- Summary: **5-7 actions** (not paragraphs)
- Price CUT guard remains, reframed via turnover language
- **Remove weekly plan** -> prioritized action list with severity tags
- Verdict mechanism unchanged (APPROVE/CORRECT/REJECT)

### Synthesizer
- **New template** (plan-structure.md rewrite)
- All H1 -> toggle H1, H2 -> toggle H2, H3 -> toggle H3, H4 -> toggle H4
- Notion format: toggle headings at every level
- "Reference" section collapsed by default
- Section numbering: 0-6 + Reference (was 0 + A-M)

## Notion Formatting

```
Toggle heading 1: main sections (0-6 + Reference)
Toggle heading 2: subsections (channel breakdown, rationale, scenarios)
Toggle heading 3: details within subsections
Toggle heading 4: granular detail (per-model rationale)

Tables: fit-page-width, header-row, header-column
Colors: red_bg (problems), green_bg (good), yellow_bg (attention)
Callout: after key sections (insight summaries)
Numbers: space separator (35 390), % with 1 decimal (22.8%)
Currency: always with RUB suffix or prefix
```

## Files to Modify

1. `.claude/skills/monthly-plan/templates/plan-structure.md` — new document template
2. `.claude/skills/monthly-plan/prompts/synthesizer.md` — new assembly rules
3. `.claude/skills/monthly-plan/prompts/cfo.md` — summary format, no weeks
4. `.claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md` — single margin, 1 scenario
5. `.claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md` — hide raw E/r, action-first output
6. `.claude/skills/monthly-plan/prompts/analysts/ad-analyst.md` — 1 scenario visible, toggle for second
7. `.claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md` — action column, simplified
8. `.claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md` — output as rationale content (no separate section)
9. `.claude/skills/monthly-plan/prompts/critics/dq-critic.md` — adapt for single margin
10. `.claude/skills/monthly-plan/SKILL.md` — update section references (0-6 instead of A-M)

## What Does NOT Change

- Data collector Python script (`scripts/monthly_plan/collect_all.py`)
- Triage agent
- Wave architecture (5 analysts -> 2 critics -> corrector -> CFO -> synthesizer)
- Notion publishing pipeline
- Google Sheets integration
- Internal computation logic (elasticity, ROAS, ABC)

## Scope of Regeneration

After skill updates:
1. Regenerate April 2026 plan with new structure
2. Overwrite existing Notion page
3. Verify toggle structure renders correctly in Notion

## Success Criteria

- [ ] Document has 7 main sections (0-6 + Reference), all toggle H1
- [ ] Summary contains exactly 5-7 action items, no explanations
- [ ] Inventory is section 1 (right after summary)
- [ ] Single margin throughout (no M-1/M-2 distinction)
- [ ] Recommendations table: Model | Price | Ads | Inventory | Effect
- [ ] Raw elasticity (E, r, confidence) not visible in main view
- [ ] All detail available in toggles (rationale, methodology, scenarios)
- [ ] Notion page uses toggle headings at H1/H2/H3 levels
- [ ] P&L by models present and readable
- [ ] Action plan is prioritized list without weekly breakdown
