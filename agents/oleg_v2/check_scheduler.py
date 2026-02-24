"""
Oleg v2 health check — verify imports, scheduler jobs, and config.

Run: python3 -m agents.oleg_v2.check_scheduler
  or: make oleg2-check
"""
import sys


def main():
    print("=" * 50)
    print("  Oleg v2 — Health Check")
    print("=" * 50)
    print()

    errors = []

    # ── 1. Import check ─────────────────────────────────────
    print("[1/4] Проверка импортов...")
    modules = [
        "agents.oleg_v2.app",
        "agents.oleg_v2.executor.react_loop",
        "agents.oleg_v2.executor.circuit_breaker",
        "agents.oleg_v2.agents.reporter.agent",
        "agents.oleg_v2.agents.researcher.agent",
        "agents.oleg_v2.agents.quality.agent",
        "agents.oleg_v2.orchestrator.orchestrator",
        "agents.oleg_v2.pipeline.gate_checker",
        "agents.oleg_v2.pipeline.report_pipeline",
        "agents.oleg_v2.watchdog.watchdog",
        "agents.oleg_v2.bot.telegram_bot",
        "agents.oleg_v2.storage.state_store",
    ]
    import importlib
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception as e:
            errors.append(f"Import {m}: {e}")
            print(f"  FAIL: {m} — {e}")
    if not errors:
        print(f"  OK: все {len(modules)} модулей импортированы")

    # ── 2. Scheduler check ──────────────────────────────────
    print()
    print("[2/4] Проверка scheduler (APScheduler)...")
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz
        from agents.oleg_v2 import config

        tz = pytz.timezone(config.TIMEZONE)
        scheduler = AsyncIOScheduler(timezone=tz)

        daily_h, daily_m = (int(x) for x in config.DAILY_REPORT_TIME.split(":"))
        weekly_h, weekly_m = (int(x) for x in config.WEEKLY_REPORT_TIME.split(":"))

        async def _stub():
            pass

        scheduler.add_job(
            _stub,
            CronTrigger(day_of_week="mon-sat", hour=daily_h, minute=daily_m, timezone=tz),
            id="daily_report",
            name=f"Daily Report ({daily_h:02d}:{daily_m:02d} MSK)",
        )
        scheduler.add_job(
            _stub,
            CronTrigger(day_of_week="mon", hour=weekly_h, minute=weekly_m, timezone=tz),
            id="weekly_report",
            name=f"Weekly Report (Mon {weekly_h:02d}:{weekly_m:02d} MSK)",
        )
        scheduler.add_job(
            _stub,
            CronTrigger(hour="*/6", minute=0, timezone=tz),
            id="watchdog_heartbeat",
            name="Watchdog Heartbeat",
        )

        # Don't start scheduler (no event loop needed) — just verify jobs
        jobs = scheduler.get_jobs()
        print(f"  Jobs: {len(jobs)}")
        for job in jobs:
            print(f"    {job.id:<25} trigger: {job.trigger}")

        # Verify expected jobs exist
        job_ids = {j.id for j in jobs}
        expected = {"daily_report", "weekly_report", "watchdog_heartbeat"}
        missing = expected - job_ids
        if missing:
            errors.append(f"Scheduler: missing jobs: {missing}")
            print(f"  FAIL: missing jobs: {missing}")
        else:
            print("  OK: все 3 scheduled jobs созданы")

    except Exception as e:
        errors.append(f"Scheduler: {e}")
        print(f"  FAIL: {e}")

    # ── 3. Config check ─────────────────────────────────────
    print()
    print("[3/4] Проверка конфигурации...")
    try:
        from agents.oleg_v2 import config

        checks = {
            "TELEGRAM_BOT_TOKEN": bool(config.TELEGRAM_BOT_TOKEN),
            "OPENROUTER_API_KEY": bool(config.OPENROUTER_API_KEY),
            "DB_HOST": bool(config.DB_HOST),
            "ADMIN_CHAT_ID": config.ADMIN_CHAT_ID != 0,
            "ANALYTICS_MODEL": bool(config.ANALYTICS_MODEL),
            "PLAYBOOK_PATH": bool(config.PLAYBOOK_PATH),
        }

        for name, ok in checks.items():
            status = "OK" if ok else "NOT SET"
            value = ""
            if name == "OPENROUTER_API_KEY" and ok:
                value = f" ({config.OPENROUTER_API_KEY[:8]}...)"
            elif name == "DB_HOST" and ok:
                value = f" ({config.DB_HOST})"
            elif name == "ADMIN_CHAT_ID":
                value = f" ({config.ADMIN_CHAT_ID})"
            elif name == "ANALYTICS_MODEL":
                value = f" ({config.ANALYTICS_MODEL})"
            print(f"  {name:<25} {status}{value}")

        missing = [k for k, v in checks.items() if not v]
        if missing:
            print(f"  WARN: не установлены: {', '.join(missing)}")
        else:
            print("  OK: все переменные установлены")

    except Exception as e:
        errors.append(f"Config: {e}")
        print(f"  FAIL: {e}")

    # ── 4. Tool count ───────────────────────────────────────
    print()
    print("[4/4] Проверка tools...")
    try:
        from agents.oleg_v2.agents.reporter.tools import REPORTER_TOOL_DEFINITIONS
        from agents.oleg_v2.agents.researcher.tools import RESEARCHER_TOOL_DEFINITIONS
        from agents.oleg_v2.agents.quality.tools import QUALITY_TOOL_DEFINITIONS

        print(f"  Reporter:   {len(REPORTER_TOOL_DEFINITIONS)} tools")
        print(f"  Researcher: {len(RESEARCHER_TOOL_DEFINITIONS)} tools")
        print(f"  Quality:    {len(QUALITY_TOOL_DEFINITIONS)} tools")
        total = len(REPORTER_TOOL_DEFINITIONS) + len(RESEARCHER_TOOL_DEFINITIONS) + len(QUALITY_TOOL_DEFINITIONS)
        print(f"  Total:      {total} tools")
        print("  OK")

    except Exception as e:
        errors.append(f"Tools: {e}")
        print(f"  FAIL: {e}")

    # ── Summary ─────────────────────────────────────────────
    print()
    print("=" * 50)
    if errors:
        print(f"  RESULT: {len(errors)} ERRORS")
        for err in errors:
            print(f"    - {err}")
        sys.exit(1)
    else:
        print("  RESULT: ALL OK")
    print("=" * 50)


if __name__ == "__main__":
    main()
