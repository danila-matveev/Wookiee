Создай аналитический отчёт за произвольный период. $ARGUMENTS — две даты через пробел: начало и конец периода.

Пример: /period-report 2026-02-01 2026-02-07

Workflow Олега (AI финансовый аналитик Wookiee):

1. Запусти скрипт:
   ```
   python3 scripts/run_report.py period $ARGUMENTS
   ```

2. Скрипт принимает две даты (start end), инициализирует OlegApp → pipeline → orchestrator → reporter agent.
   Reporter использует playbook `agents/oleg/playbook.md` и все доступные tools.

3. Результат:
   - Краткая сводка (brief_summary) — для Telegram
   - Подробный отчёт (detailed_report) — для Notion
   - Стоимость генерации, количество шагов, длительность

4. Покажи пользователю краткую сводку и ссылку на Notion (если была синхронизация)
