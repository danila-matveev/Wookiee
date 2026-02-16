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
# Marketplace ETL Database (managed, Ибрагим)
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
# AI providers
# ============================================================================
# z.ai (primary, cost-effective)
ZAI_API_KEY: str = os.getenv('ZAI_API_KEY', '')
ZAI_MODEL: str = 'glm-4.5-flash'

# Claude (secondary)
CLAUDE_API_KEY: str = os.getenv('CLAUDE_API_KEY', '')
ANALYTICS_LLM_MODEL: str = os.getenv('ANALYTICS_LLM_MODEL', 'claude-sonnet-4-5-20250929')

# OpenRouter (Kimi 2.5 for Ибрагим)
OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')
IBRAHIM_LLM_MODEL: str = os.getenv('IBRAHIM_LLM_MODEL', 'moonshotai/kimi-k2')

# ETL schedule
SYNC_SCHEDULE: str = os.getenv('SYNC_SCHEDULE', '05:00')

# Pricing per 1K tokens (USD)
PRICING: dict = {
    'claude-opus-4-6': {'input': 0.015, 'output': 0.075},
    'claude-sonnet-4-5-20250929': {'input': 0.003, 'output': 0.015},
    'glm-4-plus': {'input': 0.007, 'output': 0.007},
    'glm-4.5-flash': {'input': 0.0001, 'output': 0.0002},
    'moonshotai/kimi-k2': {'input': 0.0006, 'output': 0.002},
}

# ============================================================================
# Notion
# ============================================================================
NOTION_TOKEN: str = os.getenv('NOTION_TOKEN', '')
NOTION_DATABASE_ID: str = os.getenv('NOTION_DATABASE_ID', '')

# ============================================================================
# Timezone
# ============================================================================
TIMEZONE: str = 'Europe/Moscow'
