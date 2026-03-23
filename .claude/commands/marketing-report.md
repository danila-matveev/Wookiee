Создай маркетинговый аналитический отчёт. $ARGUMENTS — период: одна дата (дневной), две даты через пробел (за период), или пусто (прошлая неделя).

Примеры:
- /marketing-report 2026-02-25 — дневной за указанную дату
- /marketing-report 2026-02-17 2026-02-23 — за период
- /marketing-report — за прошлую неделю

Workflow V3 orchestrator (micro-agent pipeline):

1. Запусти скрипт:
   ```
   python3 scripts/run_report.py marketing $ARGUMENTS
   ```

2. Скрипт определяет тип маркетингового отчёта (daily/weekly/monthly), затем вызывает `agents.v3.orchestrator.run_marketing_report()`, который:
   - Параллельно запускает micro-агентов: campaign-optimizer, organic-vs-paid, ad-efficiency
   - Передаёт артефакты в report-compiler для финальной сборки
   - Логирует run через services/observability

3. Результат:
   - telegram_summary — краткая сводка для Telegram
   - detailed_report — подробный отчёт для Notion
   - aggregate_confidence — уровень доверия к данным
   - Стоимость генерации, количество агентов, длительность

4. Покажи пользователю краткую сводку и метрики качества (confidence, limitations)
