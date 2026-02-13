#!/usr/bin/env python3
"""
Миграция 004: Исправление целостности данных.

1. Удаление колонок status_sayt_id и status_lamoda_id из tovary
2. Привязка set_ruby артикулов к модели (model_id = 21)
3. Создание modeli_osnova для Evelyn (id=23)
4. Привязка modeli Evelyn к modeli_osnova
5. Установка kollekciya_id для Charlotte
6. Создание modeli Charlotte (id=41)
7. Привязка Charlotte артикулов к модели (model_id = 41)
8. Привязка цветов к Angelina и set_Wendy артикулам
9. Исправление кириллицы в cveta (латинская 'c' → кириллическая 'с')
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.database import engine
from sqlalchemy import text


def migrate():
    """Выполняет миграцию."""
    print("=" * 60)
    print("МИГРАЦИЯ 004: Исправление целостности данных")
    print("=" * 60)

    with engine.connect() as conn:
        # 1. Удаление колонок status_sayt_id и status_lamoda_id
        print("\n1. Удаление status_sayt_id и status_lamoda_id из tovary...")
        for col in ['status_sayt_id', 'status_lamoda_id']:
            try:
                conn.execute(text(f"ALTER TABLE tovary DROP COLUMN IF EXISTS {col}"))
                print(f"   Колонка {col} удалена")
            except Exception as e:
                print(f"   {col}: {e}")

        # 2. Привязка set_ruby артикулов к модели Set Ruby (id=21)
        print("\n2. Привязка set_ruby артикулов к модели...")
        result = conn.execute(
            text("UPDATE artikuly SET model_id = 21 WHERE id IN (168, 169, 170, 171, 172, 173) AND model_id IS NULL")
        )
        print(f"   Обновлено {result.rowcount} записей (set_ruby → model_id=21)")

        # 3. Создание modeli_osnova для Evelyn
        print("\n3. Создание modeli_osnova для Evelyn...")
        exists = conn.execute(
            text("SELECT id FROM modeli_osnova WHERE kod = 'Evelyn'")
        ).fetchone()
        if exists:
            print(f"   Evelyn уже существует (id={exists[0]}), пропускаю")
            evelyn_osnova_id = exists[0]
        else:
            conn.execute(text("""
                INSERT INTO modeli_osnova (kod, kategoriya_id, kollekciya_id, fabrika_id,
                    razmery_modeli, sku_china, upakovka, sostav_syrya, composition,
                    tnved, gruppa_sertifikata, nazvanie_etiketka)
                VALUES ('Evelyn', 1, 6, 1,
                    'S, M, L', 'SET va01+lyn01', 'Small Cosmetic pack',
                    '95% хлопок, 5% эластан', '95% cotton, 5% elastane',
                    '6 212 10 1000', 'Товары ООО', 'Комплект нижнего белья')
            """))
            evelyn_osnova_id = conn.execute(
                text("SELECT id FROM modeli_osnova WHERE kod = 'Evelyn'")
            ).fetchone()[0]
            print(f"   Создана modeli_osnova Evelyn (id={evelyn_osnova_id})")

        # 4. Привязка modeli Evelyn к modeli_osnova
        print("\n4. Привязка modeli Evelyn к modeli_osnova...")
        result = conn.execute(
            text("UPDATE modeli SET model_osnova_id = :osnova_id WHERE kod = 'Evelyn' AND model_osnova_id IS NULL"),
            {"osnova_id": evelyn_osnova_id}
        )
        print(f"   Обновлено {result.rowcount} записей")

        # 5. Установка kollekciya_id для Charlotte
        print("\n5. Charlotte: kollekciya_id → 7 (Бесшовное белье Jelly)...")
        result = conn.execute(
            text("UPDATE modeli_osnova SET kollekciya_id = 7 WHERE kod = 'Charlotte' AND kollekciya_id IS NULL")
        )
        print(f"   Обновлено {result.rowcount} записей")

        # 6. Создание модели Charlotte
        print("\n6. Создание модели Charlotte...")
        exists = conn.execute(
            text("SELECT id FROM modeli WHERE kod = 'Charlotte'")
        ).fetchone()
        if exists:
            print(f"   Charlotte уже существует (id={exists[0]}), пропускаю")
            charlotte_model_id = exists[0]
        else:
            charlotte_osnova = conn.execute(
                text("SELECT id FROM modeli_osnova WHERE kod = 'Charlotte'")
            ).fetchone()
            if charlotte_osnova:
                conn.execute(text("""
                    INSERT INTO modeli (kod, nazvanie, artikul_modeli, model_osnova_id, importer_id, status_id, nabor)
                    VALUES ('Charlotte', 'Charlotte', 'Charlotte/', :osnova_id, 2, 7, false)
                """), {"osnova_id": charlotte_osnova[0]})
                charlotte_model_id = conn.execute(
                    text("SELECT id FROM modeli WHERE kod = 'Charlotte'")
                ).fetchone()[0]
                print(f"   Создана модель Charlotte (id={charlotte_model_id})")
            else:
                print("   ОШИБКА: modeli_osnova Charlotte не найдена!")
                charlotte_model_id = None

        # 7. Привязка Charlotte артикулов к модели
        if charlotte_model_id:
            print("\n7. Привязка Charlotte артикулов к модели...")
            result = conn.execute(
                text("UPDATE artikuly SET model_id = :model_id WHERE artikul LIKE 'Charlotte/%' AND model_id IS NULL"),
                {"model_id": charlotte_model_id}
            )
            print(f"   Обновлено {result.rowcount} записей")

        # 8. Привязка цветов к Angelina и set_Wendy артикулам
        print("\n8. Привязка цветов к артикулам...")
        color_fixes = [
            (446, 123, 'set_Wendy/nude → WE010/nude'),
            (451, 3, 'Angelina/white → code 1/White'),
            (452, 2, 'Angelina/black → code 2/Black'),
            (453, 6, 'Angelina/dark_red → code w3/Wine red'),
            (454, 4, 'Angelina/nude → code 3/Nude'),
        ]
        for art_id, cvet_id, desc in color_fixes:
            result = conn.execute(
                text("UPDATE artikuly SET cvet_id = :cvet WHERE id = :id AND cvet_id IS NULL"),
                {"cvet": cvet_id, "id": art_id}
            )
            if result.rowcount:
                print(f"   {desc} ({result.rowcount} запись)")

        # 9. Исправление кириллицы в cveta
        print("\n9. Исправление кириллицы в cveta...")
        # Latin 'c' (U+0063) → Cyrillic 'с' (U+0441)
        result = conn.execute(
            text("UPDATE cveta SET cvet = 'серый' WHERE id = 13 AND cvet = 'cерый'")
        )
        if result.rowcount:
            print(f"   cveta 13: cерый → серый")

        result = conn.execute(
            text("UPDATE cveta SET cvet = 'светло-розовый' WHERE id = 17 AND cvet = 'cветло-розовый'")
        )
        if result.rowcount:
            print(f"   cveta 17: cветло-розовый → светло-розовый")

        conn.commit()

        # Отчёт
        print("\n" + "=" * 60)
        print("ОТЧЁТ")
        print("=" * 60)

        # Проверка NULL FK
        checks = [
            ("artikuly WHERE model_id IS NULL", "Артикулы без model_id"),
            ("artikuly WHERE cvet_id IS NULL", "Артикулы без cvet_id"),
            ("modeli WHERE model_osnova_id IS NULL", "Модели без model_osnova_id"),
            ("modeli_osnova WHERE kollekciya_id IS NULL", "Модели основы без kollekciya_id"),
        ]
        for query, desc in checks:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {query}")).fetchone()
            status = "OK" if result[0] == 0 else f"ПРОБЛЕМА: {result[0]}"
            print(f"   {desc}: {status}")

        # Проверка колонок tovary
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tovary' AND column_name LIKE 'status_%'
            ORDER BY column_name
        """)).fetchall()
        cols = [r[0] for r in result]
        print(f"\n   Статус-колонки в tovary: {cols}")

        # Проверка кириллицы
        result = conn.execute(text("""
            SELECT COUNT(*) FROM cveta WHERE cvet ~ '^[a-zA-Z]'
        """)).fetchone()
        print(f"   Цвета с латинскими буквами в начале: {result[0]}")


def rollback():
    """Откат миграции — частичный."""
    print("ВНИМАНИЕ: Откат миграции 004 частично возможен.")
    print("Для полного восстановления используйте clean_import.sql + schema.sql")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Миграция 004: Исправление целостности данных')
    parser.add_argument('--rollback', action='store_true', help='Откатить миграцию')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
