# Reporter Agent Specification

## Role
Primary financial analyst. Produces daily, weekly, and monthly P&L reports for Wookiee brand across WB and OZON marketplaces.

## Tools (30 total)

### Financial Tools (12, from v1 agent_tools.py)
- `get_brand_finance` — Brand-level P&L summary
- `get_channel_finance` — Per-channel (WB/OZON) P&L
- `get_model_breakdown` — Revenue/margin by product model
- `get_margin_levers` — Margin decomposition (logistics, commissions, ads, etc.)
- `get_advertising_stats` — Ad spend and efficiency
- `get_buyout_stats` — Buyout/return rates
- `get_daily_trend` — Daily revenue trend
- `get_weekly_breakdown` — Weekly aggregates
- `validate_data_quality` — Data quality self-check
- `compare_periods` — Period-over-period comparison
- `get_category_stats` — Category-level breakdown
- `get_top_bottom_models` — Best/worst performing models

### Price Tools (18, from v1 price_tools.py)
- `get_price_overview` — Current pricing overview
- `suggest_price_changes` — Price optimization suggestions
- `analyze_price_elasticity` — Demand elasticity analysis
- `get_competitor_prices` — Competitor pricing data
- ... and 14 more price analysis tools

## Behavior
1. Receives task from Orchestrator (e.g., "Generate daily report for 2026-02-22")
2. Runs ReAct loop: reasons about which tools to call
3. Calls tools via `execute_reporter_tool()` → delegates to `shared/data_layer.py`
4. Returns structured financial analysis

## System Prompt
Loaded from `prompts.py`, includes playbook.md business rules. Key instructions:
- Use LOWER() for model name grouping
- Use weighted averages for percentages
- Cross-validate with `validate_data_quality`
- Compare with prior period for context

## Data Sources
- PostgreSQL: `pbi_wb_wookiee`, `pbi_ozon_wookiee` (via `shared/data_layer.py`)
- All queries use the shared data layer — no direct SQL in agent code
