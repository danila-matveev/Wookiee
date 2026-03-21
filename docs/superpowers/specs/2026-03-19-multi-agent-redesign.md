# Wookiee v3: Multi-Agent Architecture Redesign

**Date**: 2026-03-19
**Status**: Draft
**Author**: Claude + Danila

## Problem

Current architecture has 3 macro-agents (Oleg with 6 sub-agents, Ibrahim, Finolog Categorizer), each is a full Python application with custom ReAct loop, circuit breakers, and orchestration logic. This creates:

1. **Monolithic agents** — Reporter agent has 31 tools, hard to reason about and debug
2. **Artificial boundaries** — marketing and finance are separate sub-agents but deeply interconnected
3. **Custom infrastructure** — self-written ReAct loop, circuit breaker, watchdog replicate what frameworks provide
4. **No interoperability** — tools are hardcoded Python functions, not reusable outside our system
5. **Difficult to extend** — adding a new domain (logistics, reviews) requires writing Python code, not just describing behavior

## Design Principles

1. **One task = one agent** — each micro-agent does one narrow thing, described in an MD file
2. **Human names = orchestrators only** — Oleg (analytics), Christina (knowledge + data navigation)
3. **MCP for all data access** — tools exposed via Model Context Protocol, reusable by any client
4. **MD-defined behavior** — agent behavior lives in Markdown files, not Python code
5. **Add by describing** — new agent = new MD file + connect to existing MCP tools
6. **LangGraph orchestration** — model-agnostic, production-proven, graph-based coordination
7. **Scripts are scripts** — ETL, sync, quality checks are cron jobs, not agents

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│              USER INTERFACE                        │
│         (Telegram / CLI / Claude Code)            │
└──────────┬───────────────────────┬───────────────┘
           │                       │
     ┌─────▼─────┐          ┌─────▼──────┐
     │   OLEG    │◄────────►│ CHRISTINA  │
     │ analytics │  context  │ knowledge  │
     │ reports   │  from KB  │ data nav   │
     │ decisions │          │            │
     └─────┬─────┘          └─────┬──────┘
           │                      │
    ┌──────┼──────┐        ┌──────┼──────┐
    │  N micro-   │        │  M micro-   │
    │  agents     │        │  agents     │
    │  (MD files) │        │  (MD files) │
    └──────┬──────┘        └──────┬──────┘
           │                      │
    ┌──────▼──────────────────────▼──────┐
    │           MCP SERVERS              │
    └──────┬──────────────────────┬──────┘
           │                      │
    ┌──────▼──────┐        ┌──────▼──────┐
    │  Databases  │        │ External    │
    │  (PG, Vec)  │        │ APIs        │
    └─────────────┘        └─────────────┘
           ▲
    ┌──────┴──────┐
    │ ETL scripts │
    │ (cron jobs) │
    └─────────────┘
