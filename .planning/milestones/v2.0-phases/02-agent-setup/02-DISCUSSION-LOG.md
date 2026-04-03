# Phase 2: Настройка агента - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 02-agent-setup
**Areas discussed:** Структура модулей, Структура отчётов, Глубина анализа, Иерархия данных

---

## Структура модулей

| Option | Description | Selected |
|--------|-------------|----------|
| By function | core.md + templates/ + rules.md. Merge marketing/funnel playbooks into templates. | ✓ |
| By agent role | Each agent gets own complete playbook. Duplicated shared rules. | |
| Minimal split | Keep playbook.md mostly intact, extract templates only. | |

**User's choice:** By function (Recommended)
**Notes:** Clean separation: core (business context, formulas, glossary), templates (1 per report type), rules (strategies, antipatterns, diagnostics)

| Option | Description | Selected |
|--------|-------------|----------|
| Orchestrator assembles | Orchestrator picks core + template + rules, concatenates into prompt | ✓ |
| Agent self-loads | Each agent reads modules from disk at runtime | |

**User's choice:** Orchestrator assembles (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| agents/oleg/playbooks/ | New directory with clean structure | ✓ |
| agents/oleg/ (flat) | Flat files in agent root | |

**User's choice:** agents/oleg/playbooks/ (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Delete originals | Clean break after migration | |
| Keep as read-only archive | Rename to *_ARCHIVE.md | ✓ |

**User's choice:** Keep as read-only archive

---

## Структура отчётов

| Option | Description | Selected |
|--------|-------------|----------|
| One template per type | 8 files: daily.md, weekly.md, monthly.md, marketing_weekly.md, marketing_monthly.md, funnel_weekly.md, dds.md, localization.md | ✓ |
| Grouped by domain | 3 files: financial, marketing, other | |

**User's choice:** One template file per report type (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Strict headings | Agent MUST use exact toggle headings from template | ✓ |
| Flexible headings | Recommended but agent can adapt | |

**User's choice:** Strict headings (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| From Notion examples | Extract structure from best existing reports | |
| From requirements | Design from REQUIREMENTS.md criteria | |
| Other (user input) | Keep DDS/Localization as data-driven reports, use Notion examples as base | ✓ |

**User's choice:** DDS and Localization are newer reports that work as data-driven (no LLM analytics). User shared Notion examples for both. Templates should capture current working structure.
**Notes:** User provided Notion links to real DDS and Localization reports as reference. These reports intentionally lack deep LLM analysis.

---

## Глубина анализа

| Option | Description | Selected |
|--------|-------------|----------|
| Section presence control | Different sections per depth level | |
| Same sections, different detail | All reports same structure, depth varies | ✓ |
| You decide | Claude determines | |

**User's choice:** Same sections, different detail (user provided detailed explanation)
**Notes:** User explained: daily collects all main data, looks at dynamics of key metrics. Weekly goes deeper into parameter relationships. Monthly adds plan-fact, P&L, full strategy. Hypotheses and unit economics should be present at ALL levels (including daily) but with different depth.

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in templates | Depth markers per section within each template file | ✓ |
| Separate depth-rules.md | Generic depth rules in separate file | |

**User's choice:** Inline in templates (Recommended)

---

## Иерархия данных

| Option | Description | Selected |
|--------|-------------|----------|
| Separate data-map.md | Central file mapping tool → data → sections | ✓ |
| Embedded per template | Each template lists required tools | |
| Both | Central map + per-template required_tools | |

**User's choice:** Separate data-map.md (after explanation of what it means)
**Notes:** User initially didn't understand the concept. After explanation with examples (tool → section mapping for pre-flight and debugging), chose the central map approach.

| Option | Description | Selected |
|--------|-------------|----------|
| All agents | Cover reporter, marketer, funnel tool mappings | ✓ |
| Reporter only | Only financial report tools | |

**User's choice:** All agents (Recommended)

---

## Claude's Discretion

- Exact decomposition of 19 playbook sections between core/rules/templates
- Specific depth markers for each section of each template
- data-map.md format (table, YAML, etc.)
- orchestrator/prompts.py update for modular loading

## Deferred Ideas

- LLM analytics for DDS/Localization reports — future consideration
- Auto-update templates from feedback — Phase 5+ or backlog
