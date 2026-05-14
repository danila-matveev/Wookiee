"""Runner for the /test-coverage-check skill (Wave B4).

Runs pytest under coverage.py with the same ignore/deselect list as CI,
compares the result to .hygiene/coverage-baseline.json, writes a daily
report to .hygiene/reports/coverage-YYYY-MM-DD.json.

Behavior:
- First-ever run with no baseline → seeds baseline, no finding.
- Drop > drop_threshold_pp (default 2.0) → blocking finding,
  night-coordinator MUST NOT auto-merge.
- Improvement → updates baseline.
- Equal (within 0.05 pp) → just writes a no-finding report.

CLI: python -m scripts.nightly.test_coverage_check
     python scripts/nightly/test_coverage_check.py
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from shared.hygiene.schemas import CoverageReport, Finding

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_DIR = REPO_ROOT / ".hygiene"
BASELINE_PATH = HYGIENE_DIR / "coverage-baseline.json"
REPORTS_DIR = HYGIENE_DIR / "reports"

# Mirror of .github/workflows/ci.yml --ignore + --deselect args.
# Keep this list synchronized: if CI changes, this changes too.
CI_IGNORES = [
    "tests/product_matrix_api",
    "tests/services/influencer_crm",
    "tests/services/telemost_recorder",
    "tests/services/telemost_recorder_api",
    "tests/scripts/test_telemost_setup_webhook.py",
    "tests/wb_localization/test_cabinet_filter.py",
]
CI_DESELECTS = [
    "tests/services/logistics_audit/test_excel_sheets.py::test_generate_full_workbook",
    "tests/services/logistics_audit/test_models.py::test_audit_config",
    "tests/services/logistics_audit/test_tariff_etl.py::test_load_historical_tariff_rows_maps_defaults_and_counts",
    "tests/test_market_review_collectors.py::TestTopModelsOurs::test_returns_note_when_no_skus",
    "tests/test_market_review_collectors.py::TestTopModelsRivals::test_returns_note_when_no_skus",
    "tests/test_reviews_audit_collector.py::TestCollectDataV2::test_output_structure_v2",
    "tests/services/analytics_api/test_marketing_sync.py::test_trigger_sync_without_api_key_returns_401",
    "tests/services/analytics_api/test_marketing_sync.py::test_trigger_sync_with_wrong_api_key_returns_401",
]

DEFAULT_DROP_THRESHOLD_PP = 2.0
DEFAULT_MIN_COVERAGE_PCT = 60.0


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a subprocess; capture output but don't raise on non-zero (coverage may exit 1)."""
    logger.debug("running: %s (cwd=%s)", " ".join(cmd), cwd)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def run_coverage(repo_root: Path = REPO_ROOT) -> float:
    """Run coverage + pytest with CI ignores, return percent_covered.

    Returns:
        float: percent (0.0–100.0). May be 0 if all tests failed.

    Raises:
        RuntimeError: if coverage tooling itself fails (no JSON written).
    """
    # 1. coverage run -m pytest ...
    pytest_args: list[str] = ["coverage", "run", "-m", "pytest", "-q", "tests"]
    for ignore in CI_IGNORES:
        pytest_args.extend(["--ignore", ignore])
    for deselect in CI_DESELECTS:
        pytest_args.extend(["--deselect", deselect])

    result = _run(pytest_args, cwd=repo_root)
    # We tolerate non-zero exit from pytest (some tests may fail), but not
    # tooling errors like "coverage: command not found".
    if "command not found" in (result.stderr or "").lower() or result.returncode == 127:
        raise RuntimeError(f"coverage tooling missing: {result.stderr[:200]}")

    # 2. coverage json -o /tmp/coverage.json
    json_path = repo_root / "coverage.json"
    if json_path.exists():
        json_path.unlink()
    json_result = _run(["coverage", "json", "-o", str(json_path)], cwd=repo_root)
    if not json_path.exists():
        raise RuntimeError(
            f"coverage json failed: stdout={json_result.stdout[:200]} stderr={json_result.stderr[:200]}"
        )

    data = json.loads(json_path.read_text())
    pct = float(data.get("totals", {}).get("percent_covered", 0.0))
    return pct


