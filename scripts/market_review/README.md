# scripts/market_review/

Implementation модуль для скилла `/market-review`.

Ежемесячный обзор рынка и конкурентов — сбор данных через MPStats, LLM-анализ, публикация в Notion. Покрывает динамику рынка, отслеживание конкурентов, сравнение топ-моделей.

## Содержимое
- `collect_all.py` — оркестратор сбора данных из MPStats
- `collectors/` — модули по типам данных (market dynamics, competitors, top models)
- `config.py` — параметры выборки

## User-facing docs
- Скилл: `.claude/skills/market-review/SKILL.md`
- Документация: `docs/skills/market-review.md`

## Owner
danila-matveev
