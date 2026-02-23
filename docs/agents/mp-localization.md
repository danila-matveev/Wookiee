# WB Localization Service

## Назначение

Сервис рассчитывает индекс локализации Wildberries и генерирует рекомендации по перемещениям/допоставкам, затем экспортирует отчёт в Google Sheets.

## Статус

- Active utility service
- Больше не агентный runtime

## Код

- Расчёт: `services/wb_localization/generate_localization_report_v3.py`
- Entry point: `services/wb_localization/run_localization.py`
- Маппинги: `services/wb_localization/wb_localization_mappings.py`
- История: `services/wb_localization/history.py`
- Экспорт: `services/wb_localization/sheets_export.py`
- API trigger: `services/vasily_api/app.py`

## Запуск

```bash
# Проверка загрузки данных/маппинга без финальной генерации
python -m services.wb_localization.run_localization --dry-run

# Расчёт по обоим кабинетам
python -m services.wb_localization.run_localization --cabinet both --days 30
```

## Примечания

- Старый агентный runtime Василия архивирован в `docs/archive/retired_agents/vasily_agent_runtime/`.
- Исторические документы Василия: `docs/archive/agents/vasily/`.
