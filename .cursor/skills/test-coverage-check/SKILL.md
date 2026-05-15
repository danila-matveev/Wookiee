---
name: test-coverage-check
description: "Ночная проверка покрытия тестами. Запускает coverage run + pytest с теми же ignore/deselect-флагами, что и CI, сравнивает с baseline в .hygiene/coverage-baseline.json. Падение >2 п.п. → blocking finding в .hygiene/reports/coverage-YYYY-MM-DD.json, night-coordinator не мерджит PR. Рост → обновляет baseline. Cron 04:30 UTC."
triggers:
  - /test-coverage-check
  - coverage check
  - проверь покрытие
metadata:
  category: devops
  version: 0.1.0
  owner: danila
  wave: B4
---

# Test Coverage Check

Часть ночного DevOps-агента (план: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md`).

## Что делает

1. Запускает `coverage run -m pytest tests/` с теми же `--ignore` и `--deselect`, что и `.github/workflows/ci.yml`.
2. Генерирует JSON-отчёт через `coverage json` и читает `totals.percent_covered`.
3. Сравнивает с baseline в `.hygiene/coverage-baseline.json`.
4. **Если падение > `drop_threshold_pp` (по умолчанию 2.0 п.п.):** записывает blocking finding в `.hygiene/reports/coverage-YYYY-MM-DD.json` с `severity=high` и `blocking=true`. Night-coordinator при чтении такого отчёта **не мерджит** PR за эту ночь.
5. **Если рост:** обновляет baseline.
6. **Если без изменений:** пишет JSON-отчёт без findings.
7. Печатает короткое summary в stdout для GH Action log.

## Quick start

```bash
# Полный прогон (как в cron)
python -m scripts.nightly.test_coverage_check

# Или напрямую
python scripts/nightly/test_coverage_check.py

# Изменить порог падения / минимум
python scripts/nightly/test_coverage_check.py --drop-threshold-pp 3.0 --min-pct 65
```

## Файлы

- `scripts/nightly/test_coverage_check.py` — основная логика (runner)
- `.hygiene/coverage-baseline.json` — стартует пустым (`percent_covered: null`), пишется автоматически при первом успешном прогоне
- `.hygiene/reports/coverage-YYYY-MM-DD.json` — daily output, читается night-coordinator

## Pre-conditions

- `coverage` + `pytest` установлены (в CI — через requirements; локально — `pip install coverage pytest`)
- Запуск из корня репо
- `.hygiene/` существует (создаётся первым прогоном если нет)

## CI ignore-список

Skill копирует ignore/deselect-список из `.github/workflows/ci.yml`. Если CI меняется, обновить `CI_IGNORES` / `CI_DESELECTS` в `scripts/nightly/test_coverage_check.py`.

## Cron

`.github/workflows/test-coverage-check.yml` (Wave E, ещё не создан) — расписание 04:30 UTC, concurrency group `night-devops`.

## Контракт с night-coordinator

Coordinator читает `.hygiene/reports/coverage-YYYY-MM-DD.json`. Если `blocking=true` — **PR не мерджит**, на ветке стоит label `do-not-merge`.

Pydantic-модель: `shared.hygiene.schemas.CoverageReport`.
