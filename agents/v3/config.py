"""Wookiee v3 agent system configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# OpenRouter (same as existing system)
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# Model tiers
MODEL_HEAVY: str = os.getenv("MODEL_HEAVY", "google/gemini-3-flash-preview")
MODEL_MAIN: str = os.getenv("MODEL_MAIN", "z-ai/glm-4.7")
MODEL_LIGHT: str = os.getenv("MODEL_LIGHT", "z-ai/glm-4.7-flash")

# Agent MD files directory
AGENTS_DIR: Path = PROJECT_ROOT / "agents" / "v3" / "agents"

# Timeouts (seconds)
AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", "120"))
ORCHESTRATOR_TIMEOUT: int = int(os.getenv("ORCHESTRATOR_TIMEOUT", "600"))
