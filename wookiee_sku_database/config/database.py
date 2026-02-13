"""
Настройки подключения к базе данных PostgreSQL.

Поддерживает два режима:
- Supabase (облако) - если указан POSTGRES_HOST с pooler.supabase.com
- Docker (локально) - если POSTGRES_HOST = localhost или не указан

Использование:
    from config.database import get_session, engine, execute_sql

    # Простой SQL запрос
    result = execute_sql("SELECT * FROM cveta LIMIT 5")

    # Работа с ORM
    with get_session() as session:
        modeli = session.query(Model).all()
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Загружаем .env из корня проекта
_project_root = Path(__file__).parent.parent
_env_path = _project_root / '.env'
load_dotenv(_env_path)


@dataclass
class DatabaseConfig:
    """Конфигурация подключения к PostgreSQL"""

    host: str = os.getenv('POSTGRES_HOST', 'localhost')
    port: int = int(os.getenv('POSTGRES_PORT', '5432'))
    database: str = os.getenv('POSTGRES_DB', 'postgres')
    user: str = os.getenv('POSTGRES_USER', 'postgres')
    password: str = os.getenv('POSTGRES_PASSWORD', '')

    @property
    def is_supabase(self) -> bool:
        """Проверяет, это Supabase или локальная БД"""
        return 'supabase' in self.host.lower() or 'pooler' in self.host.lower()

    @property
    def connection_string(self) -> str:
        """Строка подключения к PostgreSQL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def display_host(self) -> str:
        """Хост для отображения (без пароля)"""
        return f"{self.host}:{self.port}/{self.database}"


# Конфигурация
config = DatabaseConfig()

# Параметры подключения зависят от типа БД
_connect_args = {}
if config.is_supabase:
    _connect_args['sslmode'] = 'require'  # Supabase требует SSL

# Создание движка SQLAlchemy
engine = create_engine(
    config.connection_string,
    echo=os.getenv('SQL_ECHO', 'false').lower() == 'true',
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ============================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================

def get_session() -> Session:
    """
    Получить сессию базы данных.

    Использование:
        session = get_session()
        try:
            modeli = session.query(Model).all()
            session.commit()
        finally:
            session.close()
    """
    return SessionLocal()


def execute_sql(sql: str, params: Optional[dict] = None, fetch: bool = True) -> Optional[List[Any]]:
    """
    Выполняет SQL запрос и возвращает результат.

    Args:
        sql: SQL запрос
        params: Параметры запроса (опционально)
        fetch: True - вернуть результат, False - только выполнить

    Returns:
        Список кортежей с результатами или None

    Использование:
        # Простой запрос
        result = execute_sql("SELECT * FROM cveta LIMIT 5")

        # С параметрами
        result = execute_sql(
            "SELECT * FROM cveta WHERE status_id = :status",
            {'status': 1}
        )
    """
    with engine.connect() as conn:
        if params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql))

        if fetch:
            return result.fetchall()
        conn.commit()
        return None


def test_connection() -> bool:
    """
    Проверка подключения к базе данных.

    Returns:
        True если подключение успешно, False если ошибка
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            db_type = "Supabase" if config.is_supabase else "Docker/Local"

            print(f"{'=' * 60}")
            print(f"ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ({db_type})")
            print(f"{'=' * 60}")
            print(f"Host: {config.host}")
            print(f"Database: {config.database}")
            print(f"User: {config.user[:20]}{'...' if len(config.user) > 20 else ''}")
            print(f"{'=' * 60}")
            print(f"PostgreSQL: {version[:60]}...")
            print(f"{'=' * 60}")

            # Проверяем таблицы
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            print(f"Таблиц в БД: {len(tables)}")
            if tables:
                print(f"Таблицы: {', '.join(tables[:8])}{'...' if len(tables) > 8 else ''}")

            return True

    except Exception as e:
        print(f"Ошибка подключения: {e}")
        return False


def get_table_counts() -> List[tuple]:
    """
    Получает количество записей в каждой таблице.

    Returns:
        Список кортежей (schema, table_name, row_count)
    """
    sql = """
    SELECT
        schemaname,
        relname as table_name,
        n_live_tup as row_count
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY n_live_tup DESC
    """
    return execute_sql(sql)


# ============================================
# ФУНКЦИИ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_database():
    """
    Инициализация базы данных: создание всех таблиц.
    Выполняется один раз при первом запуске.
    """
    from database.models import Base
    Base.metadata.create_all(bind=engine)
    print("База данных успешно инициализирована!")


def drop_all_tables():
    """
    Удаление всех таблиц (ОПАСНО! Только для разработки)
    """
    from database.models import Base
    Base.metadata.drop_all(bind=engine)
    print("Все таблицы удалены!")


# ============================================
# ЗАПУСК КАК СКРИПТ
# ============================================

if __name__ == '__main__':
    if test_connection():
        print("\nСТАТИСТИКА ТАБЛИЦ:")
        print("-" * 40)
        for schema, table, count in get_table_counts():
            print(f"  {table:25} {count:>8} строк")
