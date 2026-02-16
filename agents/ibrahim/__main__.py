"""
Allow running as: python -m agents.ibrahim <command>

Commands:
    sync              Sync yesterday's data
    sync --from DATE --to DATE   Sync a date range
    reconcile         Compare managed vs source DB
    status            Show DB table stats and recent tasks
    health            Full health check (DB + data quality)
    analyze-api       Analyze marketplace API docs (LLM)
    analyze-schema    Analyze and propose schema changes (LLM)
    run-scheduler     Start persistent scheduler (blocking)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from agents.ibrahim import config


def _setup_logging() -> None:
    Path(config.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m agents.ibrahim",
        description="Ибрагим — автономный дата-инженер",
    )
    sub = parser.add_subparsers(dest="command")

    # sync
    p_sync = sub.add_parser("sync", help="Run ETL sync")
    p_sync.add_argument("--from", dest="date_from", help="Start date YYYY-MM-DD")
    p_sync.add_argument("--to", dest="date_to", help="End date YYYY-MM-DD")

    # reconcile
    p_recon = sub.add_parser("reconcile", help="Compare managed vs source DB")
    p_recon.add_argument("--days", type=int, default=1, help="Days back to check")

    # status
    sub.add_parser("status", help="Show DB stats and recent tasks")

    # health
    sub.add_parser("health", help="Full health check")

    # analyze-api
    sub.add_parser("analyze-api", help="Analyze API docs (LLM)")

    # analyze-schema
    sub.add_parser("analyze-schema", help="Analyze schema (LLM)")

    # run-scheduler
    p_sched = sub.add_parser("run-scheduler", help="Start persistent scheduler")
    p_sched.add_argument("--run-now", action="store_true", help="Run daily routine immediately")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    _setup_logging()
    logger = logging.getLogger("ibrahim")
    logger.info("Ibrahim Agent v0.1 — command: %s", args.command)

    from agents.ibrahim.ibrahim_service import IbrahimService

    ibrahim = IbrahimService()

    if args.command == "sync":
        if args.date_from and args.date_to:
            result = ibrahim.sync_range(args.date_from, args.date_to)
        else:
            result = ibrahim.sync_yesterday()
        _print_json(result)

    elif args.command == "reconcile":
        result = ibrahim.reconcile(days=args.days)
        _print_json(result)

    elif args.command == "status":
        result = ibrahim.get_status()
        _print_json(result)

    elif args.command == "health":
        result = ibrahim.health()
        _print_json(result)

    elif args.command == "analyze-api":
        result = asyncio.run(ibrahim.analyze_api())
        _print_json(result)

    elif args.command == "analyze-schema":
        result = asyncio.run(ibrahim.analyze_schema())
        _print_json(result)

    elif args.command == "run-scheduler":
        from agents.ibrahim.scheduler import IbrahimScheduler
        sched = IbrahimScheduler()
        try:
            asyncio.run(sched.start(run_now=args.run_now))
        except KeyboardInterrupt:
            logger.info("Ibrahim Agent stopped")


if __name__ == "__main__":
    main()
