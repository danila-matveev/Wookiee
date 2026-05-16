# WB Toolkit Plan 2 — Localization Optimizer

> Continuation of [Plan 1](2026-05-06-wb-toolkit-plan1-foundation.md). This
> plan is preserved as a navigation target for the WB toolkit series; the active
> runtime already lives in `services/wb_localization/`.

## Scope

- Calculate WB localization metrics: ИЛ, ИРП and per-article localization.
- Build relocation scenarios with donor-safety constraints.
- Export operational sheets for review and execution.
- Keep historical runs for comparison and forecasting.

## Active Implementation

| Area | Path |
|---|---|
| CLI entrypoint | `services/wb_localization/run_localization.py` |
| Core report generator | `services/wb_localization/generate_localization_report_v3.py` |
| ИЛ/ИРП calculators | `services/wb_localization/calculators/` |
| Sheets export | `services/wb_localization/sheets_export/` |
| Service docs | `services/wb_localization/README.md` |

## Current Status

Implemented as the active `wb_localization` service. Future planning should
extend this file instead of linking to a missing Plan 2 placeholder.
