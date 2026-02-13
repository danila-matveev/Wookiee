#!/usr/bin/env python3
"""
Скрипт развертывания схемы БД в Supabase
"""

import os
import psycopg2
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv(Path(__file__).parent.parent / ".env")

# Supabase connection из переменных окружения
SUPABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db.gjvwcdtfglupewcwzfhw.supabase.co"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require"
}

def execute_sql_file(conn, filepath: Path, description: str):
    """Выполняет SQL файл"""
    print(f"\n{'='*50}")
    print(f"Выполняю: {description}")
    print(f"Файл: {filepath}")
    print('='*50)

    sql = filepath.read_text(encoding='utf-8')

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print(f"✓ {description} - успешно!")

def main():
    base_dir = Path(__file__).parent.parent / "database"

    schema_file = base_dir / "schema.sql"
    triggers_file = base_dir / "triggers.sql"

    print("Подключение к Supabase PostgreSQL...")

    try:
        conn = psycopg2.connect(**SUPABASE_CONFIG)
        print("✓ Подключено к Supabase!")

        # Выполняем schema.sql
        execute_sql_file(conn, schema_file, "Создание таблиц и views (schema.sql)")

        # Выполняем triggers.sql
        execute_sql_file(conn, triggers_file, "Создание триггеров (triggers.sql)")

        # Проверяем результат
        print("\n" + "="*50)
        print("Проверка развертывания...")
        print("="*50)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = cur.fetchall()
            print(f"\nСозданные таблицы ({len(tables)}):")
            for t in tables:
                print(f"  - {t[0]}")

            cur.execute("""
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            views = cur.fetchall()
            print(f"\nСозданные views ({len(views)}):")
            for v in views:
                print(f"  - {v[0]}")

        conn.close()
        print("\n✓ Развертывание завершено успешно!")
        return 0

    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
