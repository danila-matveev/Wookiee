"""Smoke tests for scripts/nightly/test_coverage_check.py (Wave B4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.nightly import test_coverage_check as tcc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_load_baseline_missing(tmp_path: Path):
    assert tcc.load_baseline(tmp_path / "no-such-file.json") is None


def test_load_baseline_malformed(tmp_path: Path, caplog):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    assert tcc.load_baseline(path) is None


def test_load_baseline_null_value(tmp_path: Path):
    """Starter stub has percent_covered=null — should be treated as missing."""
    path = tmp_path / "stub.json"
    path.write_text(json.dumps({"percent_covered": None}))
    # null → float(None) raises TypeError → returns None
    assert tcc.load_baseline(path) is None


def test_save_and_reload_baseline(tmp_path: Path):
    path = tmp_path / "b.json"
    tcc.save_baseline(67.42, path)
    assert path.exists()
    assert tcc.load_baseline(path) == 67.42


def test_build_report_no_baseline_seeds_only(tmp_path: Path):
    """First-ever run: no baseline → no finding, blocking=False."""
    started = _now()
    report = tcc.build_report(
        current_pct=70.0,
        baseline_pct=None,
        started_at=started,
        finished_at=started,
        commit_sha="abc",
    )
    assert report.findings == []
    assert report.blocking is False
    assert report.delta_pct == 0.0


def test_build_report_unchanged(tmp_path: Path):
    started = _now()
    report = tcc.build_report(
        current_pct=67.0,
        baseline_pct=67.0,
        started_at=started,
        finished_at=started,
        commit_sha="abc",
    )
    assert report.findings == []
    assert report.blocking is False


def test_build_report_improvement(tmp_path: Path):
    started = _now()
    report = tcc.build_report(
        current_pct=70.0,
        baseline_pct=67.0,
        started_at=started,
        finished_at=started,
        commit_sha="abc",
    )
    assert report.findings == []
    assert report.blocking is False
    assert report.delta_pct == 3.0


def test_build_report_small_drop_not_blocking(tmp_path: Path):
    """Drop within threshold (≤2pp) → no blocking finding."""
    started = _now()
    report = tcc.build_report(
        current_pct=65.5,
        baseline_pct=67.0,  # delta -1.5pp, threshold 2.0
        started_at=started,
        finished_at=started,
        commit_sha="abc",
        drop_threshold_pp=2.0,
        min_pct=60.0,
    )
    assert report.blocking is False
    # Still above min_pct = 60, no finding
    assert report.findings == []


def test_build_report_big_drop_blocks(tmp_path: Path):
    """Drop > 2pp → blocking finding."""
    started = _now()
    report = tcc.build_report(
        current_pct=62.0,
        baseline_pct=67.0,  # delta -5pp
        started_at=started,
        finished_at=started,
        commit_sha="abc",
        drop_threshold_pp=2.0,
    )
    assert report.blocking is True
    assert len(report.findings) == 1
    f = report.findings[0]
    assert f.category == "coverage-drop"
    assert f.severity == "high"
    assert f.delta_pct == -5.0
    assert "62" in (f.rationale or "")


def test_build_report_below_floor_warning(tmp_path: Path):
    """Below min_pct but no big drop → finding without blocking."""
    started = _now()
    report = tcc.build_report(
        current_pct=55.0,
        baseline_pct=56.0,  # delta -1pp
        started_at=started,
        finished_at=started,
        commit_sha="abc",
        drop_threshold_pp=2.0,
        min_pct=60.0,
    )
    assert report.blocking is False
    assert len(report.findings) == 1
    assert report.findings[0].severity == "medium"


def test_write_report_creates_dated_file(tmp_path: Path):
    started = _now()
    report = tcc.build_report(
        current_pct=67.0,
        baseline_pct=67.0,
        started_at=started,
        finished_at=started,
        commit_sha="abc",
    )
    out_path = tcc.write_report(report, reports_dir=tmp_path)
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["current_pct"] == 67.0
    assert data["blocking"] is False
    # Filename uses date stamp
    assert out_path.name.startswith("coverage-")


def test_print_summary_runs(capsys, tmp_path: Path):
    started = _now()
    report = tcc.build_report(
        current_pct=67.0,
        baseline_pct=67.0,
        started_at=started,
        finished_at=started,
        commit_sha="abc",
    )
    out_path = tmp_path / "coverage.json"
    out_path.write_text("{}")
    tcc.print_summary(report, out_path)
    captured = capsys.readouterr()
    assert "[test-coverage-check]" in captured.out
    assert "OK" in captured.out
