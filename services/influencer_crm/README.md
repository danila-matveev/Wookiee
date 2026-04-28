# Influencer CRM API (BFF)

FastAPI app on `service_role` Supabase pooler. Powers the React frontend in P4.

## Run locally

```bash
cp .env.example .env  # set INFLUENCER_CRM_API_KEY + SUPABASE_*
.venv/bin/pip install -r services/influencer_crm/requirements-dev.txt
bash services/influencer_crm/scripts/run_dev.sh
# → http://127.0.0.1:8082/docs
```

## Auth

Every endpoint except `/health` requires `X-API-Key: <INFLUENCER_CRM_API_KEY>`.

## Endpoint catalogue

See `docs/superpowers/plans/2026-04-27-influencer-crm-p3-api-bff.md` § Endpoint Catalogue.
