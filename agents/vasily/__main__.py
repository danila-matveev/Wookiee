"""Allow running as: python -m agents.vasily"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from agents.vasily import config


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


def main() -> None:
    _setup_logging()
    logger = logging.getLogger("vasily_agent")

    logger.info("Vasily Agent v0.1")
    logger.info("Кабинеты: %s", ", ".join(config.CABINETS))
    logger.info("Расписание: %s в %02d:%02d МСК, период анализа: %d дн.",
                config.REPORT_DAY_OF_WEEK, config.REPORT_HOUR,
                config.REPORT_MINUTE, config.REPORT_PERIOD_DAYS)

    if not config.VASILY_SPREADSHEET_ID:
        logger.warning("VASILY_SPREADSHEET_ID не задан — экспорт в Sheets отключён")
    if not config.BITRIX_WEBHOOK_URL:
        logger.warning("Bitrix_rest_api не задан — уведомления в Bitrix отключены")
    if not config.BITRIX_CHAT_ID:
        logger.warning("VASILY_BITRIX_CHAT_ID не задан — уведомления в Bitrix отключены")

    from agents.vasily.scheduler import VasilyScheduler

    scheduler = VasilyScheduler()
    try:
        asyncio.run(scheduler.start())
    except KeyboardInterrupt:
        logger.info("Vasily Agent остановлен")


if __name__ == "__main__":
    main()
