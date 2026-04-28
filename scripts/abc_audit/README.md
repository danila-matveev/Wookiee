# scripts/abc_audit/

Implementation модуль для скилла `/abc-audit`.

ABC-аудит товарной матрицы Wookiee (WB+OZON) — классификация ABC × ROI, color_code анализ, рекомендации по каждому артикулу.

## Содержимое
- `collect_data.py` — оркестратор сбора данных (DB → Supabase)
- `collectors/` — отдельные сборщики метрик (sales, ads, returns, stock)
- `utils.py` — общие helper'ы

## User-facing docs
- Скилл: `.claude/skills/abc-audit/SKILL.md`
- Документация: `docs/skills/abc-audit.md`

## Owner
danila-matveev
