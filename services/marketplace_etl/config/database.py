"""
Database configuration and connection settings.
Delegates to shared.config for all env vars. Supports multiple marketplace accounts.
"""

import os
import json

from shared.config import (
    MARKETPLACE_DB_CONFIG,
    DB_CONFIG, DB_WB, DB_OZON,
    SYNC_SCHEDULE,
)

# Re-export for backward compatibility within ETL package
SOURCE_DB_WB = DB_WB
SOURCE_DB_OZON = DB_OZON

# Single API Keys (loaded from shared config's .env)
WB_API_KEY = os.getenv('WB_API_KEY')
OZON_CLIENT_ID = os.getenv('OZON_CLIENT_ID')
OZON_API_KEY = os.getenv('OZON_API_KEY')


def get_db_connection(config=None):
    """
    Create connection to managed marketplace database.

    Args:
        config: Database configuration dict. If None, uses MARKETPLACE_DB_CONFIG.

    Returns:
        psycopg2 connection object
    """
    import psycopg2

    if config is None:
        config = MARKETPLACE_DB_CONFIG

    return psycopg2.connect(**config)


def get_source_db_connection(database):
    """
    Create connection to source database (read-only, for reconciliation).

    Args:
        database: Database name (SOURCE_DB_WB or SOURCE_DB_OZON)

    Returns:
        psycopg2 connection object
    """
    import psycopg2

    config = DB_CONFIG.copy()
    config['database'] = database

    return psycopg2.connect(**config)


def get_accounts():
    """
    Load marketplace accounts from config/accounts.json or env vars.

    Returns:
        dict with 'wb' and 'ozon' lists of account dicts:
        {
            'wb': [{'lk': 'WB ИП Медведева П.В.', 'api_key': '...'}, ...],
            'ozon': [{'lk': 'Ozon ИП Медведева П.В.', 'client_id': '...', 'api_key': '...'}, ...]
        }
    """
    accounts_file = os.path.join(os.path.dirname(__file__), 'accounts.json')

    if os.path.exists(accounts_file):
        with open(accounts_file) as f:
            return json.load(f)

    # Fallback: single account from env vars
    accounts = {'wb': [], 'ozon': []}

    if WB_API_KEY:
        accounts['wb'].append({
            'lk': os.getenv('WB_LK', 'WB Default'),
            'api_key': WB_API_KEY,
        })

    if OZON_CLIENT_ID and OZON_API_KEY:
        accounts['ozon'].append({
            'lk': os.getenv('OZON_LK', 'Ozon Default'),
            'client_id': OZON_CLIENT_ID,
            'api_key': OZON_API_KEY,
        })

    return accounts
