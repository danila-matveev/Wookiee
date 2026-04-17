# WB Localization Service

## Назначение

Сервис рассчитывает индекс локализации Wildberries и генерирует рекомендации по перемещениям/допоставкам, затем экспортирует отчёт в Google Sheets.

## Статус

- Active utility service
- Больше не агентный runtime
- **2026-04-16:** редизайн с градацией сценариев, прогнозом перестановок и расширенным справочником

## Код

**Калькуляторы (чистые функции, `calculators/`):**
- `il_irp_analyzer.py` — расчёт ИЛ/ИРП per-article
- `economic_analyzer.py` — legacy 3-scenario экономика
- `scenario_engine.py` — градация 30–90% + топ-артикулы + экономика перестановок
- `relocation_forecaster.py` — 13-недельный понедельный прогноз с инерцией скользящего окна
- `reference_builder.py` — данные для расширенного справочника

**Экспорт (`sheets_export/` — пакет):**
- `__init__.py` — фасад с `export_to_sheets()`
- `formatters.py` — общие хелперы + `SHEET_COLUMN_DOCS` (описания колонок)
- `core_sheets.py` — Перемещения/Допоставки/Сводка/Регионы/Проблемные SKU
- `analysis_sheets.py` — ИЛ Анализ + legacy Экономика
- `reference_sheet.py` — расширенный Справочник (8 блоков)
- `scenario_sheet.py` — Экономика сценариев (градация 30–90%)
- `roadmap_sheet.py` — Перестановки Roadmap (14 недель)

**Инфраструктура:**
- Расчёт: `generate_localization_report_v3.py`
- Entry point: `run_localization.py`
- Маппинги: `wb_localization_mappings.py`
- История: `history.py` (таблицы `reports` + `weekly_snapshots`)
- Коэффициенты WB: `irp_coefficients.py` (источник истины — WB Partners, 27.03.2026)
- API trigger: `services/vasily_api/app.py`

## Листы в Google Sheets

Выход — 10 листов в целевом spreadsheet:

1. **Справочник** — полная документация WB (общий)
2. **Сводка {cabinet}** — ключевые метрики
3. **Экономика сценариев {cabinet}** — градация 30–90% + топ-15 артикулов
4. **Перестановки Roadmap {cabinet}** — 14 недель прогноза
5. **ИЛ Анализ {cabinet}** — per-article ИЛ/ИРП
6. **Регионы {cabinet}** — региональная разбивка
7. **Проблемные SKU {cabinet}**
8. **Допоставки {cabinet}**
9. **История** — append-only (общий)
10. **Обновление** — dashboard (общий)

## Запуск

```bash
# Полный запуск (всё включено)
python -m services.wb_localization.run_localization --cabinet both --days 30

# Проверка загрузки данных/маппинга без финальной генерации
python -m services.wb_localization.run_localization --dry-run

# Только справочник (быстрое обновление документации)
python -m services.wb_localization.run_localization --only-reference

# Без сценариев/прогноза (облегчённый запуск)
python -m services.wb_localization.run_localization --skip-scenarios --skip-forecast

# Кастомный % получаемых лимитов для forecast
python -m services.wb_localization.run_localization --realistic-limit-pct 0.5
```

## CLI-флаги (2026-04-16)

| Флаг | Описание | Дефолт |
|---|---|---|
| `--skip-scenarios` | Пропустить градацию сценариев (30–90%) | off |
| `--skip-forecast` | Пропустить 13-недельный roadmap | off |
| `--realistic-limit-pct` | Доля реально получаемых слотов в forecast | 0.3 |
| `--only-reference` | Обновить только лист «Справочник» | off |

## Математика forecast

13-недельный прогноз использует инерцию скользящего окна. Для каждого артикула на неделю `t`:

```
move_fraction = units_moved_to_date / total_stock
effective_new = loc_before × (1 - move_fraction) + loc_after × move_fraction
blended_loc(t) = ((13 - t) × loc_before + t × effective_new) / 13
```

Это отражает что старые недели 13-нед. окна продолжают тянуть индекс вниз, пока не выветрятся.

## Таблица weekly_snapshots

Новая таблица в SQLite-истории (`wb_logistics.db`):
- PK: `(cabinet, week_start, article, region)`
- Поля: `local_orders`, `nonlocal_orders`, `updated_at`
- UPSERT через `ON CONFLICT DO UPDATE`
- Заполняется при каждом запуске, используется в forecast'е

## Источники коэффициентов

- **КТР/КРП:** `COEFF_TABLE` в `irp_coefficients.py` — синхронизировано с WB Partners (авторизованный UI) на 27.03.2026
- **Расхождение с публичными seller docs:** только ниже 35% локализации — см. `docs/database/KTR_SYNC_VERIFICATION.md`
- **Лимиты складов:** `REDISTRIBUTION_LIMITS` — от 200 (Шушары: Питание) до 499 300 (Котовск) шт/день

## Примечания

- Старый агентный runtime Василия архивирован в `docs/archive/retired_agents/vasily_agent_runtime/`.
- Исторические документы Василия: `docs/archive/agents/vasily/`.
- Дизайн редизайна: `docs/superpowers/specs/2026-04-16-localization-service-redesign-design.md`
- План реализации: `docs/superpowers/plans/2026-04-16-localization-service-redesign-plan.md`
