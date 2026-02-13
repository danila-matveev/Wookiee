#!/usr/bin/env python3
"""
Миграция: Добавление поля tip_kollekcii в modeli_osnova.

Типы коллекций:
- tricot: Vuki, Moon, Ruby, Joy, Space, Alice, Valery, Set Vuki, Set Moon, Set Ruby, VukiP, RubyP, и т.д.
- seamless_wendy: Wendy, Bella, Charlotte, Eva, Lana, Mia, Miafull, Jess, Angelina, Set Wendy
- seamless_audrey: Audrey
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db_connection import engine, execute_sql
from sqlalchemy import text


# Маппинг моделей на типы коллекций
TRICOT_MODELS = [
    'Vuki', 'Moon', 'Ruby', 'Joy', 'Space', 'Alice', 'Valery',
    'Set Vuki', 'Set Moon', 'Set Ruby',
    'VukiP', 'RubyP', 'MoonP', 'JoyP',  # принты
    'Vuki Pattern', 'Ruby Pattern',  # паттерны
]

SEAMLESS_WENDY_MODELS = [
    'Wendy', 'Bella', 'Charlotte', 'Eva', 'Lana', 'Mia', 'Miafull',
    'Jess', 'Angelina', 'Set Wendy',
]

SEAMLESS_AUDREY_MODELS = [
    'Audrey',
]


def migrate():
    """Выполняет миграцию."""
    print("=" * 60)
    print("МИГРАЦИЯ: Добавление tip_kollekcii в modeli_osnova")
    print("=" * 60)

    with engine.begin() as conn:
        # 1. Проверяем, существует ли уже колонка
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'modeli_osnova'
            AND column_name = 'tip_kollekcii'
        """))
        if result.fetchone():
            print("⚠️  Колонка tip_kollekcii уже существует")
        else:
            # 2. Добавляем колонку
            print("➕ Добавляю колонку tip_kollekcii...")
            conn.execute(text("""
                ALTER TABLE modeli_osnova
                ADD COLUMN tip_kollekcii VARCHAR(30)
                CHECK (tip_kollekcii IN ('tricot', 'seamless_wendy', 'seamless_audrey'))
            """))
            print("✅ Колонка добавлена")

        # 3. Обновляем значения для tricot
        print("\n📝 Обновляю типы коллекций...")

        # Tricot
        tricot_list = "', '".join(TRICOT_MODELS)
        result = conn.execute(text(f"""
            UPDATE modeli_osnova
            SET tip_kollekcii = 'tricot'
            WHERE kod IN ('{tricot_list}')
            AND (tip_kollekcii IS NULL OR tip_kollekcii != 'tricot')
        """))
        print(f"   tricot: {result.rowcount} записей")

        # Seamless Wendy
        wendy_list = "', '".join(SEAMLESS_WENDY_MODELS)
        result = conn.execute(text(f"""
            UPDATE modeli_osnova
            SET tip_kollekcii = 'seamless_wendy'
            WHERE kod IN ('{wendy_list}')
            AND (tip_kollekcii IS NULL OR tip_kollekcii != 'seamless_wendy')
        """))
        print(f"   seamless_wendy: {result.rowcount} записей")

        # Seamless Audrey
        audrey_list = "', '".join(SEAMLESS_AUDREY_MODELS)
        result = conn.execute(text(f"""
            UPDATE modeli_osnova
            SET tip_kollekcii = 'seamless_audrey'
            WHERE kod IN ('{audrey_list}')
            AND (tip_kollekcii IS NULL OR tip_kollekcii != 'seamless_audrey')
        """))
        print(f"   seamless_audrey: {result.rowcount} записей")

        # 4. Проверяем результат
        print("\n📊 Результат:")
        result = conn.execute(text("""
            SELECT tip_kollekcii, COUNT(*) as cnt, STRING_AGG(kod, ', ' ORDER BY kod) as models
            FROM modeli_osnova
            GROUP BY tip_kollekcii
            ORDER BY tip_kollekcii NULLS LAST
        """))
        for row in result:
            tip = row[0] or 'NULL'
            cnt = row[1]
            models = row[2][:60] + '...' if len(row[2]) > 60 else row[2]
            print(f"   {tip:20} {cnt:3} шт: {models}")

    print("\n✅ Миграция завершена!")


def rollback():
    """Откат миграции."""
    print("🔄 Откат миграции...")
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE modeli_osnova
            DROP COLUMN IF EXISTS tip_kollekcii
        """))
    print("✅ Колонка tip_kollekcii удалена")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--rollback', action='store_true', help='Откатить миграцию')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
