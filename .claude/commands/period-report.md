Создай аналитический отчёт за произвольный период. $ARGUMENTS — две даты через пробел: начало и конец периода.

Пример: /period-report 2026-02-01 2026-02-07

Workflow V3 orchestrator (micro-agent pipeline):

1. Запусти скрипт:
   ```
   python3 scripts/run_report.py period $ARGUMENTS
   ```

2. Скрипт принимает две даты (start end), автоматически определяет тип отчёта (daily/weekly/monthly) по длине периода, затем вызывает соответствующую функцию из `agents.v3.orchestrator` (run_daily_report / run_weekly_report / run_monthly_report), которая:
   - Параллельно запускает micro-агентов: margin-analyst, revenue-decomposer, ad-efficiency
   - Передаёт артефакты в report-compiler для финальной сборки
   - Логирует run через services/observability

3. Результат:
   - telegram_summary — краткая сводка для Telegram
   - detailed_report — подробный отчёт для Notion
   - aggregate_confidence — уровень доверия к данным
   - Стоимость генерации, количество агентов, длительность

4. Покажи пользователю краткую сводку и метрики качества (confidence, limitations)
