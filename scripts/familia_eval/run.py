#!/usr/bin/env python3
# scripts/familia_eval/run.py
"""Familia Evaluation Pipeline — orchestrator.

Usage:
    python scripts/familia_eval/run.py                  # Full pipeline
    python scripts/familia_eval/run.py --calc-only      # Data + calc, no LLM
    python scripts/familia_eval/run.py --llm-only       # Reuse cached scenarios.json
    python scripts/familia_eval/run.py --logistics 80   # Override logistics cost
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

# Ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.familia_eval.config import CONFIG
from scripts.familia_eval.collector import collect_all
from scripts.familia_eval.calculator import calculate_scenarios

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("familia_eval")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def parse_args():
    parser = argparse.ArgumentParser(description="Familia evaluation pipeline")
    parser.add_argument("--calc-only", action="store_true", help="Skip LLM agents")
    parser.add_argument("--llm-only", action="store_true", help="Reuse cached scenarios.json")
    parser.add_argument("--logistics", type=int, help="Override logistics cost per unit")
    parser.add_argument("--discount-min", type=float, help="Min discount (e.g. 0.45)")
    parser.add_argument("--discount-max", type=float, help="Max discount (e.g. 0.60)")
    return parser.parse_args()


async def run_llm_agents(scenarios: list) -> str:
    """Wave 3 (parallel) + Wave 4 (sequential)."""
    from scripts.familia_eval.agents.mp_comparator import run_mp_comparator, _build_summary
    from scripts.familia_eval.agents.familia_expert import run_familia_expert
    from scripts.familia_eval.agents.advisor import run_advisor

    # Wave 3: parallel LLM agents
    log.info("Wave 3: running MP Comparator + Familia Expert in parallel...")
    mp_task = asyncio.create_task(run_mp_comparator(scenarios))
    expert_task = asyncio.create_task(run_familia_expert(scenarios))

    mp_report, expert_report = await asyncio.gather(mp_task, expert_task)

    # Save intermediate reports
    mp_report = mp_report or "[MP Comparator returned empty response]"
    expert_report = expert_report or "[Familia Expert returned empty response]"
    _save_output("mp_comparator.md", mp_report)
    _save_output("familia_expert.md", expert_report)
    log.info("Wave 3 complete. Reports saved.")

    # Wave 4: Advisor synthesis
    log.info("Wave 4: running Advisor...")
    scenarios_summary = _build_summary(scenarios)
    advisor_report = await run_advisor(scenarios_summary, mp_report, expert_report)

    _save_output("familia_eval_report.md", advisor_report)
    log.info("Wave 4 complete. Final report saved.")

    return advisor_report


def main():
    args = parse_args()
    t0 = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Apply CLI overrides
    if args.logistics:
        CONFIG["logistics_to_rc"] = args.logistics
    if args.discount_min or args.discount_max:
        lo = args.discount_min or CONFIG["discount_range"][0]
        hi = args.discount_max or CONFIG["discount_range"][-1]
        CONFIG["discount_range"] = [round(lo + i * 0.05, 2) for i in range(int((hi - lo) / 0.05) + 1)]

    if args.llm_only:
        # Load cached scenarios
        cache_path = os.path.join(OUTPUT_DIR, "scenarios.json")
        if not os.path.exists(cache_path):
            log.error("No cached scenarios.json found. Run without --llm-only first.")
            sys.exit(1)
        with open(cache_path) as f:
            data = json.load(f)
        scenarios = data["articles"]
        log.info("Loaded %d articles from cache.", len(scenarios))
    else:
        # Wave 1: Collect
        log.info("Wave 1: collecting data...")
        raw = collect_all()
        articles = raw["articles"]
        log.info("Collected %d articles (errors: %s)", len(articles), raw["meta"].get("errors", {}))

        if not articles:
            log.warning("No articles found matching filters. Check status_filter and min_stock.")
            sys.exit(0)

        # Wave 2: Calculate
        log.info("Wave 2: calculating scenarios...")
        scenarios = calculate_scenarios(articles)
        log.info("Calculated scenarios for %d articles.", len(scenarios))

        # Save scenarios.json
        output = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "params": {k: v for k, v in CONFIG.items() if k != "discount_range"},
            "discount_range": CONFIG["discount_range"],
            "articles": scenarios,
        }
        _save_output("scenarios.json", json.dumps(output, ensure_ascii=False, indent=2, default=str))

        # Print summary
        for art in scenarios:
            best = max(art["scenarios"], key=lambda s: s["margin"])
            worst = min(art["scenarios"], key=lambda s: s["margin"])
            log.info(
                "  %s: stock=%d, breakeven=%.0f%%, best=%.0f%% (margin %.1f), worst=%.0f%% (margin %.1f)",
                art["article"], art["stock_moysklad"],
                art["breakeven_discount"] * 100,
                best["discount"] * 100, best["margin"],
                worst["discount"] * 100, worst["margin"],
            )

    if args.calc_only:
        log.info("--calc-only: skipping LLM agents. See output/scenarios.json")
        return

    # Wave 3-4: LLM agents
    report = asyncio.run(run_llm_agents(scenarios))

    elapsed = round(time.time() - t0, 1)
    log.info("Pipeline complete in %.1f sec. Report: output/familia_eval_report.md", elapsed)
    print(f"\n{'='*60}")
    print(report[:500] + "..." if len(report) > 500 else report)
    print(f"{'='*60}")
    print("\nFull report: scripts/familia_eval/output/familia_eval_report.md")


def _save_output(filename: str, content: str):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
