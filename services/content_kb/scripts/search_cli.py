#!/usr/bin/env python3
"""CLI for testing content search."""

import asyncio
import json
import sys
import logging

logging.basicConfig(level=logging.INFO)


async def main():
    from services.content_kb.search import search_content

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "каталожное фото Bella"
    print(f"Searching: {query}\n")

    result = await search_content(query, limit=5, include_preview=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
