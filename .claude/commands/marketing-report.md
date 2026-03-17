Создай маркетинговый аналитический отчёт. $ARGUMENTS — период: одна дата (дневной), две даты через пробел (за период), или пусто (прошлая неделя).

Примеры:
- /marketing-report 2026-02-25 — дневной за указанную дату
- /marketing-report 2026-02-17 2026-02-23 — за период
- /marketing-report — за прошлую неделю

Workflow Олега (AI маркетинговый аналитик Wookiee):

1. Запусти скрипт:
   ```
   python3 scripts/run_report.py marketing $ARGUMENTS
   ```

2. Скрипт инициализирует OlegApp → pipeline → orchestrator → marketer agent.
   Marketer использует playbook `agents/oleg/marketing_playbook.md` и все маркетинговые tools (get_marketing_overview, get_funnel_analysis, get_external_ad_breakdown, get_model_ad_efficiency, get_organic_vs_paid, get_ad_daily_trend, get_campaign_performance, get_ad_budget_utilization, get_ad_spend_correlation и др.)

3. Результат:
   - Краткая сводка (brief_summary) — для Telegram
   - Подробный отчёт (detailed_report) — для Notion
   - Стоимость генерации, количество шагов, длительность

4. Покажи пользователю краткую сводку и ссылку на Notion (если была синхронизация)
