"""Code-quality scan runner — wraps ruff/mypy/vulture/pip-deptree, emits JSON.

Output: .hygiene/reports/code-quality-YYYYMMDD.json per plan §3.2.

Usage:
    python .claude/skills/code-quality-scan/runner.py --repo <path> --out <json>
    python .claude/skills/code-quality-scan/runner.py --dry-run        # print to stdout
    python .claude/skills/code-quality-scan/runner.py --no-codex       # skip sidecar

Exit codes:
    0  success (report written)
    1  one or more wrapped tools failed catastrophically (binary missing)
    2  --repo path doesn't exist
    3  output directory unwritable

Wave B3 of `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md`.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

REPORT_VERSION = "1.0.0"
SCHEMA_URL = "https://wookiee.shop/schemas/code-quality-report-v1.json"

# Paths the night-coordinator lints (matches CI's `ruff check agents services shared scripts`)
DEFAULT_LINT_PATHS = ["agents", "services", "shared", "scripts"]

# Hard timeout per tool — keep the night run bounded
TOOL_TIMEOUT_SECONDS = 300

# Vulture default min-confidence; raise to keep false-positives manageable
VULTURE_MIN_CONFIDENCE = 70


@dataclass
class Finding:
    """One line in the code-quality report (plan §3.2)."""

    id: str
    tool: str
    severity: str  # error | warning | info
    rule_id: Optional[str]
    file: str
    line: Optional[int]
    column: Optional[int]
    message: str
    auto_fixable: bool
    confidence: Optional[int]  # 0–100, especially for vulture


@dataclass
class ToolResult:
    version: str
    exit_code: int
    errors: int


@dataclass
class Report:
    started_at: str
    finished_at: str
    run_id: str
    tools: dict[str, ToolResult] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": SCHEMA_URL,
            "version": REPORT_VERSION,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tools": {name: asdict(t) for name, t in self.tools.items()},
            "findings": [asdict(f) for f in self.findings],
            "summary": {
                "total": len(self.findings),
                "auto_fixable": sum(1 for f in self.findings if f.auto_fixable),
                "needs_human": sum(1 for f in self.findings if not f.auto_fixable),
                "by_tool": {
                    tool: sum(1 for f in self.findings if f.tool == tool)
                    for tool in {f.tool for f in self.findings}
                },
            },
        }


def _slugify(text: str) -> str:
    """Build a stable, file-system-safe id fragment."""
    out = re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-").lower()
    return out[:80] or "x"


def _tool_version(binary: str) -> str:
    """Run `<binary> --version` and return the first line of stdout, or 'missing'."""
    if shutil.which(binary) is None:
        return "missing"
    try:
        completed = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"
    return (completed.stdout or completed.stderr or "unknown").strip().splitlines()[0][:80]


# ---------------------------------------------------------------------------
# ruff
# ---------------------------------------------------------------------------


def _run_ruff(repo: Path, lint_paths: list[str]) -> tuple[ToolResult, list[Finding]]:
    if shutil.which("ruff") is None:
        return ToolResult(version="missing", exit_code=-1, errors=0), []

    targets = [p for p in lint_paths if (repo / p).exists()]
    if not targets:
        return ToolResult(version=_tool_version("ruff"), exit_code=0, errors=0), []

    cmd = ["ruff", "check", "--output-format", "json", "--exit-zero", *targets]
    try:
        completed = subprocess.run(
            cmd,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("ruff timed out after %ss", TOOL_TIMEOUT_SECONDS)
        return ToolResult(version=_tool_version("ruff"), exit_code=-2, errors=0), []

    findings: list[Finding] = []
    try:
        items = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        logger.warning("ruff: could not parse JSON output")
        items = []

    for item in items:
        code = item.get("code") or "unknown"
        location = item.get("location") or {}
        end_location = item.get("end_location") or {}
        filename = item.get("filename") or "?"
        line = location.get("row") or end_location.get("row")
        column = location.get("column") or end_location.get("column")
        rel = Path(filename).relative_to(repo) if Path(filename).is_absolute() else Path(filename)
        fid = f"ruff-{code}-{_slugify(str(rel))}-{line or 0}"
        autofixable = bool(item.get("fix"))
        findings.append(
            Finding(
                id=fid,
                tool="ruff",
                severity="error" if str(code).startswith("E") else "warning",
                rule_id=code,
                file=str(rel),
                line=line,
                column=column,
                message=item.get("message") or "",
                auto_fixable=autofixable,
                confidence=None,
            )
        )

    return (
        ToolResult(version=_tool_version("ruff"), exit_code=completed.returncode, errors=len(findings)),
        findings,
    )


# ---------------------------------------------------------------------------
# mypy
# ---------------------------------------------------------------------------


_MYPY_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?P<severity>error|warning|note):\s*(?P<msg>.+?)(?:\s+\[(?P<code>[a-z-]+)\])?$"
)


def _run_mypy(repo: Path, lint_paths: list[str]) -> tuple[ToolResult, list[Finding]]:
    if shutil.which("mypy") is None:
        return ToolResult(version="missing", exit_code=-1, errors=0), []

    targets = [p for p in lint_paths if (repo / p).exists()]
    if not targets:
        return ToolResult(version=_tool_version("mypy"), exit_code=0, errors=0), []

    # `--no-error-summary` makes parsing simpler; `--show-error-codes` adds [rule-id]
    cmd = [
        "mypy",
        "--ignore-missing-imports",
        "--no-error-summary",
        "--show-error-codes",
        "--show-column-numbers",
        *targets,
    ]
    try:
        completed = subprocess.run(
            cmd,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("mypy timed out after %ss", TOOL_TIMEOUT_SECONDS)
        return ToolResult(version=_tool_version("mypy"), exit_code=-2, errors=0), []

    findings: list[Finding] = []
    for raw_line in (completed.stdout or "").splitlines():
        match = _MYPY_LINE_RE.match(raw_line.strip())
        if not match:
            continue
        if match.group("severity") == "note":
            continue
        file = match.group("file")
        line = int(match.group("line"))
        col = int(match.group("col")) if match.group("col") else None
        code = match.group("code") or "mypy"
        message = match.group("msg").strip()
        fid = f"mypy-{code}-{_slugify(file)}-{line}"
        findings.append(
            Finding(
                id=fid,
                tool="mypy",
                severity=match.group("severity"),
                rule_id=code,
                file=file,
                line=line,
                column=col,
                message=message,
                # Some mypy errors are mechanically fixable (missing return, e.g.) — be conservative.
                auto_fixable=False,
                confidence=None,
            )
        )

    return (
        ToolResult(version=_tool_version("mypy"), exit_code=completed.returncode, errors=len(findings)),
        findings,
    )


# ---------------------------------------------------------------------------
# vulture
# ---------------------------------------------------------------------------


_VULTURE_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<msg>.+?)\s*\((?P<conf>\d+)% confidence\)\s*$"
)


def _run_vulture(repo: Path, lint_paths: list[str]) -> tuple[ToolResult, list[Finding]]:
    if shutil.which("vulture") is None:
        return ToolResult(version="missing", exit_code=-1, errors=0), []

    targets = [p for p in lint_paths if (repo / p).exists()]
    if not targets:
        return ToolResult(version=_tool_version("vulture"), exit_code=0, errors=0), []

    cmd = [
        "vulture",
        "--min-confidence",
        str(VULTURE_MIN_CONFIDENCE),
        *targets,
    ]
    try:
        completed = subprocess.run(
            cmd,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("vulture timed out after %ss", TOOL_TIMEOUT_SECONDS)
        return ToolResult(version=_tool_version("vulture"), exit_code=-2, errors=0), []

    findings: list[Finding] = []
    for raw_line in (completed.stdout or "").splitlines():
        match = _VULTURE_LINE_RE.match(raw_line.strip())
        if not match:
            continue
        file = match.group("file")
        line = int(match.group("line"))
        message = match.group("msg").strip()
        confidence = int(match.group("conf"))
        # Best-effort rule_id from the message ("unused function 'foo'" → "unused-function")
        kind_match = re.match(r"unused (\w+)", message)
        rule_id = f"unused-{kind_match.group(1)}" if kind_match else "dead-code"
        fid = f"vulture-{_slugify(rule_id)}-{_slugify(file)}-{line}"
        findings.append(
            Finding(
                id=fid,
                tool="vulture",
                severity="warning",
                rule_id=rule_id,
                file=file,
                line=line,
                column=None,
                message=message,
                auto_fixable=False,  # never auto-delete dead code without arbiter
                confidence=confidence,
            )
        )

    return (
        ToolResult(version=_tool_version("vulture"), exit_code=completed.returncode, errors=len(findings)),
        findings,
    )


# ---------------------------------------------------------------------------
# pip-deptree / pipdeptree — unused-dep heuristic
# ---------------------------------------------------------------------------


def _collect_requirements(repo: Path) -> dict[str, set[Path]]:
    """Return {package_name_lower: {requirements_paths}} for every requirements*.txt in repo."""
    out: dict[str, set[Path]] = {}
    for req_file in repo.rglob("requirements*.txt"):
        if any(part in {".venv", "node_modules", ".git"} for part in req_file.parts):
            continue
        try:
            text = req_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Strip extras and version markers: "package[extra]>=1.2" -> "package"
            pkg = re.split(r"[<>=!~;\[\s]", line, maxsplit=1)[0].strip().lower()
            if pkg:
                out.setdefault(pkg, set()).add(req_file.relative_to(repo))
    return out


def _grep_import_present(repo: Path, package: str) -> bool:
    """Cheap heuristic: does any *.py file under repo import this package?

    We check the package's import-name (best-effort: package name with dashes -> underscores),
    plus the raw package string as a fallback.
    """
    import_name = package.replace("-", "_")
    needles = {import_name, package}
    # Walk a bounded set of dirs to stay fast
    for path in (repo / "agents", repo / "services", repo / "shared", repo / "scripts", repo / "tests"):
        if not path.exists():
            continue
        for py in path.rglob("*.py"):
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for needle in needles:
                if re.search(rf"^\s*(?:import|from)\s+{re.escape(needle)}(\W|$)", text, re.MULTILINE):
                    return True
    return False


# Packages that are always considered used even if no `import` line references them
# (build-system or runtime deps invoked via CLI / entrypoints)
_ALWAYS_USED = {
    "pip",
    "setuptools",
    "wheel",
    "pytest",
    "pytest-asyncio",
    "pytest-cov",
    "ruff",
    "mypy",
    "vulture",
    "pipdeptree",
}


def _run_pipdeptree(repo: Path) -> tuple[ToolResult, list[Finding]]:
    """Detect packages declared in requirements*.txt but never imported.

    Uses pipdeptree primarily as a version-detection probe. The actual heuristic is
    a grep across `agents/services/shared/scripts/tests` for the package's import name.
    """
    binary = "pipdeptree" if shutil.which("pipdeptree") else (
        "pip-deptree" if shutil.which("pip-deptree") else None
    )
    if binary is None:
        return ToolResult(version="missing", exit_code=-1, errors=0), []

    requirements_map = _collect_requirements(repo)
    findings: list[Finding] = []

    for pkg, req_files in sorted(requirements_map.items()):
        if pkg in _ALWAYS_USED:
            continue
        if _grep_import_present(repo, pkg):
            continue
        # Could not find an import — likely unused (still a judgment call, queue it)
        req_file = sorted(req_files)[0]
        fid = f"deptree-unused-{_slugify(pkg)}"
        findings.append(
            Finding(
                id=fid,
                tool="pip-deptree",
                severity="info",
                rule_id="unused-dep",
                file=str(req_file),
                line=None,
                column=None,
                message=f"package '{pkg}' declared but no import found in agents/services/shared/scripts/tests",
                auto_fixable=False,
                confidence=60,
            )
        )

    return (
        ToolResult(version=_tool_version(binary), exit_code=0, errors=len(findings)),
        findings,
    )


# ---------------------------------------------------------------------------
# Codex sidecar enrichment
# ---------------------------------------------------------------------------


def _enrich_with_codex(report: Report, repo: Path) -> None:
    """For ambiguous findings (vulture, mypy unreachable), ask Codex.

    Codex's verdict overrides our heuristic confidence. If Codex says
    `used=true` we treat the finding as a false positive: drop confidence
    so night-coordinator discards it (< 60). If `used=false` and confidence
    high, bump our finding's confidence up so coordinator can auto-fix.
    """
    try:
        from shared.codex_sidecar import (  # type: ignore[import-not-found]
            CodeQualityFinding,
            analyze_finding,
        )
    except ImportError as exc:
        logger.warning("codex sidecar unavailable: %s", exc)
        return

    for finding in report.findings:
        if finding.tool != "vulture" and finding.rule_id != "unreachable":
            continue

        cq_finding = CodeQualityFinding(
            id=finding.id,
            tool=finding.tool,
            rule_id=finding.rule_id,
            severity=finding.severity,
            file=finding.file,
            line=finding.line,
            column=finding.column,
            message=finding.message,
            confidence=float(finding.confidence) if finding.confidence is not None else None,
        )
        try:
            verdict = analyze_finding(cq_finding, repo)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("codex_sidecar threw for %s: %s", finding.id, exc)
            continue

        # If Codex says the symbol IS used, this is a false-positive: drop confidence
        # below the queue threshold (60) so coordinator silently discards it.
        if verdict.used:
            finding.confidence = min(finding.confidence or 0, 30)
            finding.message = f"{finding.message} [codex: {verdict.evidence}]"
        else:
            # Codex says unused — surface its confidence as ours
            finding.confidence = verdict.confidence
            finding.message = f"{finding.message} [codex: {verdict.evidence}]"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_repo(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).resolve()
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            check=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()
    return Path(completed.stdout.strip())


def build_report(
    repo: Path,
    lint_paths: list[str],
    use_codex: bool,
) -> Report:
    """Run all tools and assemble a single Report object."""
    started = datetime.now(timezone.utc).isoformat()
    run_id = f"code-quality-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = Report(started_at=started, finished_at="", run_id=run_id)

    ruff_result, ruff_findings = _run_ruff(repo, lint_paths)
    report.tools["ruff"] = ruff_result
    report.findings.extend(ruff_findings)

    mypy_result, mypy_findings = _run_mypy(repo, lint_paths)
    report.tools["mypy"] = mypy_result
    report.findings.extend(mypy_findings)

    vulture_result, vulture_findings = _run_vulture(repo, lint_paths)
    report.tools["vulture"] = vulture_result
    report.findings.extend(vulture_findings)

    deptree_result, deptree_findings = _run_pipdeptree(repo)
    report.tools["pip-deptree"] = deptree_result
    report.findings.extend(deptree_findings)

    if use_codex:
        _enrich_with_codex(report, repo)

    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report


def _default_out(repo: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return repo / ".hygiene" / "reports" / f"code-quality-{today}.json"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="code-quality-scan")
    parser.add_argument("--repo", help="Repo root (default: git rev-parse --show-toplevel)")
    parser.add_argument("--out", help="Output JSON path (default: .hygiene/reports/code-quality-YYYYMMDD.json)")
    parser.add_argument("--paths", nargs="+", default=DEFAULT_LINT_PATHS, help="Paths to scan")
    parser.add_argument("--dry-run", action="store_true", help="Print report to stdout, don't write file")
    parser.add_argument("--no-codex", action="store_true", help="Skip Codex sidecar for ambiguous findings")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    repo = _resolve_repo(args.repo)
    if not repo.exists():
        print(f"ERROR: repo path does not exist: {repo}", file=sys.stderr)
        return 2

    out_path = Path(args.out).resolve() if args.out else _default_out(repo)
    out_dir = out_path.parent

    if not args.dry_run:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"ERROR: cannot create output directory {out_dir}: {exc}", file=sys.stderr)
            return 3

    report = build_report(repo=repo, lint_paths=args.paths, use_codex=not args.no_codex)
    payload = report.to_dict()

    if args.dry_run:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    try:
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write {out_path}: {exc}", file=sys.stderr)
        return 3

    print(
        f"code-quality-scan: wrote {len(report.findings)} findings to {out_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
