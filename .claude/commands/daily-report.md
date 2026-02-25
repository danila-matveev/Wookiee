Создай дневной аналитический отчёт за $ARGUMENTS в сравнении с предыдущим днём.

Workflow Олега (AI финансовый аналитик Wookiee):

1. Запусти скрипт:
   ```
   python3 scripts/run_daily_report.py $ARGUMENTS
   ```

2. Скрипт инициализирует OlegApp → pipeline → orchestrator → reporter agent.
   Reporter использует playbook `agents/oleg/playbook.md` и все доступные tools (get_brand_finance, get_channel_finance, get_margin_levers, get_model_breakdown и др.)

3. Результат:
   - Краткая сводка (brief_summary) — для Telegram
   - Подробный отчёт (detailed_report) — для Notion
   - Стоимость генерации, количество шагов, длительность

4. Покажи пользователю краткую сводку и ссылку на Notion (если была синхронизация)
