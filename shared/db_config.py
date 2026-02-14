"""
Backward-compatible re-export.

Old code may import from db_config — redirect to shared.config.
"""
from shared.config import DB_CONFIG, DB_WB, DB_OZON, DB_NAME_WB, DB_NAME_OZON, SUPABASE_ENV_PATH  # noqa: F401
