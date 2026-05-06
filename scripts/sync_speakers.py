#!/usr/bin/env python3
"""Refresh data/speakers.yml from Bitrix24.

Usage:
    python scripts/sync_speakers.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.telemost_recorder.config import BITRIX_REST_API, SPEAKERS_FILE  # noqa: E402
from services.telemost_recorder.speakers import save_speakers, sync_from_bitrix  # noqa: E402


def main() -> None:
    if not BITRIX_REST_API:
        print("ERROR: Bitrix_rest_api not set in .env")
        sys.exit(1)
    print("Fetching employees from Bitrix24...")
    employees = sync_from_bitrix()
    save_speakers(employees)
    print(f"Saved {len(employees)} employees to {SPEAKERS_FILE}")


if __name__ == "__main__":
    main()
