"""
SQLite database service for Lyudmila Bot
Пользователи + лог действий
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from agents.lyudmila import config

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 5.0  # seconds


class DBService:
    """SQLite storage for users and action log"""

    def __init__(self, db_path: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT):
        self.db_path = db_path or config.SQLITE_DB_PATH
        self.timeout = timeout
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")
        return conn

    def _init_db(self) -> None:
        """Create tables if not exist"""
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    telegram_username TEXT,
                    bitrix_user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    timezone TEXT DEFAULT 'Europe/Moscow',
                    is_active INTEGER DEFAULT 1,
                    digest_enabled INTEGER DEFAULT 1,
                    digest_time TEXT DEFAULT '09:00',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    bitrix_entity_id INTEGER,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                ON users(telegram_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_log_telegram_id
                ON action_log(telegram_id)
            """)

            conn.commit()
            logger.info("Lyudmila DB initialized")

    # ─── Users CRUD ───────────────────────────────────────────────

    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram_id"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_user(
        self,
        telegram_id: int,
        bitrix_user_id: int,
        email: str,
        first_name: str,
        last_name: str,
        telegram_username: Optional[str] = None,
    ) -> int:
        """Create new user, return row id"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users
                (telegram_id, telegram_username, bitrix_user_id, email,
                 first_name, last_name, is_active, last_active_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (telegram_id, telegram_username, bitrix_user_id, email,
                  first_name, last_name))
            conn.commit()
            logger.info(f"User created/updated: tg={telegram_id} bitrix={bitrix_user_id}")
            return cursor.lastrowid

    def update_last_active(self, telegram_id: int) -> None:
        """Update last_active_at timestamp"""
        with self._connect() as conn:
            conn.cursor().execute(
                "UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (telegram_id,),
            )
            conn.commit()

    def update_user_settings(
        self,
        telegram_id: int,
        timezone: Optional[str] = None,
        digest_enabled: Optional[bool] = None,
        digest_time: Optional[str] = None,
    ) -> None:
        """Update user settings"""
        updates = []
        params = []
        if timezone is not None:
            updates.append("timezone = ?")
            params.append(timezone)
        if digest_enabled is not None:
            updates.append("digest_enabled = ?")
            params.append(int(digest_enabled))
        if digest_time is not None:
            updates.append("digest_time = ?")
            params.append(digest_time)

        if not updates:
            return

        params.append(telegram_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?"

        with self._connect() as conn:
            conn.cursor().execute(query, params)
            conn.commit()

    def deactivate_user(self, telegram_id: int) -> None:
        """Deactivate user"""
        with self._connect() as conn:
            conn.cursor().execute(
                "UPDATE users SET is_active = 0 WHERE telegram_id = ?",
                (telegram_id,),
            )
            conn.commit()
            logger.info(f"User deactivated: tg={telegram_id}")

    def get_all_active_users(self) -> List[Dict[str, Any]]:
        """Get all active users"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]

    # ─── Action Log ───────────────────────────────────────────────

    def log_action(
        self,
        telegram_id: int,
        action_type: str,
        bitrix_entity_id: Optional[int] = None,
        details: Optional[Dict] = None,
    ) -> None:
        """Log user action"""
        with self._connect() as conn:
            conn.cursor().execute("""
                INSERT INTO action_log (telegram_id, action_type, bitrix_entity_id, details)
                VALUES (?, ?, ?, ?)
            """, (
                telegram_id,
                action_type,
                bitrix_entity_id,
                json.dumps(details, ensure_ascii=False) if details else None,
            ))
            conn.commit()
