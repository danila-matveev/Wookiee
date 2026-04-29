#!/usr/bin/env python3
"""
Wookiee Database CLI - главная команда для работы с базой данных.

Использование:
    python db.py status          # Статус подключения
    python db.py query "SQL"     # Выполнить SQL запрос
    python db.py colors          # Статистика цветов
    python db.py models          # Список моделей
    python db.py import-excel    # Импорт из Excel
    python db.py sync-colors     # Синхронизация статусов цветов
    python db.py backup          # Создать SQL backup
"""

import sys
import argparse
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from tabulate import tabulate
from config.database import (
    engine, execute_sql, test_connection, get_table_counts, config
)
from sqlalchemy import text


def cmd_status(args):
    """Показывает статус подключения и статистику."""
    if not test_connection():
        return 1

    print("\nСТАТИСТИКА ТАБЛИЦ:")
    print("-" * 45)

    counts = get_table_counts()
    data = [[table, f"{count:,}"] for _, table, count in counts]
    print(tabulate(data, headers=['Таблица', 'Записей'], tablefmt='simple'))

    total = sum(c for _, _, c in counts)
    print(f"\nВсего записей: {total:,}")
    return 0


def cmd_query(args):
    """Выполняет SQL запрос."""
    sql = args.sql
    print(f"SQL: {sql[:80]}{'...' if len(sql) > 80 else ''}\n")

    try:
        with engine.connect() as conn:
            res = conn.execute(text(sql))
            columns = list(res.keys())
            rows = res.fetchall()

        if rows:
            print(tabulate(rows, headers=columns, tablefmt='psql'))
            print(f"\nВсего строк: {len(rows)}")
        else:
            print("Запрос выполнен (нет результата)")
    except Exception as e:
        print(f"Ошибка: {e}")
        return 1

    return 0


def cmd_tables(args):
    """Показывает список таблиц с размерами."""
    sql = """
    SELECT
        t.table_name,
        pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name))) as size,
        (SELECT COUNT(*) FROM information_schema.columns c
         WHERE c.table_name = t.table_name AND c.table_schema = 'public') as columns
    FROM information_schema.tables t
    WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
    ORDER BY t.table_name
    """
    result = execute_sql(sql)
    print(tabulate(result, headers=['Таблица', 'Размер', 'Колонок'], tablefmt='simple'))
    return 0


def cmd_colors(args):
    """Показывает статистику цветов."""
    print("=" * 50)
    print("СТАТИСТИКА ЦВЕТОВ")
    print("=" * 50)

    # По статусам
    sql = """
    SELECT
        COALESCE(s.nazvanie, 'Без статуса') as status,
        COUNT(*) as count
    FROM cveta c
    LEFT JOIN statusy s ON c.status_id = s.id
    GROUP BY s.nazvanie
    ORDER BY count DESC
    """
    result = execute_sql(sql)
    print("\nПо статусам:")
    print(tabulate(result, headers=['Статус', 'Кол-во'], tablefmt='simple'))

    # Топ цветов по артикулам
    sql = """
    SELECT
        c.color_code,
        c.cvet,
        COALESCE(s.nazvanie, '-') as status,
        COUNT(DISTINCT a.id) as artikulov
    FROM cveta c
    LEFT JOIN statusy s ON c.status_id = s.id
    LEFT JOIN artikuly a ON a.cvet_id = c.id
    GROUP BY c.id, c.color_code, c.cvet, s.nazvanie
    ORDER BY artikulov DESC
    LIMIT 15
    """
    result = execute_sql(sql)
    print("\nТоп-15 цветов по артикулам:")
    print(tabulate(result, headers=['Код', 'Цвет', 'Статус', 'Артикулов'], tablefmt='simple'))

    return 0


def cmd_models(args):
    """Показывает список моделей."""
    sql = """
    SELECT
        mo.kod as model,
        COALESCE(mo.tip_kollekcii, '-') as kollekciya,
        COUNT(DISTINCT m.id) as variaciy,
        COUNT(DISTINCT a.id) as artikulov,
        COUNT(DISTINCT t.id) as sku
    FROM modeli_osnova mo
    LEFT JOIN modeli m ON m.model_osnova_id = mo.id
    LEFT JOIN artikuly a ON a.model_id = m.id
    LEFT JOIN tovary t ON t.artikul_id = a.id
    GROUP BY mo.id, mo.kod, mo.tip_kollekcii
    ORDER BY sku DESC
    """
    result = execute_sql(sql)
    print(tabulate(result, headers=['Модель', 'Коллекция', 'Вариаций', 'Артикулов', 'SKU'], tablefmt='simple'))
    return 0


