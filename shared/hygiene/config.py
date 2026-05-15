"""Load `.hygiene/config.yaml` for the nighttime DevOps agent.

Single source of truth for runtime configuration: the master `read_only`
kill-switch, thresholds (coverage, Codex confidence), retention windows, token
budgets, and Telegram routing.

The module is intentionally tiny: parse → validate → expose a Pydantic model.
No I/O is hidden behind getters; callers always know they read the YAML file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field


# Default file location relative to the repo root.
DEFAULT_CONFIG_PATH = Path(".hygiene/config.yaml")


class TokenBudgets(BaseModel):
    """Hard-cap token budgets per skill. Exceeding a cap → fail + Telegram alert."""

    model_config = ConfigDict(extra="forbid")

    hygiene: int = 150_000
    code_quality_scan: int = 250_000
    test_coverage_check: int = 50_000
    night_coordinator: int = 100_000
    heartbeat: int = 20_000


class TelegramRoute(BaseModel):
    """Env-var names that resolve to bot token + chat id at runtime."""

    model_config = ConfigDict(extra="forbid")

    chat_id_env: str
    bot_token_env: str


class PRSettings(BaseModel):
    """Pull-request creation parameters for `/night-coordinator`."""

    model_config = ConfigDict(extra="forbid")

    base_branch: str = "main"
    branch_prefix: str = "night-devops/"
    auto_merge: bool = True
    merge_method: str = "squash"


class HygieneConfig(BaseModel):
    """Top-level model for `.hygiene/config.yaml`."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    read_only: bool = Field(
        default=True,
        description="Master kill-switch. true = no PRs, just JSON + Telegram digest.",
    )

    coverage_min_pct: int = 60
    codex_confidence_auto: float = Field(default=0.90, ge=0.0, le=1.0)
    codex_confidence_queue: float = Field(default=0.60, ge=0.0, le=1.0)

    queue_expire_days: int = 7
    reports_retention_days: int = 30

    heartbeat_enabled: bool = True
    heartbeat_quiet_if_zero: bool = True

    token_budgets: TokenBudgets = Field(default_factory=TokenBudgets)
    telegram: Optional[TelegramRoute] = None
    pr: PRSettings = Field(default_factory=PRSettings)


def load_config(path: Optional[Path] = None) -> HygieneConfig:
    """Parse `.hygiene/config.yaml` into a validated `HygieneConfig`.

    Args:
        path: Optional explicit path. Defaults to `.hygiene/config.yaml`
              relative to the current working directory.

    Returns:
        Validated `HygieneConfig`. Raises `FileNotFoundError` if the file is
        missing and `pydantic.ValidationError` if it's malformed.
    """
    target = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not target.is_file():
        raise FileNotFoundError(
            f"Hygiene config not found at {target}. "
            "Create .hygiene/config.yaml — see docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md §3.5."
        )
    raw: Any = yaml.safe_load(target.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"Hygiene config at {target} must be a YAML mapping at the top level"
        )
    return HygieneConfig.model_validate(raw)


def is_read_only(config: Optional[HygieneConfig] = None) -> bool:
    """Convenience: returns the master kill-switch value.

    Equivalent to `load_config().read_only`. Pass an already-loaded config to
    avoid re-reading the file on hot paths.
    """
    if config is None:
        config = load_config()
    return config.read_only
