"""Load config from environment / .env for logistics audit."""
from __future__ import annotations
import json
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from services.logistics_audit.models.audit_config import AuditConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

IL_OVERRIDES_PATH = Path(__file__).parent / "il_overrides.json"


def load_il_overrides(path: Path | None = None) -> dict[str, float]:
    """Load IL overrides from JSON. Returns {date_str: il_value}."""
    p = path or IL_OVERRIDES_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, ValueError):
        return {}


def load_config(
    cabinet: str = "OOO",
    date_from: str | None = None,
    date_to: str | None = None,
    ktr: float = 1.0,
) -> AuditConfig:
    api_key = os.getenv(f"WB_API_KEY_{cabinet.upper()}")
    if not api_key:
        raise ValueError(f"Missing WB_API_KEY_{cabinet.upper()} in .env")
    return AuditConfig(
        api_key=api_key,
        date_from=date.fromisoformat(date_from) if date_from else date.today(),
        date_to=date.fromisoformat(date_to) if date_to else date.today(),
        ktr=ktr,
    )
