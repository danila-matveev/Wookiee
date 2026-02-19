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
from scripts.config import NOTION_TOKEN, NOTION_DATABASE_ID


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
# MARKDOWN → NOTION BLOCKS
# =============================================================================

def _parse_inline(text):
    """Парсит bold-маркеры в rich_text массив Notion."""
    parts = []
    segments = re.split(r'(\*\*[^*]+\*\*)', text)
    for seg in segments:
        if seg.startswith('**') and seg.endswith('**'):
            parts.append({
                "type": "text",
                "text": {"content": seg[2:-2]},
                "annotations": {
                    "bold": True, "italic": False, "strikethrough": False,
                    "underline": False, "code": False, "color": "default"
                }
            })
        elif seg:
            parts.append({"type": "text", "text": {"content": seg}})
    return parts if parts else [{"type": "text", "text": {"content": text}}]


def md_to_notion_blocks(md_text):
    """Конвертирует Markdown-отчёт в массив Notion-блоков."""
    blocks = []
    lines = md_text.split('\n')
    i = 0
    table_rows = []
    in_table = False
    in_code_block = False
    code_content = []

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        num_cols = max(len(r) for r in table_rows)
        notion_rows = []
        for row in table_rows:
            while len(row) < num_cols:
                row.append('')
            cells_rt = [
                [{"type": "text", "text": {"content": cell.replace('**', '')[:2000]}}]
                for cell in row[:num_cols]
            ]
            notion_rows.append({
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": cells_rt}
            })
        # Notion API ограничивает таблицу 100 строками.
        # Разбиваем: первый чанк 100 строк (вкл. заголовок),
        # остальные — 99 строк данных + копия заголовка = 100.
        MAX_ROWS = 100
        header_row = notion_rows[0] if notion_rows else None
        first_chunk = notion_rows[:MAX_ROWS]
        blocks.append({
            "object": "block",
            "type": "table",
            "table": {
                "table_width": num_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": first_chunk
            }
        })
        remaining = notion_rows[MAX_ROWS:]
        while remaining:
            chunk = remaining[:MAX_ROWS - 1]  # 99 строк + 1 заголовок = 100
            remaining = remaining[MAX_ROWS - 1:]
            if header_row:
                chunk = [header_row] + chunk
            blocks.append({
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": num_cols,
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": chunk
                }
            })
        table_rows = []

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": '\n'.join(code_content)[:2000]}}],
                        "language": "plain text"
                    }
                })
                code_content = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_content.append(line)
            i += 1
            continue

        # Tables
        if '|' in line and line.strip().startswith('|'):
            stripped = line.strip()
            if re.match(r'^[\|\-\s:]+$', stripped):
                i += 1
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)

            next_is_table = (
                i + 1 < len(lines)
                and lines[i + 1].strip().startswith('|')
                and '|' in lines[i + 1]
            )
            if not next_is_table:
                flush_table()
                in_table = False
            i += 1
            continue

        # Headings
        if line.startswith('### '):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:].strip()[:2000]}}]}
            })
            i += 1
            continue
        if line.startswith('## '):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:].strip()[:2000]}}]}
            })
            i += 1
            continue
        if line.startswith('# '):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:].strip()[:2000]}}]}
            })
            i += 1
            continue

        # Divider
        if line.strip() == '---':
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        # Bullet list
        if line.strip().startswith('- '):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _parse_inline(line.strip()[2:])}
            })
            i += 1
            continue

        # Numbered list (1. 2. etc.)
        if re.match(r'^\d+\.\s', line.strip()):
            text = re.sub(r'^\d+\.\s*', '', line.strip())
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _parse_inline(text)}
            })
            i += 1
            continue

        # Empty line
        if line.strip() == '':
            i += 1
            continue

        # Paragraph
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _parse_inline(line)}
        })
        i += 1

    return blocks


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
