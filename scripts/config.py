"""
Настройки подключения к базам данных.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

# Финансовая БД (WB и OZON)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
}

# Базы данных
DB_WB = os.getenv('DB_NAME_WB', 'pbi_wb_wookiee')
DB_OZON = os.getenv('DB_NAME_OZON', 'pbi_ozon_wookiee')

# Supabase (товарная матрица)
SUPABASE_ENV_PATH = os.getenv(
    'SUPABASE_ENV_PATH',
    str(Path(__file__).resolve().parent.parent / 'wookiee_sku_database' / '.env')
)

# Notion API (синхронизация отчётов)
NOTION_TOKEN = os.getenv('NOTION_TOKEN', '')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', '')

# Claude API (для Фазы 2: Рома в боте)
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
ANALYTICS_LLM_MODEL = os.getenv('ANALYTICS_LLM_MODEL', 'claude-sonnet-4-5-20250929')
