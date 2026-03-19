#!/usr/bin/env python3
"""
CLI tool for testing knowledge base search.

Single query:
    python -m services.knowledge_base.scripts.search_cli "как продвигать карточки"
    python -m services.knowledge_base.scripts.search_cli "воронка продаж" --module 3 --limit 3

Interactive mode:
    python -m services.knowledge_base.scripts.search_cli
    python -m services.knowledge_base.scripts.search_cli --interactive

Stats:
    python -m services.knowledge_base.scripts.search_cli --stats
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.knowledge_base.search import search_knowledge
from services.knowledge_base.store import KnowledgeStore

MODULE_NAMES = {
    "1": "Продвижение карточек",
    "2": "Юнит-экономика",
    "3": "Воронка продаж, CTR, ЦА",
    "4": "Контент и органика",
    "5": "Реклама",
    "6": "Аналитика",
    "7": "Масштабирование",
    "8": "Автоматизация",
    "processes": "Управление процессами",
}


def print_stats():
    """Print knowledge base statistics."""
    store = KnowledgeStore()
    stats = store.get_stats()

    print("\n" + "=" * 60)
    print("  БАЗА ЗНАНИЙ — СТАТИСТИКА")
    print("=" * 60)
    print(f"\n  Всего чанков: {stats['total_chunks']}")
    print(f"  Файлов:       {stats['unique_files']}")
    print(f"\n  По модулям:")
    for mod, count in sorted(stats.get("by_module", {}).items(), key=lambda x: x[0]):
        name = MODULE_NAMES.get(mod, mod)
        bar = "█" * (count // 50)
        print(f"    Модуль {mod:>10s}: {count:>5d} {bar}  ({name})")
    print(f"\n  По типу файлов:")
    for ft, count in stats.get("by_file_type", {}).items():
        print(f"    {ft:>6s}: {count}")
    print()


async def run_search(query: str, limit: int, module: str = None, content_type: str = None):
    """Run a single search and print results."""
    results = await search_knowledge(
        query=query,
        limit=limit,
        module=module,
        content_type=content_type,
        min_score=0.3,
    )

    if not results:
        print("  Ничего не найдено.")
        return

    print(f"\n  Найдено {len(results)} результатов для: «{query}»\n")

    for i, r in enumerate(results, 1):
        score = r["score"]
        # Color-code relevance
        if score >= 0.75:
            relevance = "ВЫСОКАЯ"
        elif score >= 0.55:
            relevance = "СРЕДНЯЯ"
        else:
            relevance = "НИЗКАЯ"

        mod = r["module"]
        mod_name = MODULE_NAMES.get(mod, mod)

        print(f"  ┌─ Результат {i}  |  Релевантность: {score:.2f} ({relevance})")
        print(f"  │  Модуль: {mod} — {mod_name}")
        print(f"  │  Файл:   {r['file_name']}")
        print(f"  │  Тип:    {r['content_type']}  |  Чанк #{r['chunk_index']}")
        print(f"  │")
        # Show text, indented
        text = r["text"]
        if len(text) > 600:
            text = text[:600] + "…"
        for line in text.split("\n"):
            print(f"  │  {line}")
        print(f"  └{'─' * 70}")
        print()


async def interactive_mode(limit: int):
    """Interactive search loop."""
    print("\n" + "=" * 60)
    print("  БАЗА ЗНАНИЙ WILDBERRIES — ИНТЕРАКТИВНЫЙ ПОИСК")
    print("=" * 60)
    print()
    print("  Команды:")
    print("    <запрос>            — поиск по всей базе")
    print("    /m <N> <запрос>     — поиск в модуле N (1-8 или processes)")
    print("    /n <N>              — изменить кол-во результатов (по умолч. 5)")
    print("    /stats              — статистика базы")
    print("    /help               — справка")
    print("    /exit или Ctrl+C    — выход")
    print()

    current_module = None

    while True:
        try:
            prompt = "  KB"
            if current_module:
                prompt += f" [модуль {current_module}]"
            prompt += " > "
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  До свидания!")
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit", "/q"):
            print("  До свидания!")
            break

        if user_input == "/stats":
            print_stats()
            continue

        if user_input == "/help":
            print("  /m <N> <запрос>  — поиск в модуле N")
            print("  /m clear         — сбросить фильтр модуля")
            print("  /n <N>           — кол-во результатов")
            print("  /stats           — статистика базы")
            print("  /exit            — выход")
            continue

        if user_input.startswith("/n "):
            try:
                limit = int(user_input[3:].strip())
                print(f"  Количество результатов: {limit}")
            except ValueError:
                print("  Ошибка: /n <число>")
            continue

        if user_input.startswith("/m "):
            parts = user_input[3:].strip().split(None, 1)
            if parts[0] == "clear":
                current_module = None
                print("  Фильтр модуля сброшен")
                continue
            if len(parts) >= 2:
                current_module = parts[0]
                query = parts[1]
            else:
                current_module = parts[0]
                print(f"  Фильтр модуля: {current_module} ({MODULE_NAMES.get(current_module, '?')})")
                continue
        else:
            query = user_input

        await run_search(query, limit=limit, module=current_module)


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base — поиск по базе знаний")
    parser.add_argument("query", nargs="?", help="Поисковый запрос (без него — интерактивный режим)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Интерактивный режим")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Кол-во результатов")
    parser.add_argument("--module", "-m", type=str, default=None, help="Фильтр по модулю")
    parser.add_argument("--content-type", "-t", type=str, default=None)
    parser.add_argument("--stats", "-s", action="store_true", help="Показать статистику базы")
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    if args.stats:
        print_stats()
        return

    if args.query and not args.interactive:
        asyncio.run(run_search(
            query=args.query,
            limit=args.limit,
            module=args.module,
            content_type=args.content_type,
        ))
    else:
        asyncio.run(interactive_mode(limit=args.limit))


if __name__ == "__main__":
    main()