def load_baseline(path: Path = BASELINE_PATH) -> float | None:
    """Return baseline percent or None if no baseline yet."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return float(data.get("percent_covered"))
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("baseline at %s unreadable (%s) — treating as missing", path, e)
        return None


def save_baseline(pct: float, path: Path = BASELINE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "percent_covered": round(pct, 2),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _commit_sha(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build_report(
    current_pct: float,
    baseline_pct: float | None,
    *,
    started_at: datetime,
    finished_at: datetime,
    commit_sha: str,
    drop_threshold_pp: float = DEFAULT_DROP_THRESHOLD_PP,
    min_pct: float = DEFAULT_MIN_COVERAGE_PCT,
) -> CoverageReport:
    """Build the CoverageReport pydantic object."""
    effective_baseline = baseline_pct if baseline_pct is not None else current_pct
    delta = current_pct - effective_baseline

    findings: list[Finding] = []
    blocking = False

    if baseline_pct is None:
        # First run: seed only, no finding.
        pass
    elif delta < -drop_threshold_pp:
        blocking = True
        findings.append(
            Finding(
                id=f"coverage-drop-{finished_at.strftime('%Y%m%d')}",
                category="coverage-drop",
                severity="high",
                safe_to_autofix=False,
                rationale=(
                    f"Покрытие тестами упало с {baseline_pct:.1f}% до {current_pct:.1f}% "
                    f"({delta:+.1f} п.п., порог {drop_threshold_pp:.1f} п.п.)."
                ),
                current_pct=round(current_pct, 2),
                baseline_pct=round(baseline_pct, 2),
                delta_pct=round(delta, 2),
            )
        )
    elif current_pct < min_pct:
        # Not a drop, but below the absolute floor.
        findings.append(
            Finding(
                id=f"coverage-below-floor-{finished_at.strftime('%Y%m%d')}",
                category="coverage-drop",
                severity="medium",
                safe_to_autofix=False,
                rationale=(
                    f"Покрытие {current_pct:.1f}% ниже минимума {min_pct:.0f}% "
                    "(не блокирует мердж, но стоит подтянуть)."
                ),
                current_pct=round(current_pct, 2),
                baseline_pct=round(baseline_pct, 2),
                delta_pct=round(delta, 2),
            )
        )

    summary = {
        "current_pct": round(current_pct, 2),
        "baseline_pct": round(baseline_pct, 2) if baseline_pct is not None else None,
        "delta_pp": round(delta, 2),
        "blocking": blocking,
        "min_pct": min_pct,
        "drop_threshold_pp": drop_threshold_pp,
    }

    report = CoverageReport(
        run_id=f"coverage-{finished_at.strftime('%Y-%m-%dT%H%M-utc')}",
        started_at=started_at,
        finished_at=finished_at,
        commit_sha=commit_sha,
        current_pct=round(current_pct, 2),
        baseline_pct=round(baseline_pct, 2) if baseline_pct is not None else round(current_pct, 2),
        delta_pct=round(delta, 2),
        threshold_pct=min_pct,
        drop_threshold_pp=drop_threshold_pp,
        findings=findings,
        blocking=blocking,
        summary=summary,
    )
    return report


def write_report(report: CoverageReport, reports_dir: Path = REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    date_str = report.finished_at.strftime("%Y-%m-%d")
    out_path = reports_dir / f"coverage-{date_str}.json"
    out_path.write_text(report.model_dump_json(indent=2) + "\n")
    return out_path


def print_summary(report: CoverageReport, report_path: Path) -> None:
    """Tee a short summary to stdout for the GH Action log."""
    if report.blocking:
        marker = "BLOCKING"
    elif report.findings:
        marker = "WARN"
    else:
        marker = "OK"
    print(
        f"[test-coverage-check] {marker} "
        f"current={report.current_pct:.1f}% "
        f"baseline={report.baseline_pct:.1f}% "
        f"delta={report.delta_pct:+.1f}pp "
        f"findings={len(report.findings)} "
        f"report={report_path}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drop-threshold-pp", type=float, default=DEFAULT_DROP_THRESHOLD_PP)
    parser.add_argument("--min-pct", type=float, default=DEFAULT_MIN_COVERAGE_PCT)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    started = datetime.now(timezone.utc)

    try:
        current_pct = run_coverage(args.repo_root)
    except RuntimeError as e:
        logger.error("coverage run failed: %s", e)
        # Emit a truncated report so coordinator knows we ran but failed
        finished = datetime.now(timezone.utc)
        empty_report = CoverageReport(
            run_id=f"coverage-{finished.strftime('%Y-%m-%dT%H%M-utc')}",
            started_at=started,
            finished_at=finished,
            commit_sha=_commit_sha(args.repo_root),
            current_pct=0.0,
            baseline_pct=0.0,
            delta_pct=0.0,
            threshold_pct=args.min_pct,
            drop_threshold_pp=args.drop_threshold_pp,
            blocking=True,
            truncated=True,
            summary={"error": str(e)},
        )
        path = write_report(empty_report)
        print_summary(empty_report, path)
        return 1

    baseline_pct = load_baseline()
    finished = datetime.now(timezone.utc)

    report = build_report(
        current_pct,
        baseline_pct,
        started_at=started,
        finished_at=finished,
        commit_sha=_commit_sha(args.repo_root),
        drop_threshold_pp=args.drop_threshold_pp,
        min_pct=args.min_pct,
    )

    report_path = write_report(report)
    print_summary(report, report_path)

    # Update baseline if improved (or seed if missing).
    if baseline_pct is None:
        save_baseline(current_pct)
        logger.info("seeded baseline at %.2f%%", current_pct)
    elif current_pct > baseline_pct:
        save_baseline(current_pct)
        logger.info("baseline raised: %.2f%% → %.2f%%", baseline_pct, current_pct)

    return 1 if report.blocking else 0


if __name__ == "__main__":
    sys.exit(main())
