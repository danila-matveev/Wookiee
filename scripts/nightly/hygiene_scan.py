"""Deterministic hygiene scanner for the Night DevOps pipeline.

The interactive `/hygiene` skill can open branches, PRs and Cloudflare reports.
This runner is intentionally narrower: it only inspects the repository and
writes `.hygiene/reports/hygiene-YYYY-MM-DD.json` for `night-coordinator`.

CLI:
    python -m scripts.nightly.hygiene_scan
    python -m scripts.nightly.hygiene_scan --out /tmp/hygiene.json
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from shared.hygiene.reports import report_path, save_report
from shared.hygiene.schemas import AskUser, FixReport, HygieneFinding, ReportSummary


REPO_ROOT = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = (".xlsx", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".wmv", ".mov", ".mp4", ".zip")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+?(?:\.(?:md|py|sh|ya?ml|json|toml|txt)|/))(?:#[^)]*)?\)")
FENCE_RE = re.compile(r"^```", re.MULTILINE)


def _run_git(repo: Path, args: list[str]) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _sha(parts: Iterable[str]) -> str:
    raw = "\n".join(sorted(parts)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:10]


def _finding(
    *,
    category: str,
    files: list[str],
    rationale: str,
    severity: str = "low",
    safe_to_autofix: bool = False,
    autofix_kind: str | None = None,
    rollback_command: str | None = None,
    question_ru: str | None = None,
    options: list[str] | None = None,
    default_after_7d: str | None = None,
) -> HygieneFinding:
    ask_user = None
    if question_ru:
        ask_user = AskUser(
            question_ru=question_ru,
            options=options or ["fix", "keep"],
            default_after_7d=default_after_7d or (options or ["fix"])[0],
        )
    return HygieneFinding(
        id=f"hygiene-{category}-{_sha(files + [rationale])}",
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        safe_to_autofix=safe_to_autofix,
        autofix_kind=autofix_kind,
        files=files,
        rationale=rationale,
        rollback_command=rollback_command,
        ask_user=ask_user,
    )


def _load_hygiene_config(repo: Path) -> dict:
    path = repo / ".claude" / "hygiene-config.yaml"
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _binary_whitelist(config: dict) -> list[str]:
    return list(((config.get("whitelist") or {}).get("binaries_keep") or []))


def _is_whitelisted(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def scan_stray_binaries(repo: Path, config: dict) -> list[HygieneFinding]:
    whitelist = _binary_whitelist(config)
    findings: list[HygieneFinding] = []
    for path in _run_git(repo, ["ls-files"]):
        if not path.lower().endswith(BINARY_SUFFIXES):
            continue
        if _is_whitelisted(path, whitelist):
            continue
        findings.append(
            _finding(
                category="stray-binary",
                files=[path],
                rationale="Tracked binary is outside .claude/hygiene-config.yaml whitelist.binaries_keep.",
                severity="medium",
                question_ru=f"`{path}` is a tracked binary outside the whitelist. Keep it in git or move it out?",
                options=["keep-and-whitelist", "remove-from-git"],
                default_after_7d="keep-and-whitelist",
            )
        )
    return findings


def scan_gitignore_violations(repo: Path) -> list[HygieneFinding]:
    ignored = _run_git(repo, ["ls-files", "--ignored", "--exclude-standard", "--cached"])
    if not ignored:
        return []

    groups: dict[str, list[str]] = {}
    for path in ignored:
        key = ".agents/skills/" if path.startswith(".agents/skills/") else path
        groups.setdefault(key, []).append(path)

    findings: list[HygieneFinding] = []
    for key, files in groups.items():
        label = key if key.endswith("/") else files[0]
        findings.append(
            _finding(
                category="gitignore-violation",
                files=files,
                rationale=f"`{label}` is tracked by git but also matched by .gitignore.",
                severity="low",
                question_ru=f"`{label}` is tracked but gitignored. Should it be untracked or should .gitignore be relaxed?",
                options=["untrack", "unignore", "keep-for-now"],
                default_after_7d="untrack",
            )
        )
    return findings


def scan_cross_platform_skills(repo: Path) -> list[HygieneFinding]:
    source = repo / ".claude" / "skills"
    if not source.exists():
        return []
    claude_skills = {p.name for p in source.iterdir() if p.is_dir()}
    findings: list[HygieneFinding] = []
    for target_name in (".cursor/skills", ".codex/skills"):
        target = repo / target_name
        target_skills = {p.name for p in target.iterdir() if p.is_dir()} if target.exists() else set()
        missing = sorted(claude_skills - target_skills)
        if not missing:
            continue
        files = [f"{target_name}/{name}" for name in missing]
        findings.append(
            _finding(
                category="cross-platform-skill-prep",
                files=files,
                rationale=f"{len(missing)} skill(s) exist in .claude/skills but are missing from {target_name}.",
                safe_to_autofix=True,
                autofix_kind="sync-skill-mirror",
                rollback_command="git rm -r --cached .cursor/skills .codex/skills && git checkout -- .cursor/skills .codex/skills",
            )
        )
    return findings


def _fenced_ranges(text: str) -> list[tuple[int, int]]:
    fences = [match.start() for match in FENCE_RE.finditer(text)]
    return [(fences[i], fences[i + 1]) for i in range(0, len(fences) - 1, 2)]


def scan_broken_doc_links(repo: Path) -> list[HygieneFinding]:
    docs = repo / "docs"
    if not docs.exists():
        return []
    findings: list[HygieneFinding] = []
    for src in docs.rglob("*.md"):
        text = src.read_text(encoding="utf-8")
        skips = _fenced_ranges(text)
        rel_src = src.relative_to(repo)
        for match in LINK_RE.finditer(text):
            if any(start <= match.start() < end for start, end in skips):
                continue
            link = match.group(1)
            if link.startswith(("http://", "https://", "mailto:", "#", "/")) or not link:
                continue
            candidates = [(src.parent / link).resolve(), (repo / link).resolve()]
            if any(candidate.exists() for candidate in candidates):
                continue
            line_no = text[: match.start()].count("\n") + 1
            findings.append(
                _finding(
                    category="broken-doc-links",
                    files=[str(rel_src)],
                    rationale=f"Line {line_no} links to missing target `{link}`.",
                    question_ru=f"`{rel_src}:{line_no}` links to missing `{link}`. Fix the link or create the target?",
                    options=["fix-link", "create-target", "leave-for-now"],
                    default_after_7d="fix-link",
                )
            )
    return findings


def scan_missing_readmes(repo: Path) -> list[HygieneFinding]:
    services = repo / "services"
    if not services.exists():
        return []
    findings: list[HygieneFinding] = []
    for child in sorted(services.iterdir()):
        if not child.is_dir() or child.name.startswith("__"):
            continue
        readme = child / "README.md"
        if readme.exists():
            continue
        rel = str(child.relative_to(repo))
        findings.append(
            _finding(
                category="missing-readme",
                files=[rel],
                rationale="Service directory has no README.md.",
                question_ru=f"`{rel}/` has no README.md. Add a service stub or mark it as intentionally undocumented?",
                options=["add-readme", "document-exception"],
                default_after_7d="add-readme",
            )
        )
    return findings


def build_report(repo: Path) -> FixReport:
    started = datetime.now(timezone.utc)
    config = _load_hygiene_config(repo)
    findings: list[HygieneFinding] = []
    findings.extend(scan_stray_binaries(repo, config))
    findings.extend(scan_gitignore_violations(repo))
    findings.extend(scan_cross_platform_skills(repo))
    findings.extend(scan_broken_doc_links(repo))
    findings.extend(scan_missing_readmes(repo))

    finished = datetime.now(timezone.utc)
    categories = Counter(f.category for f in findings)
    commit_sha = (_run_git(repo, ["rev-parse", "HEAD"]) or ["unknown"])[0]
    return FixReport(
        run_id=f"hygiene-{started.strftime('%Y%m%dT%H%M%SZ')}",
        started_at=started,
        finished_at=finished,
        commit_sha=commit_sha,
        findings=findings,
        summary=ReportSummary(
            total=len(findings),
            safe_to_autofix=sum(1 for f in findings if f.safe_to_autofix),
            needs_human=sum(1 for f in findings if not f.safe_to_autofix),
            categories=dict(sorted(categories.items())),
        ),
    )


def render_markdown(report: FixReport) -> str:
    lines = [
        f"# Wookiee Hygiene Run {report.started_at.date().isoformat()}",
        "",
        f"- Run: `{report.run_id}`",
        f"- Commit: `{report.commit_sha}`",
        f"- Findings: {report.summary.total}",
        f"- Safe to autofix: {report.summary.safe_to_autofix}",
        f"- Needs human: {report.summary.needs_human}",
        "",
    ]
    if not report.findings:
        lines.append("No hygiene findings.")
        return "\n".join(lines) + "\n"

    lines.append("## Findings")
    for finding in report.findings:
        files = ", ".join(f"`{p}`" for p in finding.files[:8])
        if len(finding.files) > 8:
            files += f", ... ({len(finding.files)} total)"
        lines.extend(
            [
                "",
                f"### {finding.category}",
                f"- Severity: `{finding.severity}`",
                f"- Safe to autofix: `{str(finding.safe_to_autofix).lower()}`",
                f"- Files: {files}",
                f"- Rationale: {finding.rationale}",
            ]
        )
        if finding.ask_user:
            lines.append(f"- Question: {finding.ask_user.question_ru}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(REPO_ROOT), help="Repository root")
    parser.add_argument("--out", help="JSON output path; defaults to .hygiene/reports/hygiene-YYYY-MM-DD.json")
    parser.add_argument("--markdown-out", help="Markdown output path; defaults next to JSON")
    parser.add_argument("--print-summary", action="store_true", help="Print report summary JSON to stdout")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"Not a git repo: {repo}", file=sys.stderr)
        return 2

    report = build_report(repo)
    out = Path(args.out) if args.out else report_path("hygiene", report.started_at.date(), repo / ".hygiene" / "reports")
    if not out.is_absolute():
        out = repo / out
    save_report(report, out)

    markdown_out = Path(args.markdown_out) if args.markdown_out else out.with_suffix(".md")
    if not markdown_out.is_absolute():
        markdown_out = repo / markdown_out
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    if args.print_summary:
        print(json.dumps(report.summary.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    else:
        print(f"Wrote {out}")
        print(f"Wrote {markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
