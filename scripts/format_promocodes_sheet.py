#!/usr/bin/env python3
"""Re-apply visual formatting to the wb-promocodes analytics sheet.

Use after bootstrap, or any time the layout drifts. Idempotent.

    python scripts/format_promocodes_sheet.py
"""
from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> int:
    from services.sheets_sync.sync.sync_promocodes import ensure_analytics_sheet
    from services.sheets_sync.sync.format_promocodes_sheet import apply_visual_formatting

    ws = ensure_analytics_sheet()   # makes sure the sheet + headers exist
    apply_visual_formatting(ws)
    print(f"OK: formatting applied to '{ws.title}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
