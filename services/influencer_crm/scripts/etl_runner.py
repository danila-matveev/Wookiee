"""Cron entrypoint for CRM Sheets→DB sync. Logs every run to crm.etl_runs.

Usage:
    python -m services.influencer_crm.scripts.etl_runner [--full]

Default = --incremental. Pass --full to force full-import.
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import UTC, datetime

from services.influencer_crm.scripts._telemetry import insert_etl_run
from services.sheets_etl import run as etl_run

AGENT_NAME = "crm-sheets-etl"
AGENT_VERSION = "1.0.0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CRM Sheets ETL cron entrypoint")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full re-import (default: incremental)",
    )
    args = parser.parse_args(argv)

    started = datetime.now(UTC)
    t0 = time.monotonic()
    mode = "full" if args.full else "incremental"
    etl_argv = [] if args.full else ["--incremental"]

    status = "running"
    error: str | None = None
    exit_code = 0

    try:
        exit_code = etl_run.main(etl_argv)
        status = "success" if exit_code == 0 else "failed"
        if exit_code != 0:
            error = f"ETL exited non-zero: {exit_code}"
    except Exception as exc:  # noqa: BLE001 - top-level cron entrypoint
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        exit_code = 1

    duration_ms = int((time.monotonic() - t0) * 1000)
    finished = datetime.now(UTC)

    insert_etl_run(
        agent=AGENT_NAME,
        version=AGENT_VERSION,
        mode=mode,
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        status=status,
        error_message=error,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
