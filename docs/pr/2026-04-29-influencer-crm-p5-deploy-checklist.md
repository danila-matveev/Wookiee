# P5 deploy checklist (после merge PR)

## 1. На localhost — финальный smoke
- [ ] `git checkout main && git pull`
- [ ] `pytest tests/services/influencer_crm/ tests/services/sheets_etl/ -q` → all green

## 2. Deploy на app server
- [ ] `ssh timeweb`
- [ ] `cd /home/danila/projects/wookiee && git pull`
- [ ] `cd deploy && docker compose up -d --build wookiee-cron`
- [ ] `docker compose logs --tail 20 wookiee-cron` → "Wookiee cron installed: ... + CRM ETL every 6h"

## 3. Первый ETL и smoke
- [ ] На сервере: `docker compose exec wookiee-cron python -m services.influencer_crm.scripts.etl_runner --full`
- [ ] Проверить `crm.etl_runs` в Supabase (через MCP):
  ```sql
  SELECT started_at, status, duration_ms, mode FROM crm.etl_runs ORDER BY started_at DESC LIMIT 5;
  ```

## 4. /ops/health smoke
- [ ] `curl -H "X-API-Key: $CRM_API_KEY" $BFF_URL/ops/health | jq`
- [ ] Ожидаем: etl_last_run.status='success', cron_jobs.length=4, mv_age_seconds<=300

## 5. QA2 canary 24h
- [ ] `/schedule` агента на 24h: проверять /ops/health каждые 6 часов, сравнивать с baseline
