# agents/reporter/__main__.py
"""Reporter V4 entry point: scheduler + bot."""
import argparse
import asyncio
import logging
import signal

from agents.reporter.config import LOG_LEVEL, SUPABASE_SERVICE_KEY, SUPABASE_URL


def _configure_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _create_state():
    from supabase import create_client

    from agents.reporter.state import ReporterState

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return ReporterState(client=client)


async def run(dry_run: bool = False):
    _configure_logging()
    logger = logging.getLogger("agents.reporter")
    logger.info("Reporter V4 starting...")

    state = _create_state()

    from agents.reporter.gates import GateChecker

    gate_checker = GateChecker()

    from agents.reporter.scheduler import create_scheduler

    scheduler = create_scheduler(gate_checker, state)

    if dry_run:
        logger.info("DRY RUN — printing jobs:")
        for job in scheduler.get_jobs():
            logger.info("  %s: %s", job.id, job.trigger)
        return

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))

    stop_event = asyncio.Event()

    def _shutdown(*_):
        logger.info("Shutdown requested")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, _shutdown)

    # Start bot (runs in background)
    from agents.reporter.bot.bot import start_bot

    bot_task = asyncio.create_task(start_bot(state, gate_checker))

    try:
        await stop_event.wait()
    finally:
        bot_task.cancel()
        scheduler.shutdown(wait=False)
        logger.info("Reporter V4 stopped")


def main():
    parser = argparse.ArgumentParser(description="Reporter V4")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs and exit")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
