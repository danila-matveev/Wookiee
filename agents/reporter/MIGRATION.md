# V4 Reporter — Migration Checklist

## Phase 1: BUILD
- [ ] Supabase tables created (run migrations/001_create_tables.sql)
- [ ] .env updated: REPORTER_V4_BOT_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY
- [ ] Base playbook rules loaded into analytics_rules table
- [ ] Dependencies installed: jinja2, supabase, aiogram>=3.0, pydantic>=2.0, openai

## Phase 2: TEST (shadow mode)
- [ ] V4 generates financial_daily to shadow Notion DB
- [ ] V4 generates financial_weekly correctly
- [ ] V4 generates marketing_weekly correctly
- [ ] V4 generates funnel_weekly correctly
- [ ] Anti-spam: max 1 error notification per type per day
- [ ] Circuit breaker tested (3 failures → stops)
- [ ] Telegram edit works on retry (no duplicate messages)
- [ ] Bot commands work: /status, /run, /health

## Phase 3: SWITCH
- [ ] V4 Notion database = production NOTION_DATABASE_ID
- [ ] V4 Telegram chat = production ADMIN_CHAT_ID
- [ ] V3 scheduler disabled (V3_REPORTS_ENABLED=false or stop container)
- [ ] Monitor 24 hours — no errors, all reports generated

## Phase 4: CLEANUP
- [ ] Delete agents/v3/ (except gates.py already copied)
- [ ] Delete dead V2 code:
  - agents/oleg/orchestrator/ (830 lines)
  - agents/oleg/agents/reporter/
  - agents/oleg/agents/advisor/
  - agents/oleg/agents/validator/
  - agents/oleg/agents/marketer/
  - agents/oleg/executor/
  - agents/oleg/watchdog/
- [ ] Delete 12 unused .md agents from agents/v3/agents/
- [ ] Remove SQLite state from deploy volumes
- [ ] Update docs/architecture.md
- [ ] Update docs/development-history.md

## Rollback to V2
If V4 fails:
1. Stop wookiee_reporter container
2. Re-enable V2 orchestrator in wookiee_oleg
3. V2 playbook.md and tools still in agents/oleg/
