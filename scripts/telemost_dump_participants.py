#!/usr/bin/env python3
"""Operator one-shot: capture the Telemost participants-panel DOM from a real
meeting so the extract_participants() selectors can be rebuilt against the
live Yandex 360 corporate UI.

Why: on telemost.360.yandex.ru the panel renders with different CSS classes
than the public telemost.yandex.ru build, so extract_participants() returns
[] in production. Without a live HTML dump we'd be guessing at selectors.

Usage:
    # On your Mac, with the Yandex 360 storage_state already exported:
    TELEMOST_STORAGE_STATE_PATH=data/telemost_storage_state.json \\
        python scripts/telemost_dump_participants.py \\
            https://telemost.360.yandex.ru/j/<meeting-id>

    1. Chromium opens authenticated as recorder@wookiee.shop.
    2. The meeting page loads. Walk it through the join flow yourself
       (Подключиться, etc.). It's faster than re-implementing FSM here.
    3. Once you see real participants in the call, return to this terminal
       and press Enter.
    4. Script clicks "Участники", captures the panel HTML, saves to
       data/dom_dumps/<timestamp>.html.

Env:
    TELEMOST_STORAGE_STATE_PATH — same path as the recorder uses
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright  # noqa: E402

from services.telemost_recorder.join import dump_participants_dom  # noqa: E402


async def _run(meeting_url: str, out_dir: Path) -> int:
    storage_state = os.environ.get("TELEMOST_STORAGE_STATE_PATH", "").strip()
    if not storage_state or not os.path.isfile(storage_state):
        print(
            "ERROR: TELEMOST_STORAGE_STATE_PATH not set or file missing.\n"
            "Export cookies first: python scripts/telemost_export_cookies.py",
            file=sys.stderr,
        )
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()

        print(f">> Opening {meeting_url}")
        await page.goto(meeting_url, wait_until="domcontentloaded")

        print()
        print("=" * 70)
        print("  Step 1: walk through the join flow in the Chromium window")
        print("          (Подключиться, accept any prompts).")
        print("  Step 2: confirm you can see other participants on the call.")
        print("  Step 3: come back here and press Enter to dump the DOM.")
        print("=" * 70)
        print()
        await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

        ts = int(time.time())
        per_run_dir = out_dir / str(ts)
        dump_path = await dump_participants_dom(page, per_run_dir)
        if dump_path is None:
            print("ERROR: dump_participants_dom returned None", file=sys.stderr)
            await context.close()
            await browser.close()
            return 1

        print()
        print(f"Saved DOM to: {dump_path}")
        print(f"File size:    {dump_path.stat().st_size / 1024:.1f} KB")
        print()
        print("Next steps:")
        print("  1. Open the file, find the participants list elements.")
        print("  2. Add their selectors to services/telemost_recorder/join.py")
        print("     in extract_participants() (data-testid / class patterns).")
        print("  3. Commit and redeploy.")

        await context.close()
        await browser.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("meeting_url", help="Telemost meeting URL (https://telemost.360.yandex.ru/j/...)")
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "data" / "dom_dumps",
        help="Output directory (default: data/dom_dumps)",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.meeting_url, args.out))


if __name__ == "__main__":
    sys.exit(main())
