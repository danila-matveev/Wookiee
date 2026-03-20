"""
Unified project configuration.

Single source of truth for all shared settings.
Agent-specific settings remain in agents/<name>/config.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ============================================================================
# Project root & .env
# ============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# ============================================================================
# Database (PostgreSQL)
# ============================================================================
DB_HOST: str = os.getenv('DB_HOST', 'localhost')
DB_PORT: int = int(os.getenv('DB_PORT', '5432'))
DB_USER: str = os.getenv('DB_USER', '')
DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')

DB_CONFIG: dict = {
    'host': DB_HOST,
    'port': DB_PORT,
    'user': DB_USER,
    'password': DB_PASSWORD,
}

# Database names
DB_WB: str = os.getenv('DB_NAME_WB', 'pbi_wb_wookiee')
DB_OZON: str = os.getenv('DB_NAME_OZON', 'pbi_ozon_wookiee')
DB_NAME_WB = DB_WB    # alias for backward compatibility
DB_NAME_OZON = DB_OZON  # alias for backward compatibility

# ============================================================================
# Marketplace ETL Database (managed, services/marketplace_etl)
# ============================================================================
MARKETPLACE_DB_HOST: str = os.getenv('MARKETPLACE_DB_HOST', '')
MARKETPLACE_DB_PORT: int = int(os.getenv('MARKETPLACE_DB_PORT', '5432'))
MARKETPLACE_DB_NAME: str = os.getenv('MARKETPLACE_DB_NAME', 'wookiee_marketplace')
MARKETPLACE_DB_USER: str = os.getenv('MARKETPLACE_DB_USER', '')
MARKETPLACE_DB_PASSWORD: str = os.getenv('MARKETPLACE_DB_PASSWORD', '')

MARKETPLACE_DB_CONFIG: dict = {
    'host': MARKETPLACE_DB_HOST,
    'port': MARKETPLACE_DB_PORT,
    'database': MARKETPLACE_DB_NAME,
    'user': MARKETPLACE_DB_USER,
    'password': MARKETPLACE_DB_PASSWORD,
}

# Supabase (product matrix)
SUPABASE_ENV_PATH: str = os.getenv(
    'SUPABASE_ENV_PATH',
    str(PROJECT_ROOT / 'sku_database' / '.env'),
)

# ============================================================================
# AI providers — единый провайдер OpenRouter
# ============================================================================
OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')

# Model tiers (все через OpenRouter)
MODEL_LIGHT: str = os.getenv('MODEL_LIGHT', 'z-ai/glm-4.7-flash')
MODEL_MAIN: str = os.getenv('MODEL_MAIN', 'z-ai/glm-4.7')
MODEL_HEAVY: str = os.getenv('MODEL_HEAVY', 'google/gemini-3-flash-preview')
MODEL_FREE: str = os.getenv('MODEL_FREE', 'openrouter/free')

# Backward-compatible alias for Ibrahim
IBRAHIM_LLM_MODEL: str = os.getenv('IBRAHIM_LLM_MODEL', MODEL_MAIN)

# ETL schedule
SYNC_SCHEDULE: str = os.getenv('SYNC_SCHEDULE', '05:00')

# Pricing per 1K tokens (USD) — OpenRouter pricing
PRICING: dict = {
    'z-ai/glm-4.7-flash': {'input': 0.00007, 'output': 0.0003},
    'z-ai/glm-4.7': {'input': 0.00006, 'output': 0.0004},
    'google/gemini-3-flash-preview': {'input': 0.0005, 'output': 0.003},
    'openrouter/free': {'input': 0.0, 'output': 0.0},
}

# ============================================================================
# Knowledge Base — Gemini Embedding (прямой доступ, не через OpenRouter)
# ============================================================================
GOOGLE_API_KEY: str = os.getenv('GOOGLE_API_KEY', '')

# ============================================================================
# Notion
# ============================================================================
NOTION_TOKEN: str = os.getenv('NOTION_TOKEN', '')
NOTION_DATABASE_ID: str = os.getenv('NOTION_DATABASE_ID', '')

# ============================================================================
# Timezone
# ============================================================================
TIMEZONE: str = 'Europe/Moscow'
