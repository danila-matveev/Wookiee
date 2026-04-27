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
    from services.sheets_sync.sync.sync_promocodes import ensure_analytics_sheet, _read_pivot_state
    from services.sheets_sync.sync.format_promocodes_sheet import apply_base_formatting, format_week_columns

    ws = ensure_analytics_sheet()
    apply_base_formatting(ws)

    week_col_map, _ = _read_pivot_state(ws)
    for idx, (label, first_col) in enumerate(sorted(week_col_map.items(), key=lambda x: x[1])):
        format_week_columns(ws, first_col, week_index=idx)
        print(f"  formatted week {label} (col {first_col}, idx={idx})")

    print(f"OK: formatting applied to '{ws.title}' ({len(week_col_map)} week columns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
