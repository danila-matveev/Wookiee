#!/usr/bin/env python3
"""
Миграция: Синхронизация статусов цветов из Excel в базу данных.

Читает статусы из таблицы "Аналитики цветов" в Excel
и обновляет поле status_id в таблице cveta.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from scripts.db_connection import engine, execute_sql
from sqlalchemy import text


def get_status_mapping():
    """Получает маппинг статусов из БД."""
    result = execute_sql("SELECT id, nazvanie FROM statusy")
    return {row[1]: row[0] for row in result}


def migrate():
    """Выполняет синхронизацию статусов."""
    print("=" * 60)
    print("МИГРАЦИЯ: Синхронизация статусов цветов")
    print("=" * 60)

    # Путь к Excel
    excel_path = Path(__file__).parent.parent.parent.parent / 'Спецификации.xlsx'
    if not excel_path.exists():
        # Попробуем в другом месте
        excel_path = Path(__file__).parent.parent.parent / 'Спецификации.xlsx'

    if not excel_path.exists():
        print(f"❌ Файл не найден: {excel_path}")
        return

    print(f"📂 Читаю Excel: {excel_path.name}")

    # Читаем данные
    df = pd.read_excel(excel_path, sheet_name='Аналитики цветов')
    print(f"   Строк в Excel: {len(df)}")

    # Получаем маппинг статусов
    status_map = get_status_mapping()
    print(f"   Статусов в БД: {len(status_map)}")
    print(f"   Статусы: {list(status_map.keys())}")

    # Получаем текущие цвета из БД
    current_colors = execute_sql("""
        SELECT c.id, c.color_code, c.status_id, s.nazvanie
        FROM cveta c
        LEFT JOIN statusy s ON c.status_id = s.id
    """)
    db_colors = {row[1]: {'id': row[0], 'status_id': row[2], 'status_name': row[3]} for row in current_colors}
    print(f"   Цветов в БД: {len(db_colors)}")

    # Готовим обновления
    updates = []
    for idx, row in df.iterrows():
        color_code = str(row.get('Color code', '')).strip()
        excel_status = str(row.get('Статус', '')).strip()

        if not color_code or color_code == 'nan' or not excel_status or excel_status == 'nan':
            continue

        if color_code in db_colors:
            db_info = db_colors[color_code]
            current_status = db_info['status_name']

            if excel_status in status_map:
                new_status_id = status_map[excel_status]

                if db_info['status_id'] != new_status_id:
                    updates.append({
                        'color_code': color_code,
                        'old_status': current_status,
                        'new_status': excel_status,
                        'new_status_id': new_status_id,
                        'cvet_id': db_info['id']
                    })

    print(f"\n📊 Найдено изменений: {len(updates)}")

    if not updates:
        print("✅ Всё синхронизировано!")
        return

    # Группируем по типу изменения
    changes_by_type = {}
    for upd in updates:
        key = f"{upd['old_status']} → {upd['new_status']}"
        if key not in changes_by_type:
            changes_by_type[key] = []
        changes_by_type[key].append(upd['color_code'])

    print("\n📝 Изменения по типам:")
    for change_type, codes in sorted(changes_by_type.items()):
        print(f"   {change_type}: {len(codes)} шт ({', '.join(codes[:5])}{'...' if len(codes) > 5 else ''})")

    # Применяем изменения
    print("\n⚡ Применяю изменения...")
    with engine.begin() as conn:
        for upd in updates:
            conn.execute(text("""
                UPDATE cveta
                SET status_id = :status_id, updated_at = CURRENT_TIMESTAMP
                WHERE id = :cvet_id
            """), {'status_id': upd['new_status_id'], 'cvet_id': upd['cvet_id']})

    print(f"✅ Обновлено {len(updates)} записей")

    # Проверяем результат
    print("\n📊 Статистика после обновления:")
    result = execute_sql("""
        SELECT s.nazvanie, COUNT(*) as cnt
        FROM cveta c
        LEFT JOIN statusy s ON c.status_id = s.id
        GROUP BY s.nazvanie
        ORDER BY cnt DESC
    """)
    for row in result:
        status = row[0] or 'NULL'
        print(f"   {status:20} {row[1]:5} цветов")


if __name__ == '__main__':
    migrate()
