"""
PlaybookLoader — assembles core + template + rules per task_type.

Usage:
    from agents.oleg.playbooks.loader import load as load_playbook
    prompt = load_playbook("weekly")  # returns: core + weekly template + rules
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PLAYBOOKS_DIR = Path(__file__).parent

TEMPLATE_MAP = {
    "daily": "daily.md",
    "weekly": "weekly.md",
    "monthly": "monthly.md",
    "marketing_weekly": "marketing_weekly.md",
    "marketing_monthly": "marketing_monthly.md",
    "funnel_weekly": "funnel_weekly.md",
    "dds": "dds.md",
    "localization": "localization.md",
    "custom": "weekly.md",  # fallback: custom maps to weekly depth
}


def load(task_type: str) -> str:
    """Assemble core + template + rules for given task_type."""
    core = (_PLAYBOOKS_DIR / "core.md").read_text(encoding="utf-8")
    template_name = TEMPLATE_MAP.get(task_type, "weekly.md")
    template = (_PLAYBOOKS_DIR / "templates" / template_name).read_text(encoding="utf-8")
    rules = (_PLAYBOOKS_DIR / "rules.md").read_text(encoding="utf-8")
    logger.info(
        "Loaded playbook modules for %s: core(%d) + %s(%d) + rules(%d)",
        task_type, len(core), template_name, len(template), len(rules),
    )
    return f"{core}\n\n---\n\n{template}\n\n---\n\n{rules}"
