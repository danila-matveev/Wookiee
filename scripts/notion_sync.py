"""
Синхронизация аналитических отчётов с Notion.

Логика:
- Если страница с таким периодом уже существует → обновляем (удаляем старый контент, заливаем новый)
- Если нет → создаём новую страницу

Использование:
  # Из командной строки:
  python scripts/notion_sync.py --file reports/2026-02-01_2026-02-05_analytics.md

  # Из кода (period_analytics.py):
  from scripts.notion_sync import sync_report_to_notion
  sync_report_to_notion("2026-02-01", "2026-02-05", report_md_text)
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

# Добавляем корень проекта
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import NOTION_TOKEN, NOTION_DATABASE_ID


API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# =============================================================================
# NOTION API
# =============================================================================

def _notion_request(method, endpoint, payload=None):
    """Выполняет запрос к Notion API."""
    url = f"{API_BASE}/{endpoint}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {NOTION_TOKEN}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Notion API error {e.code}: {body}")


def _find_existing_page(start_date, end_date, source=None, title=None):
    """Ищет страницу в базе с совпадающим периодом. Если указан title — ищет по title."""
    if title:
        # Поиск по title — надёжнее для разных типов отчётов за одинаковый период
        payload = {
            "filter": {
                "property": "Name",
                "title": {"equals": title}
            }
        }
    else:
        conditions = [
            {"property": "Период начала", "date": {"equals": start_date}},
            {"property": "Период конца", "date": {"equals": end_date}},
        ]
        if source:
            conditions.append({"property": "Источник", "select": {"equals": source}})
        payload = {"filter": {"and": conditions}}
    result = _notion_request("POST", f"databases/{NOTION_DATABASE_ID}/query", payload)
    pages = result.get("results", [])
    return pages[0] if pages else None


def _delete_page_content(page_id):
    """Удаляет все блоки со страницы (для перезаписи)."""
    result = _notion_request("GET", f"blocks/{page_id}/children?page_size=100")
    for block in result.get("results", []):
        _notion_request("DELETE", f"blocks/{block['id']}")


def _append_blocks(page_id, blocks):
    """Добавляет блоки на страницу пакетами по 100."""
    for i in range(0, len(blocks), 100):
        batch = blocks[i:i + 100]
        _notion_request("PATCH", f"blocks/{page_id}/children", {"children": batch})


# =============================================================================
# MARKDOWN → NOTION BLOCKS (shared implementation)
# =============================================================================

from shared.notion_blocks import parse_inline as _parse_inline  # noqa: E402
from shared.notion_blocks import md_to_notion_blocks  # noqa: E402


# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ СИНХРОНИЗАЦИИ
# =============================================================================

def sync_report_to_notion(start_date, end_date, report_md, source="Скрипт", title=None):
    """
    Синхронизирует отчёт с Notion.

    Если страница с таким периодом/title есть → удаляет содержимое и перезаписывает.
    Если нет → создаёт новую страницу.

    Args:
        start_date: Начало периода (YYYY-MM-DD)
        end_date: Конец периода (YYYY-MM-DD)
        report_md: Текст отчёта в формате Markdown
        source: Источник отчёта ("Скрипт" или "Telegram Bot")
        title: Кастомный заголовок страницы (если не указан — авто из дат)

    Returns:
        URL страницы в Notion
    """
    if not title:
        start_fmt = ".".join(reversed(start_date.split("-")))
        end_fmt = ".".join(reversed(end_date.split("-")))
        title = f"Аналитика {start_fmt} — {end_fmt}"
    blocks = md_to_notion_blocks(report_md)

    print(f"\n[Notion] Поиск существующей страницы: \"{title}\"...")
    existing = _find_existing_page(start_date, end_date, source=source, title=title)

    if existing:
        page_id = existing["id"]
        page_url = existing["url"]
        print(f"[Notion] Найдена существующая страница, обновляем...")

        # Удаляем старый контент
        _delete_page_content(page_id)

        # Обновляем свойства
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Статус": {"select": {"name": "Актуальный"}},
        }
        # Добавляем источник если указан
        if source:
            properties["Источник"] = {"select": {"name": source}}

        _notion_request("PATCH", f"pages/{page_id}", {"properties": properties})

        # Заливаем новый контент
        _append_blocks(page_id, blocks)
        print(f"[Notion] Страница обновлена: {page_url}")
        return page_url
    else:
        print(f"[Notion] Создаём новую страницу...")

        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Период начала": {"date": {"start": start_date}},
            "Период конца": {"date": {"start": end_date}},
            "Статус": {"select": {"name": "Актуальный"}},
        }
        # Добавляем источник если указан
        if source:
            properties["Источник"] = {"select": {"name": source}}

        page_payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": properties,
            "children": blocks[:100]
        }

        result = _notion_request("POST", "pages", page_payload)
        page_id = result["id"]
        page_url = result["url"]

        # Дозаписываем оставшиеся блоки
        if len(blocks) > 100:
            _append_blocks(page_id, blocks[100:])

        print(f"[Notion] Страница создана: {page_url}")
        return page_url


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Синхронизация отчёта с Notion')
    parser.add_argument('--file', required=True, help='Путь к .md файлу отчёта')
    args = parser.parse_args()

    filepath = args.file
    if not os.path.isabs(filepath):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(project_root, filepath)

    if not os.path.exists(filepath):
        print(f"Файл не найден: {filepath}")
        sys.exit(1)

    # Извлекаем даты из имени файла
    basename = os.path.basename(filepath)
    # Периодный отчёт: YYYY-MM-DD_YYYY-MM-DD_analytics.md
    match = re.match(r'(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})_analytics', basename)
    if match:
        start_date, end_date = match.group(1), match.group(2)
    else:
        # Дневной отчёт: YYYY-MM-DD_daily_analytics.md
        match_daily = re.match(r'(\d{4}-\d{2}-\d{2})_daily_analytics', basename)
        if match_daily:
            start_date = end_date = match_daily.group(1)
        else:
            print(f"Не удалось извлечь даты из имени файла: {basename}")
            print("Ожидаемый формат: YYYY-MM-DD_YYYY-MM-DD_analytics.md или YYYY-MM-DD_daily_analytics.md")
            sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        report_md = f.read()

    url = sync_report_to_notion(start_date, end_date, report_md)
    print(f"\nГотово! {url}")


if __name__ == "__main__":
    main()
