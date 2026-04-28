# scripts/daily_brief/

Implementation модуль для скилла `/daily-brief`.

Ежедневный отчёт Wookiee — финансы, воронка, маркетинг, модели, план-факт по марже. Собирает данные через DB + Sheets, пишет narrative и публикует в Notion DB «Аналитические отчёты».

## Содержимое
- `run.py` — entry point: `python -m scripts.daily_brief.run`
- `collector.py` — сбор данных из БД и Sheets
- `funnel.py` — расчёт воронки
- `marketing_sheets.py` — чтение план-факта маркетинга
- `forecast.py` — прогнозирование выкупов
- `patterns.py` — детектор аномалий

## User-facing docs
- Скилл: `.claude/skills/daily-brief/SKILL.md`
- Документация: `docs/skills/daily-brief.md`

## Owner
danila-matveev
