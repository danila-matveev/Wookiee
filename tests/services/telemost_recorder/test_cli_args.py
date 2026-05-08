"""Test that the recorder CLI supports --meeting-id and --output-dir."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.telemost_record import _build_parser


def test_join_subparser_accepts_meeting_id_and_output_dir():
    parser = _build_parser()
    args = parser.parse_args([
        "join",
        "https://telemost.yandex.ru/j/abc",
        "--meeting-id", "11111111-1111-1111-1111-111111111111",
        "--output-dir", "/tmp/out",
    ])
    assert args.command == "join"
    assert args.url == "https://telemost.yandex.ru/j/abc"
    assert args.meeting_id == "11111111-1111-1111-1111-111111111111"
    assert args.output_dir == "/tmp/out"


def test_join_subparser_old_invocation_still_works():
    """Backward compat: positional url + --name only must still parse."""
    parser = _build_parser()
    args = parser.parse_args([
        "join",
        "https://telemost.yandex.ru/j/abc",
        "--name", "Wookiee",
    ])
    assert args.url == "https://telemost.yandex.ru/j/abc"
    assert args.name == "Wookiee"
    assert args.meeting_id is None
    assert args.output_dir is None