def cmd_import_excel(args):
    """Импорт данных из Excel."""
    print("Запуск импорта из Excel...")
    print("-" * 40)

    try:
        from scripts.migrate_data import migrate_all
        migrate_all()
        print("\nИмпорт завершен!")
    except ImportError:
        print("Ошибка: не найден скрипт migrate_data.py")
        print("Путь: scripts/migrate_data.py")
        return 1
    except Exception as e:
        print(f"Ошибка импорта: {e}")
        return 1

    return 0


def cmd_sync_colors(args):
    """Синхронизирует статусы цветов из Excel."""
    print("Синхронизация статусов цветов...")
    print("-" * 40)

    try:
        from scripts.migrations.m002_sync_color_statuses import migrate
        migrate()
    except ImportError:
        # Пробуем альтернативный путь
        try:
            from scripts.sync_color_statuses import sync_and_update
            sync_and_update()
        except ImportError:
            print("Ошибка: не найден скрипт синхронизации")
            return 1
    except Exception as e:
        print(f"Ошибка: {e}")
        return 1

    return 0


def cmd_backup(args):
    """Создает SQL backup базы данных."""
    from datetime import datetime

    output_file = args.output or f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    print(f"Создание backup в {output_file}...")

    tables = [
        'kategorii', 'kollekcii', 'statusy', 'razmery', 'importery', 'fabriki',
        'cveta', 'modeli_osnova', 'modeli', 'artikuly', 'tovary',
        'skleyki_wb', 'skleyki_ozon'
    ]

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("-- Wookiee SKU Database Backup\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n")
            f.write(f"-- Host: {config.host}\n\n")

            for table in tables:
                try:
                    # Получаем данные
                    rows = execute_sql(f"SELECT * FROM {table}")
                    if not rows:
                        continue

                    # Получаем колонки
                    with engine.connect() as conn:
                        result = conn.execute(text(f"SELECT * FROM {table} LIMIT 1"))
                        columns = list(result.keys())

                    f.write(f"\n-- Table: {table}\n")
                    f.write(f"TRUNCATE TABLE {table} CASCADE;\n")

                    for row in rows:
                        values = []
                        for v in row:
                            if v is None:
                                values.append('NULL')
                            elif isinstance(v, str):
                                values.append(f"'{v.replace(chr(39), chr(39)+chr(39))}'")
                            elif isinstance(v, bool):
                                values.append('TRUE' if v else 'FALSE')
                            else:
                                values.append(str(v))

                        f.write(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(values)});\n")

                except Exception as e:
                    f.write(f"-- Error exporting {table}: {e}\n")

        print(f"Backup создан: {output_file}")

    except Exception as e:
        print(f"Ошибка создания backup: {e}")
        return 1

    return 0


def cmd_views(args):
    """Показывает список VIEW в базе данных."""
    sql = """
    SELECT table_name as view_name
    FROM information_schema.views
    WHERE table_schema = 'public'
    ORDER BY table_name
    """
    result = execute_sql(sql)

    if result:
        print("VIEW в базе данных:")
        print("-" * 40)
        for row in result:
            print(f"  {row[0]}")
    else:
        print("VIEW не найдены")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Wookiee Database CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python db.py status
  python db.py query "SELECT * FROM cveta WHERE status_id = 1 LIMIT 10"
  python db.py colors
  python db.py models
  python db.py import-excel
  python db.py backup --output my_backup.sql
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Команда')

    # status
    subparsers.add_parser('status', help='Статус подключения и статистика')

    # query
    query_parser = subparsers.add_parser('query', help='Выполнить SQL запрос')
    query_parser.add_argument('sql', help='SQL запрос')

    # tables
    subparsers.add_parser('tables', help='Список таблиц с размерами')

    # colors
    subparsers.add_parser('colors', help='Статистика цветов')

    # models
    subparsers.add_parser('models', help='Список моделей')

    # import-excel
    subparsers.add_parser('import-excel', help='Импорт данных из Excel')

    # sync-colors
    subparsers.add_parser('sync-colors', help='Синхронизация статусов цветов из Excel')

    # backup
    backup_parser = subparsers.add_parser('backup', help='Создать SQL backup')
    backup_parser.add_argument('--output', '-o', help='Имя выходного файла')

    # views
    subparsers.add_parser('views', help='Список VIEW в базе данных')

    args = parser.parse_args()

    if not args.command:
        # По умолчанию показываем status
        return cmd_status(args)

    commands = {
        'status': cmd_status,
        'query': cmd_query,
        'tables': cmd_tables,
        'colors': cmd_colors,
        'models': cmd_models,
        'import-excel': cmd_import_excel,
        'sync-colors': cmd_sync_colors,
        'backup': cmd_backup,
        'views': cmd_views,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
