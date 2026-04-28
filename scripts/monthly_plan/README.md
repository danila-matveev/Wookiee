# scripts/monthly_plan/

Implementation модуль для скилла `/monthly-plan`.

Генерация месячного бизнес-плана Wookiee через multi-wave агентскую архитектуру.

## Содержимое
- `collect_all.py` — оркестратор сбора входных данных
- `collectors/` — модули по типам метрик (sales, ads, costs, capacity)
- `utils.py` — общие helper'ы

## User-facing docs
- Скилл: `.claude/skills/monthly-plan/SKILL.md`
- Документация: `docs/skills/monthly-plan.md`

## Owner
danila-matveev
