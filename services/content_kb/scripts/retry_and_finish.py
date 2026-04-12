#!/usr/bin/env python3
"""
Retry failed files and finish remaining indexing.

1. Reset failed → pending (re-embed them)
2. Run index_all for each root sequentially
"""

import asyncio
import logging

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALL_ROOTS = [
    "/Wookiee/Контент/2025",
    "/Wookiee/Контент/2026",
    "/Wookiee/Блогеры",
]


def reset_failed():
    """Delete failed records so they get re-indexed."""
    from services.content_kb.config import (
        POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
        POSTGRES_USER, POSTGRES_PASSWORD,
    )
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT, dbname=POSTGRES_DB,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute("DELETE FROM content_assets WHERE status = 'failed'")
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Reset %d failed records", deleted)
    return deleted


async def main():
    from services.content_kb.indexer import index_all

    # Step 1: reset failed
    n = reset_failed()
    print(f"Reset {n} failed records\n", flush=True)

    # Step 2: index each root
    for root in ALL_ROOTS:
        print(f"\n{'='*60}", flush=True)
        print(f"Indexing: {root}", flush=True)
        print(f"{'='*60}", flush=True)
        result = await index_all(root=root)
        print(f"Results: {result}", flush=True)

    print("\nAll done!", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
