#!/usr/bin/env python3
"""
Миграция 003: Унификация статусов и очистка данных.

1. Создание 7 единых статусов (без колонки tip)
2. Ремаппинг всех FK ссылок (modeli, artikuly, cveta, tovary)
3. Удаление старых 21 статуса и колонки tip
4. Удаление мусорной записи БАЗА СИНГВЕР из cveta
5. Отчёт по проблемным записям
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.database import engine
from sqlalchemy import text


# Маппинг старых ID → новые единые ID
# Новые ID: 1=Продается, 2=Выводим, 3=Архив, 4=Подготовка, 5=План, 6=Новый, 7=Запуск
MODEL_MAP = {1: 1, 2: 7, 3: 5, 5: 2}  # В продаже→1, Запуск→7, Планирование→5, Выводим→2
PRODUCT_MAP = {8: 1, 9: 2, 10: 3, 11: 4, 12: 5, 13: 6, 14: 7}
COLOR_MAP = {15: 1, 16: 7, 17: 2, 18: 5, 19: 4, 20: 6, 21: 3}

UNIFIED_STATUSES = [
    (1, 'Продается'),
    (2, 'Выводим'),
    (3, 'Архив'),
    (4, 'Подготовка'),
    (5, 'План'),
    (6, 'Новый'),
    (7, 'Запуск'),
]


def migrate():
    """Выполняет миграцию."""
    print("=" * 60)
    print("МИГРАЦИЯ 003: Унификация статусов")
    print("=" * 60)

    with engine.connect() as conn:
        # 1. Временно отключаем FK constraints
        print("\n1. Ремаппинг FK ссылок...")

        # modeli.status_id (model statuses: 1,2,3,5 → new IDs)
        for old_id, new_id in MODEL_MAP.items():
            result = conn.execute(
                text("UPDATE modeli SET status_id = :new WHERE status_id = :old"),
                {"old": old_id, "new": new_id + 100}  # Временно +100 чтобы избежать конфликтов
            )
            if result.rowcount:
                print(f"   modeli: {old_id} → {new_id} ({result.rowcount} записей)")

        # artikuly.status_id
        for old_id, new_id in PRODUCT_MAP.items():
            result = conn.execute(
                text("UPDATE artikuly SET status_id = :new WHERE status_id = :old"),
                {"old": old_id, "new": new_id + 100}
            )
            if result.rowcount:
                print(f"   artikuly: {old_id} → {new_id} ({result.rowcount} записей)")

        # cveta.status_id
        for old_id, new_id in COLOR_MAP.items():
            result = conn.execute(
                text("UPDATE cveta SET status_id = :new WHERE status_id = :old"),
                {"old": old_id, "new": new_id + 100}
            )
            if result.rowcount:
                print(f"   cveta: {old_id} → {new_id} ({result.rowcount} записей)")

        # tovary — 4 колонки со статусами
        for col in ['status_id', 'status_ozon_id']:
            for old_id, new_id in PRODUCT_MAP.items():
                result = conn.execute(
                    text(f"UPDATE tovary SET {col} = :new WHERE {col} = :old"),
                    {"old": old_id, "new": new_id + 100}
                )
                if result.rowcount:
                    print(f"   tovary.{col}: {old_id} → {new_id} ({result.rowcount} записей)")

        # 2. Удаляем все старые статусы
        print("\n2. Удаление старых статусов...")
        result = conn.execute(text("DELETE FROM statusy"))
        print(f"   Удалено {result.rowcount} старых статусов")

        # 3. Удаляем колонку tip
        print("\n3. Удаление колонки tip...")
        try:
            conn.execute(text("ALTER TABLE statusy DROP CONSTRAINT IF EXISTS check_status_tip"))
            print("   Constraint check_status_tip удалён")
        except Exception as e:
            print(f"   Constraint: {e}")

        try:
            conn.execute(text("ALTER TABLE statusy DROP COLUMN IF EXISTS tip"))
            print("   Колонка tip удалена")
        except Exception as e:
            print(f"   Колонка tip: {e}")

        # Добавляем UNIQUE на nazvanie (если ещё нет)
        try:
            conn.execute(text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'statusy_nazvanie_key'
                    ) THEN
                        ALTER TABLE statusy ADD CONSTRAINT statusy_nazvanie_key UNIQUE (nazvanie);
                    END IF;
                END $$;
            """))
            print("   UNIQUE constraint на nazvanie добавлен")
        except Exception as e:
            print(f"   UNIQUE constraint: {e}")

        # Удаляем старый UNIQUE на (nazvanie, tip) если существует
        try:
            conn.execute(text("ALTER TABLE statusy DROP CONSTRAINT IF EXISTS statusy_nazvanie_tip_key"))
            print("   Старый UNIQUE (nazvanie, tip) удалён")
        except Exception as e:
            print(f"   Старый UNIQUE: {e}")

        # 4. Создаём 7 единых статусов
        print("\n4. Создание единых статусов...")
        for sid, name in UNIFIED_STATUSES:
            conn.execute(
                text("INSERT INTO statusy (id, nazvanie) VALUES (:id, :name)"),
                {"id": sid, "name": name}
            )
            print(f"   + {sid}: {name}")

        # Обновляем sequence
        conn.execute(text("SELECT setval('statusy_id_seq', 7)"))

        # 5. Снимаем временное смещение +100
        print("\n5. Снятие временного смещения...")
        for table, col in [
            ('modeli', 'status_id'),
            ('artikuly', 'status_id'),
            ('cveta', 'status_id'),
            ('tovary', 'status_id'),
            ('tovary', 'status_ozon_id'),
        ]:
            result = conn.execute(
                text(f"UPDATE {table} SET {col} = {col} - 100 WHERE {col} > 100")
            )
            if result.rowcount:
                print(f"   {table}.{col}: {result.rowcount} записей нормализовано")

        # 6. Удаление БАЗА СИНГВЕР
        print("\n6. Удаление мусорных записей из cveta...")
        result = conn.execute(
            text("DELETE FROM cveta WHERE color_code = '31' AND cvet = 'БАЗА СИНГВЕР' RETURNING id")
        ).fetchall()
        if result:
            print(f"   Удалена БАЗА СИНГВЕР (id={result[0][0]})")
        else:
            print("   БАЗА СИНГВЕР не найдена, пропускаю.")

        # Удаляем заголовок Excel и метаданные (если ещё есть)
        result = conn.execute(
            text("DELETE FROM cveta WHERE color_code = 'Color code' RETURNING id")
        ).fetchall()
        if result:
            print(f"   Удалена строка-заголовок (id={result[0][0]})")

        result = conn.execute(
            text("DELETE FROM cveta WHERE color_code = '0' AND cvet = 'Ткань как у Audrey' RETURNING id")
        ).fetchall()
        if result:
            print(f"   Удалена строка-метаданные (id={result[0][0]})")

        conn.commit()

        # 7. Отчёт
        print("\n" + "=" * 60)
        print("ОТЧЁТ")
        print("=" * 60)

        # Проверка статусов
        result = conn.execute(
            text("SELECT id, nazvanie FROM statusy ORDER BY id")
        ).fetchall()
        print(f"\nСтатусы ({len(result)} шт.):")
        for row in result:
            print(f"   {row[0]}: {row[1]}")

        # Проверка что все FK валидны
        for table, col in [
            ('modeli', 'status_id'),
            ('artikuly', 'status_id'),
            ('cveta', 'status_id'),
            ('tovary', 'status_id'),
            ('tovary', 'status_ozon_id'),
        ]:
            result = conn.execute(text(f"""
                SELECT COUNT(*) FROM {table}
                WHERE {col} IS NOT NULL
                AND {col} NOT IN (SELECT id FROM statusy)
            """)).fetchone()
            if result[0] > 0:
                print(f"\n   ОШИБКА: {table}.{col} — {result[0]} записей с невалидным FK!")
            else:
                orphans = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")).fetchone()
                total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
                print(f"   {table}.{col}: OK ({total[0]} записей, {orphans[0]} NULL)")

        # Цвета
        result = conn.execute(text("SELECT COUNT(*) FROM cveta")).fetchone()
        print(f"\nЦветов в БД: {result[0]}")

        # Проблемные записи
        result = conn.execute(
            text("SELECT id, artikul FROM artikuly WHERE model_id IS NULL ORDER BY id")
        ).fetchall()
        if result:
            print(f"\nАртикулы без model_id ({len(result)} шт.):")
            for row in result:
                print(f"   id={row[0]}, artikul='{row[1]}'")

        result = conn.execute(
            text("SELECT id, artikul FROM artikuly WHERE cvet_id IS NULL ORDER BY id")
        ).fetchall()
        if result:
            print(f"\nАртикулы без cvet_id ({len(result)} шт.):")
            for row in result:
                print(f"   id={row[0]}, artikul='{row[1]}'")


def rollback():
    """Откат миграции — невозможен, т.к. удалена колонка tip."""
    print("ВНИМАНИЕ: Откат миграции 003 невозможен.")
    print("Для восстановления используйте clean_import.sql + schema.sql")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Миграция 003: Унификация статусов')
    parser.add_argument('--rollback', action='store_true', help='Откатить миграцию')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
