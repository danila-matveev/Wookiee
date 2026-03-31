# Phase 4: Запуск и доставка - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 04-scheduling-delivery
**Areas discussed:** Cron-архитектура, Расписание отчётов, Telegram-уведомления, Русские названия типов

---

## Cron-архитектура

### Как запускать cron задачи

| Option | Description | Selected |
|--------|-------------|----------|
| System crontab in Docker | crontab inside wookiee-oleg container, each line calls python script | ✓ |
| Host crontab + docker exec | Cron on host, jobs do docker exec into running container | |
| You decide | Claude picks based on existing infrastructure | |

**User's choice:** System crontab in Docker (Recommended)
**Notes:** Like finolog-cron does now — proven pattern.

### Runner architecture

| Option | Description | Selected |
|--------|-------------|----------|
| One runner script | python -m scripts.run_report --type daily / --type weekly etc. | ✓ |
| Per-type scripts | scripts/run_daily.py, scripts/run_weekly.py, etc. | |
| You decide | Claude picks based on existing patterns | |

**User's choice:** One runner + --type (after Claude explained that V2 orchestrator already handles all types via report_type argument, and the runner is just orchestration wrapper)
**Notes:** User initially asked for consultation — wanted to understand if different data needs require different scripts. Claude explained data overlaps between financial/marketing and the difference is in playbook focus, not data pipeline.

### Delivery approach

| Option | Description | Selected |
|--------|-------------|----------|
| Inline delivery | Runner generates → publishes Notion → sends Telegram. One process. | ✓ |
| Separate delivery step | Runner only generates. Separate script delivers. | |
| You decide | Claude picks based on reliability requirements | |

**User's choice:** Inline delivery with verification step
**Notes:** User emphasized that after Notion publish, must verify the page content is actually correct before sending Telegram. This became D-04.

---

## Расписание отчётов

### Schedule approach

| Option | Description | Selected |
|--------|-------------|----------|
| Keep V3 schedule | Fixed times from APScheduler config | |
| Change | User specifies times | |
| You decide | Claude optimizes | |

**User's choice:** Data-readiness driven (not fixed times)
**Notes:** User explained data can appear at 11 or 12, not necessarily early. Wants retry until 18:00. Wants stub notifications every 2 hours so team doesn't worry. First stub at 09:00.

### Data readiness check

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-flight in runner | Runner starts at 07:00, checks data, exits if not ready. Cron retries every 30 min. | ✓ |
| Chain: check first then all reports | One cron job checks data, then launches all reports sequentially | |
| You decide | Claude picks based on Phase 3 requirements | |

**User's choice:** Pre-flight in runner (Recommended)

### Report sequence

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential | Financial → marketing → funnel → logistics → DDS | ✓ |
| Parallel where possible | Financial + marketing parallel, then DDS + localization parallel | |
| You decide | Claude picks based on server resources | |

**User's choice:** Sequential. DDS last, logistics before DDS.
**Notes:** User corrected: it's "логистика и локализация логистики", not just "локализация".

---

## Telegram-уведомления

### Message format

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: name + link | Report name + Notion link only | |
| With brief summary | Name + 3-5 key metrics + Notion link | ✓ |
| V3 full summary | Header + 1500 char summary + caveats + link + footer | |

**User's choice:** With brief summary

### Grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Each report separately | One Telegram message per report | ✓ |
| Grouped per day | One message with all reports of the day | |

**User's choice:** Each report separately (Recommended)

---

## Русские названия типов

| Option | Description | Selected |
|--------|-------------|----------|
| Proposed mapping | 8 Russian names as presented | ✓ |
| Custom names | User provides alternatives | |

**User's choice:** Proposed mapping accepted as-is

---

## Claude's Discretion

- Crontab file implementation details
- Stub notification format and wording
- Runner script internal structure
- How to extract key metrics for Telegram summary
- Retry logic for failed Notion publishes

## Deferred Ideas

- finolog-cron script fix — already deferred from Phase 1
- Alerts on metric changes — v3.0
- Telegram bot with commands — v3.0
- Watchdog monitoring — v3.0
