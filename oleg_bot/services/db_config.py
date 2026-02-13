"""
DB config bridge — data_layer.py imports from here.

data_layer.py originally imports from scripts.config.
This module provides the same interface from oleg_bot.config.
"""
from oleg_bot.config import DB_CONFIG, DB_NAME_WB, DB_NAME_OZON, SUPABASE_ENV_PATH

DB_WB = DB_NAME_WB
DB_OZON = DB_NAME_OZON
