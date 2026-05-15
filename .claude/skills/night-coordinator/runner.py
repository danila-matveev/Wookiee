"""Night coordinator runner.

Invoked by .github/workflows/night-coordinator.yml at 04:00 UTC.
Reads JSON reports → applies decisions → fixes SAFE → opens 1 PR with auto-merge.
See SKILL.md for full behavior.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from shared.hygiene import config as hygiene_config
from shared.hygiene import decisions as hygiene_decisions
from shared.hygiene import queue as hygiene_queue
from shared.hygiene import reports as hygiene_reports
from shared.hygiene.schemas import Finding, QueueItem

# Match SAFE-whitelist from plan §6
SAFE_TYPES = {
    "orphan-import",
    "broken-doc-link",
    "skill-registry-drift",
    "stray-binary",
    "gitignore-violation",
}

MAX_FIXES_PER_RUN = 10


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def _coverage_blocks() -> bool:
    """Check if today's coverage report has blocking flag."""
    today = date.today().isoformat()
    path = Path(f".hygiene/reports/coverage-{today}.json")
    if not path.exists():
        return False
    data = json.loads(path.read_text())
    return bool(data.get("blocking", False))


def _gather_findings() -> list[Finding]:
    """Load all today's reports and return all findings."""
    today = date.today().isoformat()
    findings: list[Finding] = []
    for report in hygiene_reports.load_reports_for_date(today):
        findings.extend(report.findings)
    return findings


def _apply_safe(finding: Finding) -> dict | None:
    """Apply a SAFE fix. Returns dict with action details or None on skip."""
    # Stub — real implementation depends on the autofix module
    # which lives in .claude/skills/hygiene-autofix/. For now, we
    # delegate to that skill's apply_finding if available.
    try:
        from .hygiene_autofix_apply import apply_finding  # type: ignore
    except ImportError:
        return None
    return apply_finding(finding)


def _send_telegram_digest(queue: list[QueueItem], cfg: dict) -> None:
    if not queue:
        return
    try:
        from shared.telegram_digest import render_needs_human_digest, send_digest
        message = render_needs_human_digest(queue)
        send_digest(message, level="info")
    except Exception as exc:
        print(f"[night-coordinator] Telegram digest failed: {exc}", file=sys.stderr)


def _send_failure_alert(error: str) -> None:
    try:
        from shared.telegram_digest import render_failure_alert, send_digest
        message = render_failure_alert("night-coordinator", error)
        send_digest(message, level="error")
    except Exception as exc:
        print(f"[night-coordinator] failure-alert failed: {exc}", file=sys.stderr)


def main() -> int:
    cfg = hygiene_config.load_config()

    if _coverage_blocks():
        _send_failure_alert("test-coverage упал > 2 п.п. — фиксы отложены до восстановления покрытия")
        return 1

    findings = _gather_findings()
    if not findings:
        print("[night-coordinator] no findings today — exiting cleanly")
        return 0

    decisions_path = Path(".hygiene/decisions.yaml")
    decisions = hygiene_decisions.load_decisions(decisions_path) if decisions_path.exists() else {}

    safe_to_apply: list[Finding] = []
    needs_human: list[QueueItem] = []

    for f in findings:
        decision = hygiene_decisions.match(decisions, f.id)
        if decision and decision.get("decision") in ("delete", "keep", "exclude"):
            # apply known decision (stub — in real flow this calls apply_finding too)
            print(f"[night-coordinator] applying known decision for {f.id}: {decision['decision']}")
            continue

        if f.type in SAFE_TYPES:
            if len(safe_to_apply) < MAX_FIXES_PER_RUN:
                safe_to_apply.append(f)
            else:
                needs_human.append(QueueItem.from_finding(f, reason="overflow-from-safe-cap"))
        else:
            needs_human.append(QueueItem.from_finding(f, reason="not-in-safe-whitelist"))

    # Persist queue
    if needs_human:
        queue_path = Path(".hygiene/queue.yaml")
        hygiene_queue.append_items(queue_path, needs_human)

    if cfg.get("read_only", True):
        print(f"[night-coordinator] READ-ONLY: would apply {len(safe_to_apply)} fixes, {len(needs_human)} questions queued")
        # In read-only we still send the Telegram digest so user sees what would happen
        _send_telegram_digest(needs_human, cfg)
        return 0

    # Production mode — apply fixes, create branch, push, open PR with auto-merge
    applied = []
    for finding in safe_to_apply:
        result = _apply_safe(finding)
        if result:
            applied.append(result)

    if not applied and not needs_human:
        return 0

    if applied:
        branch = f"night-devops/{date.today().isoformat()}"
        _run(["git", "checkout", "-b", branch])
        for action in applied:
            files = action.get("files_changed", [])
            if files:
                _run(["git", "add"] + files)
        _run(["git", "commit", "-m", f"chore(night-devops): apply {len(applied)} SAFE fixes\n\n[automated by /night-coordinator]"])
        _run(["git", "push", "-u", "origin", branch])
        pr_url = _run(["gh", "pr", "create", "--title", f"chore(night-devops): {len(applied)} auto-fixes for {date.today().isoformat()}", "--body", _build_pr_body(applied, needs_human)]).stdout.strip()
        _run(["gh", "pr", "merge", "--auto", "--squash", "--delete-branch", pr_url])

    _send_telegram_digest(needs_human, cfg)
    return 0


def _build_pr_body(applied: list[dict], needs_human: list[QueueItem]) -> str:
    lines = [f"Применил {len(applied)} автофиксов:\n"]
    for a in applied:
        lines.append(f"- {a.get('finding_type', '?')}: {a.get('description', '')}")
    if needs_human:
        lines.append(f"\nЕщё {len(needs_human)} вопросов — в Telegram пришёл digest с командой /hygiene-resolve.")
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        _send_failure_alert(f"{type(exc).__name__}: {exc}")
        sys.exit(1)
