Создай еженедельный аналитический отчёт. $ARGUMENTS — дата любого дня недели (по умолчанию — прошлая неделя).

Workflow V3 orchestrator (micro-agent pipeline):

1. Запусти скрипт:
   ```
   python3 scripts/run_report.py weekly $ARGUMENTS
   ```

2. Скрипт определяет понедельник и воскресенье для указанной недели, затем вызывает `agents.v3.orchestrator.run_weekly_report()`, который:
   - Параллельно запускает micro-агентов: margin-analyst, revenue-decomposer, ad-efficiency
   - Передаёт артефакты в report-compiler для финальной сборки
   - Логирует run через services/observability

3. Результат:
   - telegram_summary — краткая сводка для Telegram
   - detailed_report — подробный отчёт для Notion
   - aggregate_confidence — уровень доверия к данным
   - Стоимость генерации, количество агентов, длительность

4. Покажи пользователю краткую сводку и метрики качества (confidence, limitations)