```

## Layer 1: Orchestrators

### Oleg — Analytics Orchestrator

Single analytical brain. Routes tasks to micro-agents, synthesizes results, sees cross-domain connections (finance + marketing + pricing + funnel).

**Responsibilities:**
- Receive tasks (daily/weekly reports, ad-hoc questions, anomaly investigation)
- Decide which micro-agents to spawn (sequentially or in parallel)
- Read artifacts produced by micro-agents
- Detect when anomalies need deeper investigation (spawn additional agents)
- Call Christina for KB context when building hypotheses
- Synthesize final output via report-compiler
- Deliver via Telegram / Notion

**LangGraph implementation:** Oleg is a StateGraph with conditional edges. Nodes = micro-agent invocations. State = accumulated artifacts + task context.

**Playbook:** `agents/oleg/playbook.md` — business rules, thresholds, interpretation guidelines. Updated by quality-checker micro-agent based on feedback.

### Christina — Knowledge & Data Navigation Orchestrator

Knows everything about what data exists, where it lives, how fresh it is, and what it means. Manages the knowledge base.

**Responsibilities:**
- Answer "where can I find X?" — knows all MCP servers, tables, fields, update schedules
- Manage KB: add, update, delete, verify knowledge
- Audit KB coverage, find gaps
- When other agents need context, provide it from KB
- When users learn something new, store it

**LangGraph implementation:** Christina is a simpler StateGraph. Routing by intent: search / add / navigate / audit.

### Cross-Orchestrator Communication

Oleg's micro-agents and Oleg himself can access Christina's micro-agents at two levels:

**Direct tool access (simple queries):**
Any micro-agent (e.g., `anomaly-detector`, `price-strategist`) can call `kb-searcher` directly as a tool — no orchestrator involved. Fast, no extra LLM call. This covers 80% of KB interactions: "find what we know about SPP calculation changes."

**Orchestrator-to-orchestrator (complex queries):**
When the task requires Christina's reasoning — e.g., "check KB, then look at data catalog, figure out if we're missing data sources for this analysis" — Oleg calls Christina as a subgraph. Christina decides which of her micro-agents to involve.

```
Simple:  anomaly-detector ──→ kb-searcher (direct tool call)
Complex: Oleg ──→ Christina ──→ kb-searcher + data-navigator + kb-auditor
```

**Rule of thumb:** If you just need to search KB → direct call. If you need Christina to think about what to search or where else to look → call Christina.

## Layer 2: Micro-Agents (MD files)

Each micro-agent is defined by:
- **MD file** — system prompt describing role, rules, output format
- **MCP tools** — which tools from which MCP servers it can access
- **Output format** — structured JSON artifact written to shared state

### Micro-Agent MD File Structure

```markdown
# Agent: margin-analyst

## Role
Decompose margin into 5 levers: price_before_spp, spp%, DRR (internal/external),
logistics per unit, COGS per unit. Answer "why did margin change?"

## Rules
- Always call get_brand_finance first for baseline
- Always use get_margin_levers for decomposition
- Express impact of each lever in rubles (not just percentages)
- Compare with previous period
- GROUP BY model must use LOWER()

## MCP Tools
- wookiee-data: get_brand_finance, get_channel_finance, get_margin_levers, get_daily_trend

