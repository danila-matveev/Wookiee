# Oleg v2 — System Architecture

## Overview

Oleg v2 is a multi-agent financial analytics system for Wookiee brand (WB + OZON marketplaces). It replaces the monolithic Oleg v1 with an orchestrator + 3 collaborative sub-agents architecture.

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  OlegApp                          │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Telegram  │  │ Scheduler│  │   Watchdog     │  │
│  │   Bot     │  │(APSched) │  │ (diagnostics)  │  │
│  └─────┬────┘  └─────┬────┘  └───────┬────────┘  │
│        │             │               │            │
│        v             v               v            │
│  ┌────────────────────────────────────────────┐   │
│  │            OlegOrchestrator                │   │
│  │  (LLM-driven chain: decide → run → synth)  │  │
│  └─────┬──────────┬────────────┬──────────────┘  │
│        │          │            │                  │
│        v          v            v                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Reporter │ │Researcher│ │ Quality  │         │
│  │ Agent    │ │ Agent    │ │ Agent    │         │
│  │ (30 tools)│ │(10 tools)│ │(5 tools) │         │
│  └──────────┘ └──────────┘ └──────────┘         │
│        │          │            │                  │
│        v          v            v                  │
│  ┌────────────────────────────────────────────┐  │
│  │     ReAct Loop (hardened executor)          │  │
│  │  try-catch/tool, timeout 30s, circuit break │  │
│  └────────────────────────────────────────────┘  │
│        │                                         │
│        v                                         │
│  ┌────────────────────────────────────────────┐  │
│  │   shared/data_layer.py (60+ SQL queries)   │  │
│  │   shared/clients/ (OpenRouter, WB, Ozon)   │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Key Differences from v1

| Aspect | v1 (Monolith) | v2 (Orchestrator) |
|--------|---------------|-------------------|
| Architecture | Single agent, 381 LOC executor | Orchestrator + 3 sub-agents |
| Error handling | No try-catch on tools → crash | Try-catch per tool, circuit breaker |
| Gates | 6 hard gates, all-or-nothing | 3 hard + 3 soft, graceful degradation |
| Escalation | None (silent failure) | Watchdog + diagnostics + Telegram alerts |
| Timeout | None | 30s/tool, 120s total |
| Self-healing | None | Quality Agent updates playbook from feedback |
| Deployment | 2 containers (agent + bot) | 1 container (unified process) |

## Chain Execution Flow

1. **Task arrives** (cron or user query)
2. **Orchestrator** decides which agent to call first
3. **Agent runs** via ReAct loop (tool calls + reasoning)
4. **Orchestrator** reviews result, decides: done or call another agent
5. **Synthesize** all agent outputs into final response
6. **Deliver** via Telegram + save to Notion

### Escalation Triggers
- Margin change > 10% → Researcher investigates
- DRR change > 30% → Researcher investigates
- Feedback received → Quality Agent processes

## Component Map

```
agents/oleg_v2/
├── __init__.py
├── __main__.py           # Entry point: python -m agents.oleg_v2
├── app.py                # OlegApp: wires everything together
├── config.py             # All configuration from .env
├── playbook.md           # Business rules (updated by Quality Agent)
│
├── executor/
│   ├── react_loop.py     # Hardened ReAct executor
│   └── circuit_breaker.py # 3 failures → 5 min cooldown
│
├── agents/
│   ├── base_agent.py     # Abstract base for all sub-agents
│   ├── reporter/         # Financial analysis (30 tools)
│   ├── researcher/       # Hypothesis investigation (10 tools)
│   └── quality/          # Feedback + playbook (5 tools)
│
├── orchestrator/
│   ├── orchestrator.py   # LLM-driven chain execution
│   ├── chain.py          # Data structures (ChainResult, etc.)
│   └── prompts.py        # Decision + synthesis prompts
│
├── pipeline/
│   ├── gate_checker.py   # 3 hard + 3 soft data quality gates
│   ├── report_pipeline.py # gate → orchestrator → deliver
│   └── report_types.py   # ReportType enum + dataclasses
│
├── watchdog/
│   ├── watchdog.py       # Health monitoring + dead man's switch
│   ├── diagnostic.py     # DiagnosticRunner (gates, DB, LLM, ETL)
│   └── alerter.py        # Escalating Telegram alerts
│
├── bot/
│   ├── telegram_bot.py   # aiogram bot setup
│   ├── formatter.py      # Message formatting
│   └── handlers/         # Auth, menu, reports, feedback
│
├── storage/
│   └── state_store.py    # SQLite (op_state, gates, reports, feedback)
│
└── services/
    ├── time_utils.py     # MSK timezone helpers
    └── notion_service.py # Notion integration
```

## Scheduler Timeline (MSK)

| Time | Job | Description |
|------|-----|-------------|
| 09:00 Mon-Sat | Daily Report | Yesterday's P&L analysis |
| 10:15 Mon | Weekly Report | Last week summary |
| */6h | Heartbeat | Watchdog health check |

## Watchdog Escalation

| Day | Severity | Action |
|-----|----------|--------|
| Day 1 | Info | "Running diagnostics..." |
| Day 2 | Warning | "2nd day without report" |
| Day 3+ | Critical | "CRITICAL: N days without reports" |

## Deployment

Single Docker container via `deploy/docker-compose.yml`:

```bash
docker compose -f deploy/docker-compose.yml up wookiee-oleg-v2 -d
```

## Configuration

All via `.env` file (see `config.py` for full list):

- `TELEGRAM_BOT_TOKEN` — Telegram bot
- `OPENROUTER_API_KEY` — LLM provider
- `DB_HOST`, `DB_PORT`, etc. — PostgreSQL
- `NOTION_TOKEN` — Notion integration
- `ADMIN_CHAT_ID` — Watchdog alerts target
- `DAILY_REPORT_TIME` — Cron time (default: 09:00)
- `WEEKLY_REPORT_TIME` — Cron time (default: 10:15)
