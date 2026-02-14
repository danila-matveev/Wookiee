#!/usr/bin/env python3
"""
Интерактивная консоль для работы с базой данных Wookiee в Supabase.

Запуск:
    python3 scripts/db_shell.py

Примеры команд в консоли:
    >>> kategorii = session.query(Kategoriya).all()
    >>> for k in kategorii: print(k.nazvanie)
    >>> session.query(Tovar).count()
"""

import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Импорты для работы с БД
from config.database import get_session, engine
from database.models import (
    Base,
    Kategoriya,
    Kollekciya,
    Status,
    Razmer,
    Importer,
    Fabrika,
    Cvet,
    ModelOsnova,
    Model,
    Artikul,
    Tovar,
    SkleykaWB,
    SkleykaOzon,
    IstoriyaIzmeneniy
)
from sqlalchemy import text

def show_stats(session):
    """Показать статистику базы данных"""
    print("\n" + "="*50)
    print("СТАТИСТИКА БАЗЫ ДАННЫХ WOOKIEE")
    print("="*50)

    tables = [
        ("Категории", Kategoriya),
        ("Коллекции", Kollekciya),
        ("Статусы", Status),
        ("Размеры", Razmer),
        ("Импортеры", Importer),
        ("Фабрики", Fabrika),
        ("Цвета", Cvet),
        ("Модели основы", ModelOsnova),
        ("Модели", Model),
        ("Артикулы", Artikul),
        ("Товары/SKU", Tovar),
        ("Склейки WB", SkleykaWB),
        ("Склейки Ozon", SkleykaOzon),
    ]

    for name, model in tables:
        count = session.query(model).count()
        print(f"  {name}: {count}")

    print("="*50)

def show_help():
    """Показать справку"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          ИНТЕРАКТИВНАЯ КОНСОЛЬ WOOKIEE DATABASE              ║
╠══════════════════════════════════════════════════════════════╣
║  Доступные объекты:                                          ║
║    session    - сессия SQLAlchemy для запросов               ║
║    Kategoriya, Kollekciya, Status, Razmer                    ║
║    Importer, Fabrika, Cvet, ModelOsnova                      ║
║    Model, Artikul, Tovar, SkleykaWB, SkleykaOzon             ║
║                                                              ║
║  Функции:                                                    ║
║    stats()    - показать статистику БД                       ║
║    help_db()  - показать эту справку                         ║
║                                                              ║
║  Примеры:                                                    ║
║    >>> session.query(Kategoriya).all()                       ║
║    >>> session.query(Tovar).filter(Tovar.barkod == '123')    ║
║    >>> session.query(Model).count()                          ║
║    >>> new = Kategoriya(nazvanie='Test')                     ║
║    >>> session.add(new); session.commit()                    ║
║                                                              ║
║  Выход: exit() или Ctrl+D                                    ║
╚══════════════════════════════════════════════════════════════╝
""")

def main():
    print("\nПодключение к Supabase...")

    try:
        session = get_session()
        # Проверка подключения
        session.execute(text("SELECT 1"))
        print("✓ Подключено к Supabase!")

        # Показываем статистику
        show_stats(session)
        show_help()

        # Создаем удобные алиасы
        stats = lambda: show_stats(session)
        help_db = show_help

        # Запускаем интерактивную консоль
        import code

        # Локальные переменные для консоли
        local_vars = {
            'session': session,
            'text': text,
            'Kategoriya': Kategoriya,
            'Kollekciya': Kollekciya,
            'Status': Status,
            'Razmer': Razmer,
            'Importer': Importer,
            'Fabrika': Fabrika,
            'Cvet': Cvet,
            'ModelOsnova': ModelOsnova,
            'Model': Model,
            'Artikul': Artikul,
            'Tovar': Tovar,
            'SkleykaWB': SkleykaWB,
            'SkleykaOzon': SkleykaOzon,
            'IstoriyaIzmeneniy': IstoriyaIzmeneniy,
            'stats': stats,
            'help_db': help_db,
        }

        code.interact(local=local_vars, banner="")

    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")
        return 1
    finally:
        if 'session' in locals():
            session.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