## Output Format
JSON artifact with: period, comparison_period, total_margin, margin_change,
levers: [{name, current, previous, delta_rub, delta_pct, impact_rank}],
top_driver, top_anti_driver, summary_text
```

### Initial Micro-Agents for Oleg

Principle: start with agents that map to current Reporter/Researcher/Marketer capabilities. Split further as needed.

**Finance block:**
- `margin-analyst` — 5-lever margin decomposition
- `revenue-decomposer` — revenue by channels/models, plan-fact, weekly dynamics
- `data-validator` — data quality checks

**Pricing block:**
- `price-strategist` — elasticity, scenarios, recommendations, ROI optimization
- `hypothesis-tester` — statistical hypothesis tests

**Marketing block:**
- `ad-efficiency` — ad ROI, ROMI, CPO, Growth/Harvest/Optimize/Cut matrix
- `campaign-optimizer` — daily dynamics, budget utilization, external ads
- `organic-vs-paid` — organic vs paid traffic shares and trends

**Funnel block:**
- `funnel-digitizer` — full funnel impressions→buyouts, per-step conversions
- `keyword-analyst` — search queries, positions, keyword ROI

**Investigation block:**
- `anomaly-detector` — find anomalies >10%, build hypotheses with data

**External data block:**
- `finolog-analyst` — Finolog transactions, categorization, P&L

**Service block:**
- `report-compiler` — assemble final report in 3 formats (telegram/brief/detailed)
- `quality-checker` — process feedback, verify claims through data, update playbook

**Future (add as MD file when needed):**
- `logistics-analyst` — FBO/FBS, returns, warehouses
- `review-analyst` — reviews, ratings, sentiment
- `content-optimizer` — card SEO, photos, content quality

### Micro-Agents for Christina

- `kb-searcher` — vector search across KB
- `kb-curator` — add/update/delete knowledge entries
- `kb-auditor` — coverage audit, gap detection, statistics
- `data-navigator` — map of ALL data sources, what's where, freshness, field descriptions
- `agent-monitor` — следит за здоровьем агентов: success rate по версиям, деградация после обновления промпта, алерты при падении качества, рекомендации по откату версии

## Layer 3: MCP Servers

All data access goes through MCP. This makes tools reusable by any client (Claude Code, Cursor, LangGraph, future tools).

### Internal Data

| MCP Server | Wraps | Key Tools |
|---|---|---|
| `wookiee-data` | `shared/data_layer.py` → PostgreSQL | `get_brand_finance`, `get_channel_finance`, `get_margin_levers`, `get_daily_trend`, `get_model_breakdown`, `get_weekly_breakdown`, `get_plan_vs_fact`, `get_orders_by_model`, `get_advertising_stats`, `get_model_advertising`, `get_product_statuses`, `validate_data_quality`, `calculate_metric` |
| `wookiee-price` | `services/price_analysis/*` | `get_price_elasticity`, `get_price_recommendation`, `simulate_price_change`, `get_price_trend`, `optimize_price_for_roi`, `get_stock_price_matrix`, `analyze_cross_model_effects`, `test_price_hypothesis`, `get_deep_elasticity_analysis` |
| `wookiee-marketing` | marketing queries | `get_marketing_overview`, `get_funnel_analysis`, `get_organic_vs_paid`, `get_campaign_performance`, `get_model_ad_efficiency`, `get_ad_daily_trend`, `get_ad_budget_utilization`, `get_external_ad_breakdown`, `get_ad_profitability_alerts` |
| `wookiee-kb` | `services/knowledge_base/` (Supabase pgvector) | `search_kb`, `add_knowledge`, `update_knowledge`, `delete_knowledge`, `verify_knowledge`, `list_files`, `get_stats` |

### External APIs

| MCP Server | Wraps | Key Tools |
|---|---|---|
| `wookiee-wb` | Wildberries API | `get_wb_orders`, `get_wb_feedbacks`, `get_wb_stocks`, `get_wb_nomenclature`, `get_wb_analytics`, `get_wb_adv` |
| `wookiee-ozon` | Ozon API | `get_ozon_orders`, `get_ozon_analytics`, `get_ozon_stocks`, `get_ozon_adv` |
| `wookiee-finolog` | Finolog API | `get_transactions`, `get_accounts`, `get_contractors`, `categorize_transaction` |
| `wookiee-moysklad` | MoySklad API | `get_inventory`, `get_stock_levels`, `get_product_list` |

### Services & External Tools

| MCP Server | Wraps | Key Tools |
|---|---|---|
| `wookiee-sheets` | Google Sheets | `read_range`, `write_range`, `get_plan_data`, `list_sheets` |
| `wookiee-notion` | Notion API | `create_page`, `update_page`, `query_database`, `get_page` |
| `wookiee-bitrix` | Bitrix24 | `get_chats`, `get_messages`, `send_message` |
| `wookiee-dds` | DDS (cash flow) | `get_cashflow`, `get_balances`, `get_accounts` |

### MCP Server Implementation Pattern

Each MCP server follows the same pattern:

```python
# mcp_servers/wookiee_data/server.py
from mcp.server import Server
from shared.data_layer import get_brand_finance, get_channel_finance, ...

server = Server("wookiee-data")

@server.tool()
async def get_brand_finance(date_from: str, date_to: str, channel: str = "both") -> str:
    """Get brand-wide financial summary: margin, revenue, orders, ad spend, DRR, SPP."""
    result = await data_layer.get_brand_finance(date_from, date_to, channel)
    return json.dumps(result, ensure_ascii=False)

# ... more tools

if __name__ == "__main__":
    server.run()
```

## Layer 4: Automated Scripts (formerly Ibrahim)

Not agents. Cron jobs that collect and prepare data. Live in `services/etl/`.

| Script | What It Does | Schedule |
|---|---|---|
| `etl-marketplace` | Sync WB/OZON API → PostgreSQL (UPSERT) | Daily 05:00 MSK |
| `etl-finolog` | Sync Finolog → PostgreSQL | Daily 05:00 MSK |
| `sheets-sync` | Google Sheets ↔ DB bidirectional sync | On schedule |
| `data-quality-check` | Freshness, completeness, consistency checks | Daily 06:00 MSK |
| `reconciliation` | Compare managed vs read-only DB (<1% variance) | Daily 06:30 MSK |

These scripts write to the same PostgreSQL that MCP servers read from. The data pipeline is:

```
External APIs → ETL scripts → PostgreSQL → MCP servers → Micro-agents
```

## Layer 5: Christina as Data Navigator

Christina maintains a living **data catalog** — a structured document (or KB entries) describing:

For each data source:
- **What**: description, what business questions it answers
- **Where**: MCP server name, tool names, table/field names
- **When**: update frequency, typical lag, freshness guarantee
- **Limits**: known issues, data quality notes, coverage gaps
- **How**: example queries, common use cases

Example interaction:
```
User: "Christina, where can I see margin by article?"
Christina: "wookiee-data → get_channel_finance(channel='wb', date_from, date_to).
  Field: margin_rub. Granularity: per article per day.
  Updated daily at 05:00 MSK, lag ~1 day.
  Also available in Google Sheets 'Plan-Fact 2026', sheet 'Articles'.
  Note: WB retention==deduction duplicates may inflate margin by 1-3%,
  use data-validator to check."
```

## Migration Strategy

### Phase 1: MCP Foundation
- Create MCP servers wrapping existing `shared/data_layer.py`, `price_analysis`, `marketing_tools`
- No agent changes yet — just expose existing tools via MCP
- Validate MCP servers work with Claude Code directly

### Phase 2: First Micro-Agents
- Create MD files for 3-4 core agents: `margin-analyst`, `revenue-decomposer`, `ad-efficiency`, `report-compiler`
- Set up LangGraph with Oleg as orchestrator calling these agents
- Run in parallel with current system, compare outputs

### Phase 3: Christina
- Migrate KB tools to MCP server
- Create Christina orchestrator + `kb-searcher`, `kb-curator`, `data-navigator`
- Build data catalog

### Phase 4: Full Migration
- Migrate remaining micro-agents
- Move ETL scripts from `agents/ibrahim/` to `services/etl/`
- Move Finolog from standalone app to `finolog-analyst` micro-agent + ETL script
- Decommission old Oleg v2

### Phase 5: New Domains
- Add `logistics-analyst`, `review-analyst`, `content-optimizer` as MD files
- Create corresponding MCP servers if new data sources needed

## Technology Stack

| Component | Technology | Why |
|---|---|---|
| Orchestration | LangGraph v1.0+ | Model-agnostic, production-proven, graph-based, checkpointing |
| LLM (primary) | Claude via OpenRouter | Best for analytical reasoning |
| LLM (cost optimization) | Gemini Flash / Haiku for simple agents | 10x cheaper for data extraction tasks |
| Tool protocol | MCP (Model Context Protocol) | Industry standard, interoperable |
| Agent definitions | Markdown files | Human-readable, version-controlled, easy to iterate |
| Data storage | PostgreSQL + Supabase (pgvector) | Current stack, no migration needed |
| ETL | Python cron scripts | Simple, reliable, already working |
| Observability | LangSmith | Native LangGraph integration, traces, debugging |
| Delivery | Telegram (aiogram) + Notion API | Current stack |
| Scheduling | APScheduler | Current stack |

## Key Decisions

1. **One orchestrator for all analytics** — Oleg handles finance + marketing + pricing + funnel because these domains are deeply interconnected
2. **Christina as service, not parallel orchestrator** — Christina doesn't make business decisions, she manages knowledge and navigates data
3. **LangGraph over Claude Agent SDK** — model-agnostic, more mature (v1.0 vs v0.1.x), easier to switch LLMs per agent
4. **MCP for everything** — even internal tools go through MCP for interoperability
5. **Micro-agents grow organically** — start with ~15, split further when an agent becomes too complex
6. **Scripts stay scripts** — ETL and data quality are deterministic tasks, no LLM needed

## Success Criteria

- [ ] Any team member can understand what an agent does by reading its MD file (<2 min)
- [ ] Adding a new micro-agent takes <30 min (write MD + connect MCP tools)
- [ ] MCP servers are usable from Claude Code / Cursor directly (not just through Oleg)
- [ ] Daily report quality matches or exceeds current system
- [ ] Cost per report does not increase >20%
- [ ] System recovers gracefully when any single micro-agent fails

## Shared State Between Micro-Agents

This is the critical architectural decision. Three options evaluated:

### Option A: LangGraph TypedDict State (Recommended)

Orchestrator maintains a TypedDict state that accumulates artifacts from each micro-agent. Each micro-agent receives relevant state slice as input, returns structured output that merges back.

```python
class OlegState(TypedDict):
    task: TaskRequest
    artifacts: dict[str, Any]  # agent_name -> structured output
    anomalies_detected: bool
    kb_context: Optional[str]
    final_report: Optional[ReportOutput]
```

**Pros:** Native LangGraph, in-memory (fast), typed, easy to debug.
**Cons:** Lost on crash (mitigated by LangGraph checkpointing).
**Use for:** All normal orchestration flows.

### Option B: File-Based Artifacts

Each micro-agent writes JSON to `data/artifacts/{run_id}/{agent_name}.json`. Orchestrator reads files.

**Pros:** Survives crashes, inspectable, works across processes.
**Cons:** Slower (disk I/O), no type safety, cleanup needed.
**Use for:** Long-running investigations, audit trails.

### Option C: Database-Backed Artifacts

Artifacts stored in PostgreSQL `agent_artifacts` table.

**Pros:** Persistent, queryable, shareable across services.
**Cons:** Over-engineering for most flows, adds DB dependency.
**Use for:** Future, if we need cross-session artifact history.

**Decision:** Start with Option A (LangGraph state) for orchestration. Add Option B for audit trails when needed.

## Resilience Model

Replaces current custom `react_loop.py`, `circuit_breaker.py`, `watchdog.py`.

### Per-Agent Timeouts

Each micro-agent has a configurable timeout. If exceeded, the orchestrator receives a partial result or error, and continues with remaining agents.

```python
# In LangGraph node definition
@with_timeout(seconds=60)
async def run_margin_analyst(state: OlegState) -> OlegState:
    ...
```

### Fallback on Failure

If a micro-agent fails, the orchestrator:
1. Logs the failure with context
2. Marks the artifact as `failed` in state
3. Continues with other agents (graceful degradation)
4. Report-compiler notes which sections are incomplete

### Circuit Breaker (LangGraph-native)

LangGraph retry policies + custom node wrapper:
- 3 consecutive failures for same agent → skip for 5 min
- Persistent failures → alert via Telegram watchdog
- MCP server unreachable → all agents using it get timeout, not hang

### Health Monitoring

Lightweight watchdog (cron, not agent):
- Checks: LLM API reachable, MCP servers responding, DB connected, last report delivered
- Escalation: Day 1 info → Day 2 warning → Day 3+ critical (Telegram alert)

## Agent Observability & Logging (Day One)

**Every** invocation — orchestrators AND micro-agents — is logged to Supabase from the very first run. This data powers future dashboards, agent management UI, and version tracking.

### Database Schema

Three tables: agent registry (versions), runs (executions), orchestrator summaries.

```sql
-- 1. Agent Registry — tracks all agents, their versions, and prompt history
CREATE TABLE agent_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,           -- 'oleg' | 'margin-analyst' | 'kb-searcher'
    agent_type TEXT NOT NULL,           -- 'orchestrator' | 'micro-agent'
    version TEXT NOT NULL,              -- '1.0' | '1.1' | '2.0'

    -- Definition
    md_file_path TEXT,                  -- 'agents/margin-analyst.md'
    system_prompt TEXT NOT NULL,        -- full MD content at this version
    prompt_hash TEXT NOT NULL,          -- SHA-256 of system_prompt (detect changes)
    mcp_tools TEXT[],                   -- tools available to this agent
    model_tier TEXT,                    -- 'HEAVY' | 'MAIN' | 'LIGHT'
    default_model TEXT,                 -- 'claude-sonnet-4-5'

    -- Metadata
    description TEXT,                   -- what this agent does (one line)
    changelog TEXT,                     -- what changed in this version
    created_by TEXT,                    -- 'danila' | 'auto-detect'
    is_active BOOLEAN DEFAULT true,     -- false = deprecated version

    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(agent_name, version)
);

CREATE INDEX idx_agent_registry_name ON agent_registry(agent_name, is_active);

-- 2. Agent Runs — every invocation of every agent (orchestrators + micro-agents)
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,               -- groups all agents in one orchestrator run
    parent_run_id UUID,                 -- if spawned by another agent/orchestrator

    -- Agent identity
    agent_name TEXT NOT NULL,           -- 'oleg' | 'margin-analyst' | etc.
    agent_type TEXT NOT NULL,           -- 'orchestrator' | 'micro-agent'
    agent_version TEXT NOT NULL,        -- '1.0' | '1.1' — links to agent_registry

    -- Execution
    status TEXT NOT NULL,               -- 'success' | 'failed' | 'timeout' | 'skipped'
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    error_message TEXT,

    -- LLM details
    model TEXT,                         -- actual model used for this run
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    llm_calls INTEGER,                  -- number of LLM roundtrips
    tool_calls INTEGER,                 -- number of MCP tool invocations

    -- Content
    system_prompt_hash TEXT,            -- links to agent_registry.prompt_hash
    user_input TEXT,                    -- task/instruction given
    output_summary TEXT,                -- first 2000 chars of output
    artifact JSONB,                     -- structured output (full)

    -- Context
    task_type TEXT,                     -- 'daily_report' | 'weekly_report' | 'ad_hoc'
    trigger TEXT,                       -- 'cron' | 'user_telegram' | 'user_cli' | 'orchestrator'

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_agent_runs_run_id ON agent_runs(run_id);
CREATE INDEX idx_agent_runs_agent ON agent_runs(agent_name, started_at DESC);
CREATE INDEX idx_agent_runs_version ON agent_runs(agent_name, agent_version);
CREATE INDEX idx_agent_runs_status ON agent_runs(status, started_at DESC);
CREATE INDEX idx_agent_runs_date ON agent_runs(started_at DESC);

-- 3. Orchestrator Run Summary — high-level view per pipeline execution
CREATE TABLE orchestrator_runs (
    run_id UUID PRIMARY KEY,
    orchestrator TEXT NOT NULL,
    orchestrator_version TEXT NOT NULL,
    task_type TEXT NOT NULL,
    trigger TEXT NOT NULL,

    status TEXT NOT NULL,               -- 'success' | 'partial' | 'failed'
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Aggregates
    agents_called INTEGER,
    agents_succeeded INTEGER,
    agents_failed INTEGER,
    total_tokens INTEGER,
    total_cost_usd NUMERIC(10,6),

    -- Output
    report_format TEXT,
    delivered_to TEXT[],                -- ['telegram', 'notion']

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Version Management

Versions are tracked automatically + manually:

**Auto-detect:** On startup, the system hashes each MD file. If the hash differs from the latest active version in `agent_registry`, a new version is created automatically with `changelog: "auto-detected prompt change"`.

**Manual:** When you intentionally improve an agent, bump the version and add a changelog:
```
v1.0 → Initial margin-analyst
v1.1 → Added SPP weighted average rule
v1.2 → Fixed GROUP BY LOWER() for model names
v2.0 → Restructured output format for new report-compiler
```

**What this enables:**
- "margin-analyst v1.1 had 95% success rate, v1.2 dropped to 80%" → rollback prompt
- A/B testing: run v1.2 and v1.3 in parallel, compare output quality
- Audit trail: which prompt produced which report on which date

### Logging Implementation

Logging is **async fire-and-forget** — never blocks agent execution.

```python
# Universal wrapper — works for both orchestrators and micro-agents
async def log_run(agent_name: str, agent_type: str, run_id: UUID, result, timing, llm_stats):
    """Async insert to Supabase — does not block execution."""
    version = get_active_version(agent_name)  # from in-memory cache
    asyncio.create_task(supabase.table("agent_runs").insert({
        "run_id": str(run_id),
        "agent_name": agent_name,
        "agent_type": agent_type,
        "agent_version": version,
        "status": "success" if not result.error else "failed",
        "duration_ms": timing.duration_ms,
        "model": llm_stats.model,
        "total_tokens": llm_stats.total_tokens,
        "cost_usd": llm_stats.cost_usd,
        "system_prompt_hash": get_prompt_hash(agent_name),
        "user_input": result.input[:2000],
        "output_summary": result.output[:2000],
        "artifact": result.artifact,
        "task_type": result.task_type,
        "trigger": result.trigger,
    }).execute())
```

### What This Enables (Future)

1. **Dashboard**: запуски по дням, успешность, стоимость — для каждого агента и оркестратора
2. **Agent management UI**: список всех агентов, их версии, промпты, статистика
3. **Version comparison**: v1.0 vs v1.1 — какая версия лучше по success rate, скорости, стоимости
4. **Cost tracking**: сколько стоит каждый отчёт, какой агент/оркестратор самый дорогой
5. **Quality trends**: успешность по версиям, деградация после обновления промпта
6. **Prompt rollback**: откат к предыдущей версии если новая хуже

## Delivery Layer (Pluggable Output)

The delivery layer is decoupled from the agent system. Oleg produces structured output (JSON artifacts + formatted text). Where it goes is configurable and can change without touching agent logic.

```
Oleg (LangGraph) → structured output → Delivery adapters → destinations
                                        ├── Telegram (aiogram)
                                        ├── Notion (pages + databases)
                                        ├── Wookiee Hub (web dashboard)
                                        ├── Eggent (open source agent UI)
                                        └── [future: Slack, email, API]
```

**Principle:** Agents don't know about delivery. The `report-compiler` micro-agent produces 3 formats (short summary, brief, detailed Markdown). Delivery adapters pick the right format for the destination.

**Current destinations:**
- **Telegram** — short summary (BBCode), triggered by cron or user request
- **Notion** — detailed report (Markdown), always written for archival
- **Wookiee Hub** — web interface, reads from DB/artifacts
- **Eggent** — experimental agent UI

**Scheduling:** APScheduler triggers LangGraph invocations on cron. The scheduler is a standalone script, not embedded in any UI layer.

## Migration Mapping (Old → New)

| Old Agent | New Micro-Agents | What Gets Dropped |
|---|---|---|
| **ReporterAgent** (31 tools) | `margin-analyst`, `revenue-decomposer`, `data-validator`, `report-compiler` | Custom tool dispatch, manual section parsing |
| **ResearcherAgent** (10 tools) | `anomaly-detector`, `hypothesis-tester` | Duplicate tool wrappers (brand_finance etc — now via MCP) |
| **QualityAgent** (5 tools) | `quality-checker` | Direct playbook file manipulation (now via tool) |
| **MarketerAgent** (15 tools) | `ad-efficiency`, `campaign-optimizer`, `organic-vs-paid` | Overlapping financial tool wrappers |
| **FunnelAgent/Makar** (8 tools) | `funnel-digitizer`, `keyword-analyst` | SEO naming confusion resolved |
| **ChristinaAgent** (7 tools) | `kb-searcher`, `kb-curator`, `kb-auditor`, `data-navigator` | In-process KB calls (now via MCP) |
| **OlegOrchestrator** | Oleg (LangGraph StateGraph) | Custom chain.py, prompts.py, LLM-based decide_next_step |
| **ReactLoop** | LangGraph agent executor | Custom react_loop.py (400 lines) |
| **CircuitBreaker** | LangGraph retry + timeout wrapper | Custom circuit_breaker.py |
| **GateChecker** | Pre-invocation node in LangGraph | Custom gate_checker.py |
| **Watchdog** | Cron health check script | Custom watchdog service |
| **Ibrahim** | `services/etl/` scripts | Agent framing removed |
| **FinologCategorizer** | `finolog-analyst` micro-agent + ETL script | Standalone app removed |

## LLM Model Strategy

Current production uses OpenRouter with configurable models per tier. This continues.

| Tier | Current Model | New System | Use Case |
|---|---|---|---|
| HEAVY | Configurable via .env | Claude Sonnet / Opus | Orchestrator decisions, synthesis, complex analysis |
| MAIN | Configurable via .env | Claude Sonnet / Gemini Flash | Most micro-agents |
| LIGHT | Configurable via .env | Gemini Flash / Haiku | Data extraction, simple formatting |

**Key:** Models are configured per micro-agent in the orchestrator config, not hardcoded. The spec does not mandate specific models — the system is model-agnostic via LangGraph + OpenRouter.

## Migration Phase Acceptance Criteria

### Phase 1: MCP Foundation
- [ ] `wookiee-data` MCP server responds to all 13 tools
- [ ] `wookiee-price` MCP server responds to all 9 tools
- [ ] MCP servers work from Claude Code CLI (`mcp__wookiee_data__get_brand_finance`)
- [ ] Latency: MCP tool call < 2x direct Python call

### Phase 2: First Micro-Agents
- [ ] `margin-analyst` produces same output as current Reporter margin section
- [ ] LangGraph Oleg orchestrates 4 agents for daily report
- [ ] Parallel run: old vs new system, output diff < 5%
- [ ] report-compiler produces valid Telegram + Notion format

### Phase 3: Christina
- [ ] KB search via MCP returns same results as current direct calls
- [ ] data-navigator answers "where is X?" for all known data sources
- [ ] Oleg can call Christina for KB context mid-report

### Phase 4: Full Migration
- [ ] All current report types (daily, weekly, marketing, funnel) work
- [ ] Feedback flow works end-to-end
- [ ] Old system decommissioned, no dual-running
- [ ] ETL scripts moved to `services/etl/`, all cron jobs running

### Phase 5: New Domains
- [ ] At least one new micro-agent added in <30 min
- [ ] New agent produces useful output on first try

## Rollback Plan

During Phase 2-3, both old and new systems run in parallel. Rollback = stop LangGraph, old system continues.

**Rollback triggers:**
- Report quality degradation (human review: old is better for 3+ consecutive days)
- Cost increase >30% vs old system
- Reliability: new system fails >2x per week where old system didn't

**Phase 4 rollback:** Old system Docker image tagged and preserved. Can be redeployed in <15 min.

## Open Questions

1. **Cost optimization**: which agents can use cheaper models without quality loss? Decide empirically during Phase 2.
2. **Monitoring**: LangSmith paid tier vs self-hosted alternative (Langfuse)? Evaluate during Phase 1.
3. **MCP server boundaries**: current split (data/price/marketing) may need adjustment based on usage patterns. Revisit after Phase 2.
