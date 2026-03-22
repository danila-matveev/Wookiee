#!/usr/bin/env python3
"""Run full content indexing pipeline."""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    from services.content_kb.indexer import index_all

    dry_run = "--dry-run" in sys.argv
    root = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            root = arg

    result = await index_all(root=root, dry_run=dry_run)
    print(f"\nResults: {result}")


if __name__ == "__main__":
    asyncio.run(main())
