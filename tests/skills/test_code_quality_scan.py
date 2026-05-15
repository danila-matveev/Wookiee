"""Smoke tests for the code-quality-scan runner.

Verifies that:
- runner produces a valid JSON report
- report shape matches plan §3.2 (top-level keys + finding shape)
- runner gracefully handles missing tools (e.g. mypy not installed)
- --dry-run writes nothing to disk
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = PROJECT_ROOT / ".claude" / "skills" / "code-quality-scan" / "runner.py"


def _load_runner_module():
    """Import the runner.py file directly (it's outside of any installable package).

    Register in sys.modules BEFORE exec so dataclasses can resolve forward
    references — without this Python 3.11+ raises 'NoneType has no attribute
    __dict__' when introspecting dataclass annotations from a module loaded
    out-of-band.
    """
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    mod_name = "code_quality_runner"
    spec = importlib.util.spec_from_file_location(mod_name, RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_runner_module()


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Build a minimal repo skeleton the runner can scan."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "__init__.py").write_text("")
    (tmp_path / "shared" / "sample.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "__init__.py").write_text("")
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "__init__.py").write_text("")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "requirements.txt").write_text("pyyaml\npytest\n")
    return tmp_path


def test_runner_file_exists() -> None:
    assert RUNNER_PATH.is_file(), f"runner not found at {RUNNER_PATH}"


def test_build_report_shape(runner, fake_repo: Path) -> None:
    """The report must have the keys downstream coordinators expect."""
    report = runner.build_report(
        repo=fake_repo,
        lint_paths=["agents", "services", "shared", "scripts"],
        use_codex=False,
    )
    payload = report.to_dict()

    # Top-level required keys (plan §3.2)
    for key in ("$schema", "version", "run_id", "started_at", "finished_at", "tools", "findings", "summary"):
        assert key in payload, f"missing top-level key: {key}"

    # All four tools should appear, even if missing on this machine
    for tool in ("ruff", "mypy", "vulture", "pip-deptree"):
        assert tool in payload["tools"], f"missing tool entry: {tool}"
        entry = payload["tools"][tool]
        for sub in ("version", "exit_code", "errors"):
            assert sub in entry, f"tool {tool} missing field {sub}"

    # Findings is always a list
    assert isinstance(payload["findings"], list)

    # Summary aggregates
    summary = payload["summary"]
    assert summary["total"] == len(payload["findings"])
    assert summary["auto_fixable"] + summary["needs_human"] == summary["total"]


def test_finding_shape(runner, fake_repo: Path) -> None:
    """If any finding is produced, it must match the canonical schema."""
    # Drop a file that ruff will flag (unused import) to force at least one finding
    (fake_repo / "shared" / "bad.py").write_text(
        "import os  # F401 unused\n"
        "def f():\n    pass\n"
    )
    report = runner.build_report(
        repo=fake_repo,
        lint_paths=["shared"],
        use_codex=False,
    )
    payload = report.to_dict()

    if not payload["findings"]:
        # ruff may not be installed in this test env — that's OK, just skip
        pytest.skip("no tools available to produce findings on this runner")

    finding = payload["findings"][0]
    required_keys = {
        "id",
        "tool",
        "severity",
        "rule_id",
        "file",
        "line",
        "column",
        "message",
        "auto_fixable",
        "confidence",
    }
    assert required_keys.issubset(finding.keys()), (
        f"finding missing keys: {required_keys - finding.keys()}"
    )
    assert finding["tool"] in {"ruff", "mypy", "vulture", "pip-deptree"}
    assert finding["severity"] in {"error", "warning", "info"}
    assert isinstance(finding["auto_fixable"], bool)
    if finding["confidence"] is not None:
        assert 0 <= finding["confidence"] <= 100


def test_dry_run_writes_nothing(runner, fake_repo: Path, capsys, monkeypatch) -> None:
    """--dry-run should print JSON to stdout and not write any file."""
    out = fake_repo / ".hygiene" / "reports" / "code-quality.json"
    assert not out.exists()

    monkeypatch.chdir(fake_repo)
    rc = runner.main(
        ["--repo", str(fake_repo), "--out", str(out), "--dry-run", "--no-codex"]
    )
    assert rc == 0
    assert not out.exists(), "dry-run must not write the report file"

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "findings" in payload
    assert "tools" in payload


def test_writes_json_file(runner, fake_repo: Path, monkeypatch) -> None:
    """Without --dry-run, a valid JSON file should appear on disk."""
    out = fake_repo / ".hygiene" / "reports" / "code-quality.json"
    monkeypatch.chdir(fake_repo)

    rc = runner.main(
        ["--repo", str(fake_repo), "--out", str(out), "--no-codex"]
    )
    assert rc == 0
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["version"] == "1.0.0"
    assert isinstance(payload["findings"], list)


def test_missing_repo_path(runner, tmp_path: Path) -> None:
    """If --repo points to nothing, exit cleanly with code 2."""
    rc = runner.main(["--repo", str(tmp_path / "does-not-exist"), "--no-codex", "--dry-run"])
    assert rc == 2


def test_missing_tool_does_not_crash(runner, fake_repo: Path, monkeypatch) -> None:
    """If a wrapped tool is missing, the runner records exit_code=-1 and continues."""
    # Force `shutil.which` to return None for vulture only — runner should still finish
    original_which = shutil.which

    def fake_which(name: str, *a, **kw):
        if name in ("vulture", "mypy"):
            return None
        return original_which(name, *a, **kw)

    monkeypatch.setattr(runner.shutil, "which", fake_which)
    report = runner.build_report(repo=fake_repo, lint_paths=["shared"], use_codex=False)
    payload = report.to_dict()
    assert payload["tools"]["vulture"]["version"] == "missing"
    assert payload["tools"]["mypy"]["version"] == "missing"
    assert payload["tools"]["vulture"]["exit_code"] == -1
