"""Codex CLI sidecar — wrapper around local `codex exec` for ambiguous-case analysis.

Used by `/code-quality-scan` to verify findings (e.g. vulture dead-code candidates)
that need a judgment call. Calls the local Codex CLI in non-interactive JSON mode.

Authentication: OAuth via `~/.codex/auth.json` (chatgpt subscription, NOT OPENAI_API_KEY).
See `feedback_subscription_over_api.md`.

Reference: Wave B3 of `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md`.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Defaults derived from the plan §12.
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_TOKENS = 5000
CODEX_AUTH_PATH = Path.home() / ".codex" / "auth.json"


class CodeQualityFinding(BaseModel):
    """Minimal shape of a finding passed to the Codex sidecar."""

    id: str
    tool: str  # ruff | mypy | vulture | pip-deptree
    rule_id: Optional[str] = None
    severity: str  # error | warning | info
    file: str
    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    confidence: Optional[float] = None  # 0–100, used by vulture especially


class CodexAnalysis(BaseModel):
    """Result of asking Codex to verify a finding.

    `used`         — true means the function/symbol IS used somewhere
                     (so the finding is a false-positive, do NOT delete).
    `confidence`   — 0..100, Codex's own confidence in the verdict.
    `evidence`     — short rationale: where it found a reference, or why it's unsure.
    """

    used: bool
    confidence: int = Field(ge=0, le=100)
    evidence: str


def _find_codex_binary() -> Optional[str]:
    """Locate the `codex` binary. Returns absolute path or None if missing."""
    # Common npm-global install path on darwin / linux
    candidate = Path.home() / ".npm-global" / "bin" / "codex"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    # Fallback to PATH lookup
    return shutil.which("codex")


def _codex_available() -> bool:
    """Check that codex CLI and OAuth auth are both present.

    In CI (GH Actions) the runner has neither — we fail safe by returning False
    and letting the caller emit a conservative `used=True, confidence=0` verdict.
    """
    if _find_codex_binary() is None:
        return False
    if not CODEX_AUTH_PATH.is_file():
        return False
    return True


def _build_prompt(finding: CodeQualityFinding, repo_path: Path) -> str:
    """Build a focused prompt asking Codex to verify the finding.

    The prompt asks ONE narrow question and demands a JSON-only response so we
    can parse it deterministically. We do NOT hand Codex the whole repo — it has
    sandbox read access via `--cd` and can grep on its own if it needs to.
    """
    location = f"{finding.file}"
    if finding.line is not None:
        location += f":{finding.line}"

    return (
        "You are a code reviewer verifying a static-analysis finding. Answer ONLY with "
        "one JSON object on the LAST line of your response, with this exact shape:\n"
        '  {"used": bool, "confidence": int, "evidence": str}\n\n'
        "Where:\n"
        "- used: true if the symbol IS referenced anywhere in the repo, including "
        "dynamic imports, getattr, importlib, config strings, entrypoints, decorators, "
        "or runtime paths. false ONLY if you are confident it is genuinely unused.\n"
        "- confidence: 0–100, your confidence in the verdict.\n"
        "- evidence: one short sentence with the strongest signal "
        "(e.g. 'referenced via getattr in services/dispatcher.py:88' or "
        "'no grep hits, no dynamic dispatch, no entrypoint registration').\n\n"
        f"Finding:\n"
        f"- tool: {finding.tool}\n"
        f"- rule_id: {finding.rule_id or 'n/a'}\n"
        f"- location: {location}\n"
        f"- message: {finding.message}\n\n"
        f"Repo root: {repo_path}\n"
        "Use grep / file reads in the repo to verify before answering. Return JSON only."
    )


def _parse_codex_output(stdout: str) -> CodexAnalysis:
    """Extract the JSON verdict from Codex stdout.

    Codex `--json` emits JSONL events. We scan from the end for the first line
    that parses as our expected verdict shape. Falls back to plain-text parsing
    if Codex was invoked without `--json` (looks for a `{...}` block).
    """
    candidate_blobs: list[str] = []

    # Try JSONL events first
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Codex JSONL events wrap content in various keys; we try to find the
        # final agent message.
        if isinstance(event, dict):
            for key in ("msg", "message", "content", "text", "final_message"):
                value = event.get(key)
                if isinstance(value, str):
                    candidate_blobs.append(value)
            if event.get("type") in ("agent_message", "final_message", "assistant"):
                content = event.get("content") or event.get("text")
                if isinstance(content, str):
                    candidate_blobs.append(content)
        # Also try parsing the event itself as the verdict
        if isinstance(event, dict) and "used" in event and "confidence" in event:
            return CodexAnalysis.model_validate(event)

    # Fallback: scan the raw stdout for a JSON object that looks like a verdict
    candidate_blobs.append(stdout)

    for blob in candidate_blobs:
        start = blob.rfind("{")
        end = blob.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue
        snippet = blob[start : end + 1]
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "used" in parsed and "confidence" in parsed:
            return CodexAnalysis.model_validate(parsed)

    raise ValueError("Could not find a JSON verdict in codex output")


def analyze_finding(
    finding: CodeQualityFinding,
    repo_path: Path,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> CodexAnalysis:
    """Ask Codex to verify a static-analysis finding.

    Returns a `CodexAnalysis` with verdict + confidence + evidence.

    Fail-safe semantics: any error (codex missing, timeout, malformed JSON, auth
    expired in CI) returns `used=True, confidence=0, evidence="<reason>"`. This
    keeps the file in place — we never delete code based on an unavailable arbiter.
    """
    if not _codex_available():
        binary = _find_codex_binary()
        if binary is None:
            reason = "codex binary not found"
        else:
            reason = "codex auth.json missing (likely CI environment)"
        logger.info("codex_sidecar: unavailable — %s", reason)
        return CodexAnalysis(used=True, confidence=0, evidence=f"codex unavailable: {reason}")

    binary = _find_codex_binary()
    assert binary is not None  # narrowed by _codex_available()

    prompt = _build_prompt(finding, repo_path)

    # Token cap is enforced via -c overrides. Keys mirror Codex `config.toml`.
    # We pin to read-only sandbox so Codex cannot mutate the repo while answering.
    cmd: list[str] = [
        binary,
        "exec",
        "--json",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--cd",
        str(repo_path),
        "-c",
        f"model_context_window={max_tokens}",
        "-c",
        f"model_max_output_tokens={max_tokens}",
        prompt,
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "codex_sidecar: timeout after %ss for finding %s", timeout_seconds, finding.id
        )
        return CodexAnalysis(
            used=True,
            confidence=0,
            evidence=f"codex timeout after {timeout_seconds}s",
        )
    except FileNotFoundError:
        logger.warning("codex_sidecar: codex binary disappeared mid-run")
        return CodexAnalysis(used=True, confidence=0, evidence="codex binary not found")

    if completed.returncode != 0:
        # Auth expired, rate-limited, etc. Fail safe.
        stderr_snippet = (completed.stderr or "").strip().splitlines()[-1:] or ["no stderr"]
        logger.warning(
            "codex_sidecar: non-zero exit %s for finding %s: %s",
            completed.returncode,
            finding.id,
            stderr_snippet[0][:200],
        )
        return CodexAnalysis(
            used=True,
            confidence=0,
            evidence=f"codex exited {completed.returncode}: {stderr_snippet[0][:120]}",
        )

    try:
        return _parse_codex_output(completed.stdout or "")
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("codex_sidecar: malformed output for finding %s: %s", finding.id, exc)
        return CodexAnalysis(
            used=True,
            confidence=0,
            evidence=f"codex output unparseable: {str(exc)[:120]}",
        )
