"""Runner for the /heartbeat skill (Wave B4).

Aggregates today's hygiene + code-quality + coverage reports, renders a
short plain-Russian Telegram message via shared.telegram_digest. Honors
heartbeat_enabled / heartbeat_quiet_if_zero flags from .hygiene/config.yaml.

CLI: python scripts/nightly/heartbeat.py
     python scripts/nightly/heartbeat.py --dry-run    # render, don't send
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from shared.hygiene.schemas import HeartbeatSummary
from shared.telegram_digest import (
    MAX_HEARTBEAT_LEN,
    render_heartbeat,
    send_digest,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_DIR = REPO_ROOT / ".hygiene"
REPORTS_DIR = HYGIENE_DIR / "reports"
CONFIG_PATH = HYGIENE_DIR / "config.yaml"

_RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _date_ru(d: date) -> str:
    return f"{d.day} {_RU_MONTHS[d.month]}"


def _load_yaml_config(path: Path) -> dict:
    """Minimal YAML reader (avoid hard PyYAML dep at module-import time)."""
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        # Best-effort: parse only the keys we care about with naive regex.
        text = path.read_text()
        result: dict[str, Any] = {}
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("heartbeat_enabled:"):
                result["heartbeat_enabled"] = "true" in line.lower()
            elif line.startswith("heartbeat_quiet_if_zero:"):
                result["heartbeat_quiet_if_zero"] = "true" in line.lower()
        return result
    return yaml.safe_load(path.read_text()) or {}


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        logger.warning("heartbeat: %s is not valid JSON, skipping", path)
        return None


def _today_reports(reports_dir: Path, today: date) -> dict[str, dict | None]:
    """Pull today's three reports: hygiene, code-quality, coverage."""
    ds = today.strftime("%Y-%m-%d")
    return {
        "hygiene": _load_json(reports_dir / f"hygiene-{ds}.json"),
        "code_quality": _load_json(reports_dir / f"code-quality-{ds}.json"),
        "coverage": _load_json(reports_dir / f"coverage-{ds}.json"),
        "coordinator": _load_json(reports_dir / f"coordinator-{ds}.json"),
    }


def _count_fixes(reports: dict[str, dict | None]) -> tuple[int, list[str]]:
    """Count fixes applied today, return (count, short_example_phrases)."""
    examples: list[str] = []
    fix_count = 0

    coordinator = reports.get("coordinator")
    if coordinator and isinstance(coordinator, dict):
        # Coordinator's summary is the source of truth if available.
        applied = coordinator.get("fixes_applied") or []
        if isinstance(applied, list):
            fix_count = len(applied)
            for item in applied[:3]:
                if isinstance(item, dict) and "ru_label" in item:
                    examples.append(str(item["ru_label"]))
                elif isinstance(item, str):
                    examples.append(item)
        elif isinstance(applied, int):
            fix_count = applied

    # Fallback: count safe_to_autofix findings in hygiene + code-quality.
    if fix_count == 0:
        cats: dict[str, int] = {}
        for src in ("hygiene", "code_quality"):
            rpt = reports.get(src)
            if not rpt:
                continue
            for f in rpt.get("findings", []):
                if f.get("safe_to_autofix"):
                    fix_count += 1
                    cats[f.get("category", "прочее")] = cats.get(f.get("category", "прочее"), 0) + 1
        if cats:
            ru_map = {
                "orphan-imports": "лишние импорты",
                "orphan-docs": "сиротские доки",
                "broken-doc-links": "битые ссылки",
                "skill-registry-drift": "сдвиг реестра скиллов",
                "lint-error": "lint-замечания",
                "type-error": "ошибки типов",
                "dead-code": "мёртвый код",
            }
            examples = [
                f"{ru_map.get(cat, cat)} ({n})"
                for cat, n in sorted(cats.items(), key=lambda kv: -kv[1])[:3]
            ]

    return fix_count, examples


def _count_needs_human(reports: dict[str, dict | None]) -> int:
    total = 0
    for src in ("hygiene", "code_quality"):
        rpt = reports.get(src)
        if not rpt:
            continue
        summary = rpt.get("summary", {}) or {}
        if "needs_human" in summary:
            total += int(summary.get("needs_human", 0) or 0)
        else:
            total += sum(1 for f in rpt.get("findings", []) if not f.get("safe_to_autofix"))
    return total


def _coverage_info(reports: dict[str, dict | None]) -> tuple[float | None, float | None]:
    rpt = reports.get("coverage")
    if not rpt:
        return None, None
    cur = rpt.get("current_pct")
    delta = rpt.get("delta_pct")
    try:
        cur_f = float(cur) if cur is not None else None
    except (TypeError, ValueError):
        cur_f = None
    try:
        delta_f = float(delta) if delta is not None else None
    except (TypeError, ValueError):
        delta_f = None
    return cur_f, delta_f


def _pr_info(reports: dict[str, dict | None]) -> tuple[int | None, str | None]:
    coord = reports.get("coordinator")
    if not coord:
        return None, None
    pr = coord.get("pr") or {}
    return pr.get("number"), pr.get("status")


def build_summary(
    *,
    reports: dict[str, dict | None] | None = None,
    today: date | None = None,
    failure: str | None = None,
) -> HeartbeatSummary:
    today = today or datetime.now(timezone.utc).date()
    reports = reports or _today_reports(REPORTS_DIR, today)

    fix_count, examples = _count_fixes(reports)
    needs_human = _count_needs_human(reports)
    cov_pct, cov_delta = _coverage_info(reports)
    pr_num, pr_status = _pr_info(reports)

    return HeartbeatSummary(
        date_str=_date_ru(today),
        fixes_applied=fix_count,
        fixes_examples=examples,
        needs_human_count=needs_human,
        coverage_pct=cov_pct,
        coverage_delta_pp=cov_delta,
        pr_number=pr_num,
        pr_status=pr_status,
        failure=failure,
    )


def is_enabled(config: dict | None = None) -> bool:
    if config is None:
        config = _load_yaml_config(CONFIG_PATH)
    return bool(config.get("heartbeat_enabled", True))


def should_be_quiet(summary: HeartbeatSummary, config: dict | None = None) -> bool:
    if config is None:
        config = _load_yaml_config(CONFIG_PATH)
    if not config.get("heartbeat_quiet_if_zero", True):
        return False
    if summary.failure:
        return False
    return (
        summary.fixes_applied == 0
        and summary.needs_human_count == 0
        and (summary.pr_number is None or summary.pr_status in (None, "merged"))
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print message, don't send")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = _load_yaml_config(args.config)

    if not is_enabled(cfg):
        print("[heartbeat] disabled via config — skipping")
        return 0

    today = datetime.now(timezone.utc).date()
    reports = _today_reports(args.reports_dir, today)
    summary = build_summary(reports=reports, today=today)

    if not summary.failure and should_be_quiet(summary, cfg):
        print("[heartbeat] quiet day (fixes=0 needs_human=0 pr=None) — skipping send")
        return 0

    message = render_heartbeat(summary)
    if len(message) > MAX_HEARTBEAT_LEN:
        logger.warning("heartbeat message %d > %d chars; truncating", len(message), MAX_HEARTBEAT_LEN)
        message = message[: MAX_HEARTBEAT_LEN - 3] + "..."

    print(f"[heartbeat] ({len(message)} chars)")
    print(message)
    print()

    if args.dry_run:
        print("[heartbeat] dry-run — not sending")
        return 0

    try:
        send_digest(message, level="info")
    except RuntimeError as e:
        logger.error("heartbeat send failed: %s", e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
