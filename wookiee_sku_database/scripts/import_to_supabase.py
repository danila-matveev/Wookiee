#!/usr/bin/env python3
"""
Импорт данных из локальной БД в Supabase
"""

import os
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Загружаем переменные окружения
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Supabase connection
SUPABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "sslmode": "require"
}

def main():
    sql_file = project_root / "clean_import.sql"

    if not sql_file.exists():
        print(f"✗ Файл не найден: {sql_file}")
        return 1

    print("Подключение к Supabase...")

    try:
        conn = psycopg2.connect(**SUPABASE_CONFIG)
        conn.autocommit = False
        print("✓ Подключено к Supabase!")

        # Читаем SQL файл
        sql_content = sql_file.read_text(encoding='utf-8')

        print(f"Выполняю импорт...")

        with conn.cursor() as cur:
            cur.execute(sql_content)

        conn.commit()
        print("✓ Данные успешно импортированы!")

        # Проверяем результат
        print("\nПроверка данных:")
        with conn.cursor() as cur:
            tables = [
                ('kategorii', 'Категории'),
                ('kollekcii', 'Коллекции'),
                ('statusy', 'Статусы'),
                ('razmery', 'Размеры'),
                ('importery', 'Импортеры'),
                ('fabriki', 'Фабрики'),
                ('cveta', 'Цвета'),
                ('modeli_osnova', 'Модели основы'),
                ('modeli', 'Модели'),
                ('artikuly', 'Артикулы'),
                ('tovary', 'Товары'),
            ]

            for table, name in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  {name}: {count}")

        conn.close()
        return 0

    except Exception as e:
        print(f"✗ Ошибка: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 1

if __name__ == "__main__":
    sys.exit(main())
