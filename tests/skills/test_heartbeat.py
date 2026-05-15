"""Smoke tests for scripts/nightly/heartbeat.py (Wave B4)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.nightly import heartbeat as hb
from shared.hygiene.schemas import HeartbeatSummary
from shared.telegram_digest import MAX_HEARTBEAT_LEN, render_heartbeat


def _seed(reports_dir: Path, today: date, hygiene_data=None, cq_data=None, cov_data=None, coord_data=None):
    """Write today's report JSONs into reports_dir."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    ds = today.strftime("%Y-%m-%d")
    if hygiene_data is not None:
        (reports_dir / f"hygiene-{ds}.json").write_text(json.dumps(hygiene_data))
    if cq_data is not None:
        (reports_dir / f"code-quality-{ds}.json").write_text(json.dumps(cq_data))
    if cov_data is not None:
        (reports_dir / f"coverage-{ds}.json").write_text(json.dumps(cov_data))
    if coord_data is not None:
        (reports_dir / f"coordinator-{ds}.json").write_text(json.dumps(coord_data))


def test_build_summary_empty(tmp_path: Path):
    today = date(2026, 5, 14)
    reports = hb._today_reports(tmp_path, today)
    summary = hb.build_summary(reports=reports, today=today)
    assert summary.date_str == "14 мая"
    assert summary.fixes_applied == 0
    assert summary.needs_human_count == 0
    assert summary.coverage_pct is None
    assert summary.pr_number is None
    assert summary.failure is None


def test_build_summary_with_fixes_via_hygiene_findings(tmp_path: Path):
    today = date(2026, 5, 14)
    _seed(
        tmp_path,
        today,
        hygiene_data={
            "version": "1.0.0",
            "run_id": "h",
            "findings": [
                {"id": "1", "category": "orphan-imports", "severity": "low", "safe_to_autofix": True},
                {"id": "2", "category": "broken-doc-links", "severity": "low", "safe_to_autofix": True},
                {"id": "3", "category": "orphan-docs", "severity": "low", "safe_to_autofix": False},
            ],
            "summary": {"needs_human": 1},
        },
    )
    reports = hb._today_reports(tmp_path, today)
    summary = hb.build_summary(reports=reports, today=today)
    assert summary.fixes_applied == 2
    assert summary.needs_human_count == 1
    assert any("импорт" in ex.lower() for ex in summary.fixes_examples)


def test_build_summary_with_coordinator_overrides(tmp_path: Path):
    today = date(2026, 5, 14)
    _seed(
        tmp_path,
        today,
        coord_data={
            "fixes_applied": [
                {"ru_label": "битая ссылка"},
                {"ru_label": "лишний импорт"},
                {"ru_label": "drift зеркала"},
            ],
            "pr": {"number": 234, "status": "merged"},
        },
    )
    reports = hb._today_reports(tmp_path, today)
    summary = hb.build_summary(reports=reports, today=today)
    assert summary.fixes_applied == 3
    assert summary.fixes_examples == ["битая ссылка", "лишний импорт", "drift зеркала"]
    assert summary.pr_number == 234
    assert summary.pr_status == "merged"


def test_build_summary_coverage(tmp_path: Path):
    today = date(2026, 5, 14)
    _seed(
        tmp_path,
        today,
        cov_data={"current_pct": 67.0, "delta_pct": -1.5, "blocking": False},
    )
    reports = hb._today_reports(tmp_path, today)
    summary = hb.build_summary(reports=reports, today=today)
    assert summary.coverage_pct == 67.0
    assert summary.coverage_delta_pp == -1.5


def test_should_be_quiet_when_zero_activity():
    summary = HeartbeatSummary(date_str="14 мая")
    assert hb.should_be_quiet(summary, config={"heartbeat_quiet_if_zero": True}) is True


def test_should_be_quiet_disabled_by_config():
    summary = HeartbeatSummary(date_str="14 мая")
    assert hb.should_be_quiet(summary, config={"heartbeat_quiet_if_zero": False}) is False


def test_should_be_quiet_not_when_fixes_applied():
    summary = HeartbeatSummary(date_str="14 мая", fixes_applied=1)
    assert hb.should_be_quiet(summary, config={"heartbeat_quiet_if_zero": True}) is False


def test_should_be_quiet_not_when_failure():
    summary = HeartbeatSummary(date_str="14 мая", failure="что-то сломалось")
    assert hb.should_be_quiet(summary, config={"heartbeat_quiet_if_zero": True}) is False


def test_is_enabled_default_true():
    assert hb.is_enabled(config={}) is True
    assert hb.is_enabled(config={"heartbeat_enabled": True}) is True
    assert hb.is_enabled(config={"heartbeat_enabled": False}) is False


def test_render_via_main_path_respects_length_cap(tmp_path: Path):
    """Even with many examples, the rendered heartbeat fits the cap."""
    summary = HeartbeatSummary(
        date_str="14 мая",
        fixes_applied=42,
        fixes_examples=["битая ссылка", "лишний импорт", "drift зеркала", "ещё одна штука"],
        needs_human_count=3,
        coverage_pct=67.0,
        coverage_delta_pp=-1.5,
        pr_number=234,
        pr_status="open",
    )
    text = render_heartbeat(summary)
    assert len(text) <= MAX_HEARTBEAT_LEN
    # Sanity: still contains the key things
    assert "14 мая" in text
    assert "/hygiene-resolve" in text


def test_main_dry_run_does_not_send(monkeypatch, tmp_path: Path):
    """--dry-run should print but never call send_digest."""
    today = date.today()
    _seed(
        tmp_path,
        today,
        hygiene_data={
            "findings": [{"id": "1", "category": "orphan-imports", "severity": "low", "safe_to_autofix": True}],
            "summary": {"needs_human": 0},
        },
    )

    called: list[str] = []

    def boom(*args, **kwargs):
        called.append("send")
        raise AssertionError("send_digest must not be called in dry-run")

    monkeypatch.setattr("scripts.nightly.heartbeat.send_digest", boom)

    # Empty config → defaults (enabled, quiet_if_zero), but we have a fix, so it won't be quiet
    config_path = tmp_path / "config.yaml"
    config_path.write_text("heartbeat_enabled: true\nheartbeat_quiet_if_zero: true\n")

    rc = hb.main(["--dry-run", "--reports-dir", str(tmp_path), "--config", str(config_path)])
    assert rc == 0
    assert called == []


def test_main_disabled_via_config(tmp_path: Path, capsys):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("heartbeat_enabled: false\n")
    rc = hb.main(["--reports-dir", str(tmp_path), "--config", str(config_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "disabled" in out
