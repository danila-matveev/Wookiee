# Researcher Agent Specification

## Role
Hypothesis-driven investigator. Called by Orchestrator when anomalies are detected (margin drops, DRR spikes). Digs deeper into causality using API data and statistical analysis.

## Tools (10 total)

| Tool | Source | Purpose |
|------|--------|---------|
| `search_wb_analytics` | WB API | Product analytics from Wildberries |
| `get_wb_feedbacks` | WB API | Customer reviews and ratings |
| `get_moysklad_inventory` | MoySklad API | Current inventory levels |
| `get_moysklad_cost_history` | MoySklad API | Historical cost prices |
| `calculate_correlation` | scipy | Statistical correlation between metrics |
| `analyze_price_elasticity` | v1 price_analysis | Demand elasticity modeling |
| `compare_periods_deep` | data_layer | Deep period comparison with breakdown |
| `get_traffic_funnel` | data_layer | Conversion funnel analysis |
| `get_brand_finance` | v1 agent_tools | Brand-level P&L (shared with Reporter) |
| `get_margin_levers` | v1 agent_tools | Margin decomposition |

## Behavior
1. Receives anomaly context from Orchestrator
2. Forms initial hypotheses (up to 3)
3. Tests each hypothesis with data
4. Returns ranked hypotheses with evidence

## Hypothesis Framework
Five margin levers to investigate:
1. Logistics cost changes
2. Commission rate changes
3. Advertising efficiency
4. Buyout/return rate shifts
5. Cost price movements

## Escalation Triggers
- Margin delta > 10% → automatic investigation
- DRR delta > 30% → automatic investigation
- Orchestrator judges anomaly warrants deeper analysis
