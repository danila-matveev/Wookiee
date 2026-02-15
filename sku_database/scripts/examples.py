#!/usr/bin/env python3
"""
Примеры работы с базой данных Wookiee в Supabase.

Запуск:
    python3 scripts/examples.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from config.database import get_session
from database.models import (
    Kategoriya, Kollekciya, Status, Razmer,
    Importer, Fabrika, Cvet, ModelOsnova,
    Model, Artikul, Tovar
)
from sqlalchemy import text


def example_1_read_all():
    """Пример 1: Чтение всех записей"""
    print("\n=== Пример 1: Чтение всех категорий ===")

    with get_session() as session:
        kategorii = session.query(Kategoriya).all()

        if kategorii:
            for k in kategorii:
                print(f"  ID: {k.id}, Название: {k.nazvanie}")
        else:
            print("  (таблица пуста)")


def example_2_add_data():
    """Пример 2: Добавление данных"""
    print("\n=== Пример 2: Добавление категории ===")

    with get_session() as session:
        # Проверяем, есть ли уже такая категория
        existing = session.query(Kategoriya).filter(
            Kategoriya.nazvanie == "Комплект белья"
        ).first()

        if existing:
            print(f"  Категория уже существует: ID={existing.id}")
        else:
            new_kat = Kategoriya(nazvanie="Комплект белья")
            session.add(new_kat)
            session.commit()
            print(f"  Создана категория: ID={new_kat.id}")


def example_3_filter():
    """Пример 3: Фильтрация и поиск"""
    print("\n=== Пример 3: Поиск по фильтру ===")

    with get_session() as session:
        # Поиск по части названия
        results = session.query(Kategoriya).filter(
            Kategoriya.nazvanie.ilike("%белья%")
        ).all()

        print(f"  Найдено категорий с 'белья': {len(results)}")
        for r in results:
            print(f"    - {r.nazvanie}")


def example_4_raw_sql():
    """Пример 4: Прямой SQL-запрос"""
    print("\n=== Пример 4: Прямой SQL-запрос ===")

    with get_session() as session:
        result = session.execute(text("""
            SELECT table_name,
                   (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
            FROM (
                SELECT table_name,
                       query_to_xml(format('SELECT COUNT(*) as cnt FROM %I.%I',
                                          table_schema, table_name), false, true, '') as xml_count
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            ) t
            ORDER BY row_count DESC
            LIMIT 5;
        """))

        print("  Топ-5 таблиц по количеству записей:")
        for row in result:
            print(f"    {row[0]}: {row[1]} записей")


def example_5_relationships():
    """Пример 5: Работа со связями (когда данные загружены)"""
    print("\n=== Пример 5: Связи между таблицами ===")

    with get_session() as session:
        # Получаем товар со всеми связями
        tovar = session.query(Tovar).first()

        if tovar:
            print(f"  Товар: {tovar.barkod}")
            if tovar.artikul:
                print(f"    Артикул: {tovar.artikul.artikul}")
                if tovar.artikul.model:
                    print(f"    Модель: {tovar.artikul.model.nazvanie}")
            if tovar.razmer:
                print(f"    Размер: {tovar.razmer.nazvanie}")
        else:
            print("  (товары ещё не загружены)")


def example_6_bulk_insert():
    """Пример 6: Массовая вставка"""
    print("\n=== Пример 6: Массовая вставка размеров ===")

    with get_session() as session:
        # Стандартные размеры
        sizes = [
            ("XS", 1), ("S", 2), ("M", 3),
            ("L", 4), ("XL", 5), ("XXL", 6)
        ]

        added = 0
        for name, order in sizes:
            existing = session.query(Razmer).filter(
                Razmer.nazvanie == name
            ).first()

            if not existing:
                session.add(Razmer(nazvanie=name, poryadok=order))
                added += 1

        session.commit()
        print(f"  Добавлено размеров: {added}")


def main():
    print("="*60)
    print("ПРИМЕРЫ РАБОТЫ С БАЗОЙ ДАННЫХ WOOKIEE")
    print("="*60)

    example_1_read_all()
    example_2_add_data()
    example_3_filter()
    example_6_bulk_insert()
    example_5_relationships()

    print("\n" + "="*60)
    print("Примеры выполнены!")
    print("="*60)


if __name__ == "__main__":
    main()
