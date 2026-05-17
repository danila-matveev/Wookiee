#!/usr/bin/env python3
"""
Wookiee Telemost Recorder — CLI entry point.

Usage:
    python scripts/telemost_record.py join <url> [--name NAME]
    docker exec telemost_recorder python scripts/telemost_record.py join <url>
"""
import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.telemost_recorder.config import BOT_NAME  # noqa: E402
from services.telemost_recorder.join import run_session  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telemost_record",
        description="Join a Yandex Telemost meeting as Саймон bot",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    join_p = sub.add_parser("join", help="Join a meeting and hold the session open")
    join_p.add_argument("url", help="Telemost meeting URL (telemost.yandex.ru/j/...)")
    join_p.add_argument("--name", default=None, help=f"Bot display name (default: {BOT_NAME!r})")
    join_p.add_argument(
        "--meeting-id",
        default=None,
        help=(
            "Override meeting_id (UUID string). Used by the API service to keep "
            "container artefacts in sync with telemost.meetings rows."
        ),
    )
    join_p.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Override output dir for screenshots/audio/transcript. Defaults to "
            "data/telemost/<meeting_id>."
        ),
    )

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    bot_name = args.name or BOT_NAME

    if args.command == "join":
        try:
            asyncio.run(run_session(
                args.url,
                bot_name=bot_name,
                meeting_id=args.meeting_id,
                output_dir=args.output_dir,
            ))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
