# /test-coverage-check

Ночной gate на покрытие тестами. Часть Wave B4 ночного DevOps-агента.

## Зачем

`/hygiene` чинит лишние импорты и битые ссылки, `/code-quality-scan` ловит линт. Но если кто-то незаметно удалит тесты или закомментит проверки — покрытие просядет, а никто не узнает. Этот skill в 04:30 UTC ровно за этим и следит:

- Делает прогон `coverage run -m pytest tests/` с теми же ignore-флагами, что и CI.
- Сравнивает с baseline (`.hygiene/coverage-baseline.json`).
- Падение > 2 п.п. → finding с `blocking=true`, ночной координатор не мерджит сегодняшний PR.

## Как запустить вручную

```bash
python scripts/nightly/test_coverage_check.py            # с дефолтными порогами
python scripts/nightly/test_coverage_check.py --dry-run  # (нет такого флага — это не /hygiene)
```

## Файлы

- `SKILL.md` — описание скилла (этот же текст в форме фронт-маттера)
- `runner.py` — тонкая обёртка над `scripts/nightly/test_coverage_check.py`
- `README.md` — этот файл

## Связанное

- Plan: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md` Phase 3
- CI ignore-список: `.github/workflows/ci.yml`
- Pydantic-модель отчёта: `shared/hygiene/schemas.py` (`CoverageReport`)
- Coverage baseline: `.hygiene/coverage-baseline.json`
