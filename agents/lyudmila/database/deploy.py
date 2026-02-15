#!/usr/bin/env python3
"""
Деплой таблиц Людмилы в Supabase.

Запуск:
    python -m lyudmila_bot.database.deploy
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

try:
    import psycopg2
except ImportError:
    print("pip install psycopg2-binary")
    sys.exit(1)


def main():
    config = {
        "host": os.getenv("SUPABASE_HOST", ""),
        "port": int(os.getenv("SUPABASE_PORT", "5432")),
        "database": os.getenv("SUPABASE_DB", "postgres"),
        "user": os.getenv("SUPABASE_USER", ""),
        "password": os.getenv("SUPABASE_PASSWORD", ""),
        "sslmode": "require",
    }

    if not config["host"]:
        print("ERROR: SUPABASE_HOST not set in .env")
        sys.exit(1)

    sql_dir = Path(__file__).parent
    sql_file = sql_dir / "001_lyudmila_tables.sql"

    if not sql_file.exists():
        print(f"ERROR: {sql_file} not found")
        sys.exit(1)

    print(f"Connecting to Supabase ({config['host']})...")

    try:
        conn = psycopg2.connect(**config)
        print("Connected!")

        sql = sql_file.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("Tables created successfully!")

        # Verify
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name LIKE 'lyudmila_%'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

        print(f"\nLyudmila tables ({len(tables)}):")
        for t in tables:
            print(f"  - {t}")

        conn.close()

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
