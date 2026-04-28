# scripts/analytics_report/

Implementation модуль для скилла `/analytics-report`.

Pattern Brief — читает все существующие отчёты (finance, marketing, funnel), находит мульти-недельные тренды, cross-report паттерны и нерешённые проблемы, выдаёт Decision Brief.

## Содержимое
- `collect_all.py` — оркестратор сбора отчётов из Notion DB
- `collectors/` — модули чтения каждого типа отчёта
- `utils.py` — общие helper'ы

## User-facing docs
- Скилл: `.claude/skills/analytics-report/SKILL.md`
- Документация: `docs/skills/analytics-report.md`

## Owner
danila-matveev
