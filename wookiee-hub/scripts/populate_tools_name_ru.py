# scripts/populate_tools_name_ru.py
"""Заполняет поле name_ru в таблице tools на основе TOOLS_CATALOG.md.

Запуск: python scripts/populate_tools_name_ru.py
"""
from __future__ import annotations

import re
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv('database/sku/.env')

CATALOG_PATH = Path(__file__).parent.parent / 'docs' / 'TOOLS_CATALOG.md'

# Маппинг slug → русское название
# Берём из заголовков каталога: ### ✅ `slug` — Русское название
def parse_catalog(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    pattern = re.compile(r'###\s+\S+\s+`([^`]+)`\s+[—–]\s+(.+)')
    for match in pattern.finditer(text):
        slug, name_ru = match.group(1).strip(), match.group(2).strip()
        # Убираем суффикс версии типа ` v2` или ` 2.0.0`
        name_ru = re.sub(r'\s+`[\d.]+`$', '', name_ru)
        mapping[slug] = name_ru
    return mapping


def main() -> None:
    catalog_text = CATALOG_PATH.read_text(encoding='utf-8')
    mapping = parse_catalog(catalog_text)
    print(f'Найдено {len(mapping)} тулзов в каталоге')

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'postgres'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
    )
    try:
        cur = conn.cursor()
        updated = 0
        for slug, name_ru in mapping.items():
            cur.execute(
                'update tools set name_ru = %s where slug = %s and name_ru is null',
                (name_ru, slug)
            )
            updated += cur.rowcount
        conn.commit()
        print(f'Обновлено: {updated} строк')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
