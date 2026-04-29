"""Генератор docs/TOOLS_CATALOG.md из реестра Supabase (tools).

Supabase — единственный источник истины. Этот скрипт рендерит MD по данным из БД.
Запускается вручную или автоматически из /tool-register после UPSERT.

    python scripts/generate_tools_catalog.py
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv('database/sku/.env')

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / 'docs' / 'TOOLS_CATALOG.md'

CATEGORY_ORDER = ['analytics', 'content', 'publishing', 'infra', 'planning', 'team']
CATEGORY_LABELS = {
    'analytics': 'Аналитика',
    'content': 'Контент',
    'publishing': 'Публикация',
    'infra': 'Инфраструктура',
    'planning': 'Планирование',
    'team': 'Команда',
}
TYPE_LABELS = {'skill': 'Скилл', 'service': 'Сервис', 'script': 'Скрипт'}
STATUS_ICONS = {'active': '✅', 'deprecated': '⚠️', 'draft': '🛠️'}


def _connect():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'postgres'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
    )


def _fetch_tools() -> list[dict]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT slug, display_name, type, category, description, how_it_works,
                   status, version, run_command, data_sources, depends_on, output_targets,
                   total_runs, last_run_at, last_status, updated_at
            FROM tools
            WHERE status != 'archived' OR status IS NULL
            ORDER BY category, type, slug
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _fmt_list(values: list | None) -> str:
    if not values:
        return '—'
    return ', '.join(str(v) for v in values)


def _fmt_last_run(tool: dict) -> str:
    if not tool.get('last_run_at'):
        return '—'
    dt = tool['last_run_at']
    icon = STATUS_ICONS.get(tool.get('last_status') or '', '')
    return f"{dt.strftime('%Y-%m-%d %H:%M')} {icon}".strip()


def _render_tool(tool: dict) -> list[str]:
    status_icon = STATUS_ICONS.get(tool.get('status') or 'active', '')
    version = f" `{tool['version']}`" if tool.get('version') else ''
    lines = [
        f"### {status_icon} `{tool['slug']}` — {tool['display_name']}{version}",
        '',
    ]
    if tool.get('description'):
        lines += [tool['description'], '']
    if tool.get('how_it_works'):
        lines += [f"**Как работает:** {tool['how_it_works']}", '']

    meta_rows = [
        ('Тип', TYPE_LABELS.get(tool.get('type', ''), tool.get('type', '—'))),
        ('Источники данных', _fmt_list(tool.get('data_sources'))),
        ('Зависимости', _fmt_list(tool.get('depends_on'))),
        ('Результат идёт в', _fmt_list(tool.get('output_targets'))),
        ('Команда запуска', f"`{tool['run_command']}`" if tool.get('run_command') else '—'),
        ('Запусков (всего)', str(tool.get('total_runs') or 0)),
        ('Последний запуск', _fmt_last_run(tool)),
    ]
    lines.append('| Поле | Значение |')
    lines.append('|---|---|')
    for k, v in meta_rows:
        lines.append(f"| {k} | {v} |")
    lines += ['', '---', '']
    return lines


def _render_summary_table(tools: list[dict]) -> list[str]:
    lines = [
        '## Сводная таблица',
        '',
        '| # | Инструмент | Тип | Категория | Статус | Версия | Последний запуск |',
        '|---|---|---|---|---|---|---|',
    ]
    for i, t in enumerate(tools, 1):
        icon = STATUS_ICONS.get(t.get('status') or 'active', '')
        lines.append(
            f"| {i} | `{t['slug']}` | {TYPE_LABELS.get(t.get('type', ''), t.get('type', '—'))} "
            f"| {CATEGORY_LABELS.get(t.get('category', ''), t.get('category', '—'))} "
            f"| {icon} {t.get('status', '—')} | {t.get('version') or '—'} | {_fmt_last_run(t)} |"
        )
    lines.append('')
    return lines


def render(tools: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for t in tools:
        cat = t.get('category') or 'infra'
        by_cat.setdefault(cat, []).append(t)

    now = datetime.now().strftime('%Y-%m-%d %H:%M МСК')
    lines = [
        '# Каталог инструментов Wookiee',
        '',
        f'> Автогенерировано `scripts/generate_tools_catalog.py` из Supabase `tools` — {now}.',
        '> **Не редактируй вручную.** Источник истины — Supabase. Обновляй через `/tool-register`, затем перегенерируй файл.',
        '',
        f'Всего инструментов: **{len(tools)}**. Категории: {", ".join(f"{CATEGORY_LABELS.get(c, c)} — {len(by_cat.get(c, []))}" for c in CATEGORY_ORDER if by_cat.get(c))}.',
        '',
    ]

    for cat in CATEGORY_ORDER:
        bucket = by_cat.get(cat, [])
        if not bucket:
            continue
        lines.append(f'## {CATEGORY_LABELS[cat]}')
        lines.append('')
        for tool in bucket:
            lines.extend(_render_tool(tool))

    lines.extend(_render_summary_table(tools))
    lines.append('')
    lines.append(f'<sub>Сгенерировано автоматически {now}. Команда: `python scripts/generate_tools_catalog.py`.</sub>')
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    tools = _fetch_tools()
    if not tools:
        raise SystemExit('Реестр пуст — нечего рендерить.')
    content = render(tools)
    OUTPUT_PATH.write_text(content, encoding='utf-8')
    print(f'✅ {OUTPUT_PATH.relative_to(REPO_ROOT)} — {len(tools)} инструментов записано.')


if __name__ == '__main__':
    main()
