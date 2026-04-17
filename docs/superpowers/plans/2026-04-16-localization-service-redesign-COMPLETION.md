# WB Localization Service Redesign — Completion Report

**Дата завершения:** 2026-04-16
**Статус:** ✅ Завершено
**Ветка:** `feature/localization-redesign`
**Коммитов:** 10

## Что сделано

- [x] Task 1: Верификация коэффициентов КТР → оставили текущие (источник истины WB Partners)
- [x] Task 2: Рефакторинг `sheets_export.py` (59KB) в пакет `sheets_export/` (4 модуля)
- [x] Task 3: Калькулятор `reference_builder.py` (8 секций справочника)
- [x] Task 4: Калькулятор `scenario_engine.py` (градация 30–90%)
- [x] Task 5: Таблица `weekly_snapshots` в `history.py` с UPSERT
- [x] Task 6: Калькулятор `relocation_forecaster.py` (13-недельный прогноз с инерцией)
- [x] Task 7: Sheet writer `reference_sheet.py` (расширенный Справочник)
- [x] Task 8: Sheet writer `scenario_sheet.py` + `SHEET_COLUMN_DOCS` словарь
- [x] Task 9: Sheet writer `roadmap_sheet.py` (14 недель с milestone'ами)
- [x] Task 10: Интеграция в `run_localization.py` + CLI-флаги

## Метрики

| Метрика | Значение |
|---|---|
| Новых калькуляторов | 3 (reference_builder, scenario_engine, relocation_forecaster) |
| Новых sheet writer'ов | 3 (reference_sheet, scenario_sheet, roadmap_sheet) |
| Разбит монолит | sheets_export.py (59KB → 4 модуля) |
| Новых тестов | 51 (56 baseline → 107 итого) |
| Тесты проходят | 107 / 107 ✅ |
| Коммитов | 10 |
| Листов в Google Sheets | 10 (было 8) |

## Коммиты

```
65909ee docs: add КТР sync verification report
d6d9065 refactor(wb_localization): split sheets_export.py into package
59500a9 feat(wb_localization): add reference_builder calculator
fbac02c feat(wb_localization): add scenario_engine calculator
ca0a6c6 feat(wb_localization): add weekly_snapshots table to history
9baf271 feat(wb_localization): add relocation_forecaster calculator
71b3d02 feat(wb_localization): add reference_sheet writer
69c3fb8 feat(wb_localization): add scenario_sheet writer + SHEET_COLUMN_DOCS
da0d732 feat(wb_localization): add roadmap_sheet writer
5d0a140 feat(wb_localization): integrate scenario + forecast + reference into pipeline
```

## Новые CLI-флаги

| Флаг | Что делает | Дефолт |
|---|---|---|
| `--skip-scenarios` | Пропустить градацию 30–90% | off |
| `--skip-forecast` | Пропустить 13-недельный прогноз | off |
| `--realistic-limit-pct` | % реально получаемых слотов складов | 0.3 |
| `--only-reference` | Обновить только Справочник | off |

## Архитектура

```
services/wb_localization/
├── calculators/
│   ├── il_irp_analyzer.py       ✅ existing
│   ├── economic_analyzer.py     ✅ existing (legacy 3 сценария)
│   ├── scenario_engine.py       🆕 градация 30–90%
│   ├── relocation_forecaster.py 🆕 13-нед. прогноз
│   └── reference_builder.py     🆕 структура справочника
│
├── sheets_export/               🆕 пакет (заменил монолит)
│   ├── __init__.py              фасад export_to_sheets
│   ├── formatters.py            + SHEET_COLUMN_DOCS
│   ├── core_sheets.py
│   ├── analysis_sheets.py
│   ├── reference_sheet.py       🆕
│   ├── scenario_sheet.py        🆕
│   └── roadmap_sheet.py         🆕
│
├── irp_coefficients.py          источник истины WB Partners 27.03.2026
├── run_localization.py          🔧 +4 CLI-флага, +3 шага пайплайна
└── history.py                   🔧 +weekly_snapshots таблица
```

## Ключевые решения и judgment calls

1. **КТР оставили как есть** — в коде они синхронизированы с WB Partners (источник истины), публичные seller docs отстают. См. `docs/database/KTR_SYNC_VERIFICATION.md`.

2. **Backward-compat:** старый `write_economics_sheet` (3 сценария) сохранён; facade использует его как fallback если `scenarios` отсутствует в payload.

3. **Все новые шаги опциональны** — обёрнуты в try/except. Если сценарии или forecast упадут, базовый отчёт всё равно публикуется.

4. **Инерция 13-недельного окна** моделируется формулой `blended(t) = ((13-t)×old + t×new)/13`. Без этого прогноз был бы слишком оптимистичным (эффект виден не сразу).

5. **Реалистичный % лимитов** параметр — дефолт 30% (по исследованию: слоты популярных складов перехватывают быстро).

6. **weekly_snapshots** заполняется при каждом запуске — через 13 недель полной истории прогноз будет максимально точным.

## Известные ограничения (backlog)

- **Chart в roadmap_sheet** — пока placeholder-текст, не создан через addChart API. Пользователь видит таблицу, но не визуальный график.
- **Cell notes (hover tooltips)** — не реализованы, используются только строки-описания под заголовками.
- **Per-article target_localization** — использует глобальный 85%. Более точный forecast потребует per-article target на основе реальных данных региональной локализации.
- **Emoji в заголовках** — большинство сохранены (🟢 🟡 🔴 🎯), но одно поле `warehouse_limit_status` заменено на "OK" (по внутреннему правилу проекта).
- **Оборот кабинета** для сценариев — считается из 91-дневного окна заказов. Если нужна точность — стоит использовать отдельный источник revenue data.

## Дальнейшие шаги

- Провести реальный E2E запуск на кабинете `ooo` и визуально проверить все листы в Google Sheets
- Если всё ок — создать PR и смержить `feature/localization-redesign` → `main`
- В следующей итерации: реализовать chart в roadmap_sheet через Google Sheets addChart API
- Собрать feedback от пользователя по дизайну листов, итерировать

## Документы

- Design spec: `docs/superpowers/specs/2026-04-16-localization-service-redesign-design.md`
- Plan: `docs/superpowers/plans/2026-04-16-localization-service-redesign-plan.md`
- КТР verification: `docs/database/KTR_SYNC_VERIFICATION.md`
- Service docs: `docs/agents/mp-localization.md`
