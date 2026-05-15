"""Tests for `shared.hygiene.config`."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from pydantic import ValidationError

from shared.hygiene.config import HygieneConfig, is_read_only, load_config


def _write_yaml(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "config.yaml"
    target.write_text(dedent(body), encoding="utf-8")
    return target


def test_load_minimal_config_uses_safe_defaults(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, "version: 1\nread_only: true\n")
    config = load_config(path)
    assert isinstance(config, HygieneConfig)
    assert config.read_only is True
    assert config.coverage_min_pct == 60
    assert config.queue_expire_days == 7
    assert config.token_budgets.hygiene == 150_000
    assert config.pr.merge_method == "squash"


def test_load_full_config_parses_all_fields(tmp_path: Path) -> None:
    body = """
        version: 1
        read_only: false
        coverage_min_pct: 75
        codex_confidence_auto: 0.95
        codex_confidence_queue: 0.55
        queue_expire_days: 14
        reports_retention_days: 60
        heartbeat_enabled: false
        heartbeat_quiet_if_zero: false
        token_budgets:
          hygiene: 100000
          code_quality_scan: 200000
          test_coverage_check: 40000
          night_coordinator: 80000
          heartbeat: 10000
        telegram:
          chat_id_env: HYGIENE_TELEGRAM_CHAT_ID
          bot_token_env: TELEGRAM_ALERTS_BOT_TOKEN
        pr:
          base_branch: main
          branch_prefix: night-devops/
          auto_merge: true
          merge_method: squash
    """
    path = _write_yaml(tmp_path, body)
    config = load_config(path)
    assert config.read_only is False
    assert config.coverage_min_pct == 75
    assert config.codex_confidence_auto == pytest.approx(0.95)
    assert config.codex_confidence_queue == pytest.approx(0.55)
    assert config.queue_expire_days == 14
    assert config.reports_retention_days == 60
    assert config.heartbeat_enabled is False
    assert config.token_budgets.code_quality_scan == 200_000
    assert config.telegram is not None
    assert config.telegram.chat_id_env == "HYGIENE_TELEGRAM_CHAT_ID"


def test_missing_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_invalid_config_rejected(tmp_path: Path) -> None:
    # codex_confidence_auto must be in [0, 1]
    path = _write_yaml(tmp_path, "read_only: true\ncodex_confidence_auto: 5.0\n")
    with pytest.raises(ValidationError):
        load_config(path)


def test_extra_field_rejected(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, "read_only: true\nbogus_field: 42\n")
    with pytest.raises(ValidationError):
        load_config(path)


def test_is_read_only_reads_flag(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path, "read_only: true\n")
    config = load_config(path)
    assert is_read_only(config) is True

    path = _write_yaml(tmp_path, "read_only: false\n")
    config = load_config(path)
    assert is_read_only(config) is False


def test_empty_yaml_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    config = load_config(path)
    assert config.read_only is True  # default


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text(yaml.safe_dump([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)
