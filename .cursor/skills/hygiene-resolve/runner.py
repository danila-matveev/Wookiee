"""Hygiene resolve runner — minimal entry point.

Invoked locally by user pasting /hygiene-resolve from Telegram.
The actual interactive dialog is driven by SKILL.md (Claude reads
the prompt and asks the user questions in plain Russian).
This runner exists for non-Claude invocations (e.g. testing).
"""
from __future__ import annotations
import sys
from pathlib import Path

from shared.hygiene import queue as hygiene_queue


def main() -> int:
    queue_path = Path(".hygiene/queue.yaml")
    if not queue_path.exists():
        print("Готово, вопросов нет.")
        return 0
    items = hygiene_queue.load_queue(queue_path)
    pending = [i for i in items if not i.get("resolved")]
    if not pending:
        print("Готово, вопросов нет.")
        return 0
    print(f"В очереди {len(pending)} вопросов. Запусти эту команду в Claude Code для интерактивного разбора.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
