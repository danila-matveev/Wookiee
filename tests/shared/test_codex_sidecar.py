"""Tests for shared.codex_sidecar — Codex CLI wrapper.

Covers:
- happy path: codex returns JSONL with a verdict, sidecar parses it
- timeout: subprocess.TimeoutExpired -> fail-safe CodexAnalysis
- binary missing: returns "codex unavailable" verdict
- auth missing (CI scenario): returns "codex unavailable" verdict
- malformed JSON: returns "output unparseable" verdict
- non-zero exit: returns "codex exited <N>" verdict
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root on sys.path so `import shared.codex_sidecar` works
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.codex_sidecar import (  # noqa: E402
    CodeQualityFinding,
    CodexAnalysis,
    _parse_codex_output,
    analyze_finding,
)


@pytest.fixture
def finding() -> CodeQualityFinding:
    return CodeQualityFinding(
        id="vulture-dead-fn-services-old-aggregator-compute",
        tool="vulture",
        rule_id="unused-function",
        severity="warning",
        file="services/old_aggregator.py",
        line=88,
        column=None,
        message="unused function 'compute'",
        confidence=60.0,
    )


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    return tmp_path


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a fake subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(args=["codex"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_parse_codex_output_inline_json() -> None:
    """Codex returned a plain JSON blob (no JSONL wrapper)."""
    raw = 'some preamble\n{"used": false, "confidence": 92, "evidence": "no grep hits"}\n'
    verdict = _parse_codex_output(raw)
    assert verdict.used is False
    assert verdict.confidence == 92
    assert "no grep hits" in verdict.evidence


def test_parse_codex_output_jsonl_event() -> None:
    """Codex returned JSONL events; verdict embedded in the final agent_message."""
    payload = {
        "type": "agent_message",
        "content": '{"used": true, "confidence": 80, "evidence": "called via getattr in dispatcher.py"}',
    }
    raw = '{"type":"thinking","content":"..."}\n' + json.dumps(payload) + "\n"
    verdict = _parse_codex_output(raw)
    assert verdict.used is True
    assert verdict.confidence == 80


def test_parse_codex_output_malformed_raises() -> None:
    with pytest.raises(ValueError):
        _parse_codex_output("not json at all\nnot here either\n")


def test_analyze_finding_happy_path(finding: CodeQualityFinding, repo_path: Path) -> None:
    """Codex available, returns clean JSON — sidecar passes verdict through."""
    fake_stdout = '{"used": false, "confidence": 95, "evidence": "0 grep hits, no entrypoint"}'

    with (
        patch("shared.codex_sidecar._codex_available", return_value=True),
        patch("shared.codex_sidecar._find_codex_binary", return_value="/fake/codex"),
        patch("shared.codex_sidecar.subprocess.run", return_value=_completed(stdout=fake_stdout)) as run_mock,
    ):
        verdict = analyze_finding(finding, repo_path)

    assert verdict.used is False
    assert verdict.confidence == 95
    # Verify we called codex with shell=False and list-form args (security)
    call = run_mock.call_args
    cmd = call.args[0] if call.args else call.kwargs["args"]
    assert isinstance(cmd, list)
    assert cmd[0] == "/fake/codex"
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--sandbox" in cmd
    assert "read-only" in cmd
    assert call.kwargs["shell"] is False


def test_analyze_finding_timeout(finding: CodeQualityFinding, repo_path: Path) -> None:
    """Codex hung; we fail safe with confidence=0."""
    with (
        patch("shared.codex_sidecar._codex_available", return_value=True),
        patch("shared.codex_sidecar._find_codex_binary", return_value="/fake/codex"),
        patch(
            "shared.codex_sidecar.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=60),
        ),
    ):
        verdict = analyze_finding(finding, repo_path, timeout_seconds=60)

    assert isinstance(verdict, CodexAnalysis)
    assert verdict.used is True  # fail-safe: keep the symbol
    assert verdict.confidence == 0
    assert "timeout" in verdict.evidence.lower()


def test_analyze_finding_binary_missing(finding: CodeQualityFinding, repo_path: Path) -> None:
    """No codex binary on PATH — sidecar returns unavailable verdict, never calls subprocess."""
    with (
        patch("shared.codex_sidecar._find_codex_binary", return_value=None),
        patch("shared.codex_sidecar.subprocess.run") as run_mock,
    ):
        verdict = analyze_finding(finding, repo_path)

    assert verdict.used is True
    assert verdict.confidence == 0
    assert "unavailable" in verdict.evidence.lower()
    assert "not found" in verdict.evidence.lower()
    run_mock.assert_not_called()


def test_analyze_finding_auth_missing_in_ci(finding: CodeQualityFinding, repo_path: Path) -> None:
    """CI scenario: codex binary exists but ~/.codex/auth.json doesn't — fail safe."""
    with (
        patch("shared.codex_sidecar._find_codex_binary", return_value="/fake/codex"),
        patch("shared.codex_sidecar.CODEX_AUTH_PATH", Path("/nonexistent/.codex/auth.json")),
        patch("shared.codex_sidecar.subprocess.run") as run_mock,
    ):
        verdict = analyze_finding(finding, repo_path)

    assert verdict.used is True
    assert verdict.confidence == 0
    assert "auth" in verdict.evidence.lower() or "ci" in verdict.evidence.lower()
    run_mock.assert_not_called()


def test_analyze_finding_malformed_json(finding: CodeQualityFinding, repo_path: Path) -> None:
    """Codex returned text with no parseable verdict — fail safe."""
    with (
        patch("shared.codex_sidecar._codex_available", return_value=True),
        patch("shared.codex_sidecar._find_codex_binary", return_value="/fake/codex"),
        patch(
            "shared.codex_sidecar.subprocess.run",
            return_value=_completed(stdout="just some text, no JSON here"),
        ),
    ):
        verdict = analyze_finding(finding, repo_path)

    assert verdict.used is True
    assert verdict.confidence == 0
    assert "unparseable" in verdict.evidence.lower() or "json" in verdict.evidence.lower()


def test_analyze_finding_non_zero_exit(finding: CodeQualityFinding, repo_path: Path) -> None:
    """Codex auth expired or rate-limited: non-zero exit — fail safe."""
    with (
        patch("shared.codex_sidecar._codex_available", return_value=True),
        patch("shared.codex_sidecar._find_codex_binary", return_value="/fake/codex"),
        patch(
            "shared.codex_sidecar.subprocess.run",
            return_value=_completed(stdout="", stderr="auth token expired", returncode=2),
        ),
    ):
        verdict = analyze_finding(finding, repo_path)

    assert verdict.used is True
    assert verdict.confidence == 0
    assert "exited" in verdict.evidence.lower() or "2" in verdict.evidence
