#!/usr/bin/env python3
"""
Bitrix24 Chat Export — выгрузка сообщений из групповых чатов.

Использование:
    python scripts/bitrix_chat_export.py              # проверка scope + список чатов
    python scripts/bitrix_chat_export.py --export      # полный экспорт сообщений
    python scripts/bitrix_chat_export.py --export --all # экспорт ВСЕХ чатов (не только целевых)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, date as date_type
from pathlib import Path

import requests

# ── Настройки ────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

WEBHOOK_URL = os.getenv("Bitrix_rest_api", "").rstrip("/") + "/"
EXPORT_DIR = ROOT_DIR / "data" / "bitrix_export"

# Целевые чаты (подстроки для fuzzy matching)
TARGET_CHAT_KEYWORDS = [
    "smm",
    "рабочий чат",
    "marketplace",
    "контент",
    "разработка продукта",
    "маркетинг",
    "склад",
    "проверка качества",
    "финанс",
    "запуск",
    "тиловей",
    "идеи по продукту",
    "let's rock",
    "lets rock",
    "wookiee",
    "вуки",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── API клиент ───────────────────────────────────────────────────────

class BitrixClient:
    """Минимальный sync-клиент для Bitrix24 REST API с rate limiting."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self._session = requests.Session()
        self._last_req: float = 0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_req
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_req = time.time()

    def call(self, method: str, params: dict | None = None, _retries: int = 3) -> dict:
        self._rate_limit()
        url = f"{self.webhook_url}{method}"
        try:
            resp = self._session.post(url, json=params or {}, timeout=30)
        except (requests.ConnectionError, requests.Timeout) as e:
            if _retries <= 0:
                raise
            log.warning("Connection error (%s), retry in 5s (%d left)", e.__class__.__name__, _retries)
            time.sleep(5)
            self._session = requests.Session()  # fresh session
            return self.call(method, params, _retries=_retries - 1)
        if resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 2))
            log.warning("Rate limit, waiting %ds", retry)
            time.sleep(retry)
            return self.call(method, params, _retries=_retries)
        if resp.status_code in (502, 503, 504) and _retries > 0:
            log.warning("Server %d, retry in 10s (%d left)", resp.status_code, _retries)
            time.sleep(10)
            self._session = requests.Session()
            return self.call(method, params, _retries=_retries - 1)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Bitrix API error: {data.get('error_description', data['error'])}")
        return data

    def call_all(self, method: str, params: dict | None = None, result_key: str | None = None) -> list:
        """Вызов с автоматической пагинацией (через 'next'/'start')."""
        all_items: list = []
        start = 0
        params = dict(params or {})

        while True:
            params["start"] = start
            data = self.call(method, params)
            result = data.get("result", [])
            if result_key and isinstance(result, dict):
                result = result.get(result_key, [])
            if isinstance(result, list):
                all_items.extend(result)
            else:
                all_items.append(result)
                break

            next_start = data.get("next")
            if next_start is None:
                break
            start = next_start
            log.info("  ... загружено %d записей, продолжаю (start=%d)", len(all_items), start)

        return all_items


# ── Функции экспорта ─────────────────────────────────────────────────

def check_scope(client: BitrixClient) -> list[str]:
    """Проверить доступные scope вебхука."""
    data = client.call("scope")
    scopes = data.get("result", [])
    return scopes


def get_users(client: BitrixClient) -> dict:
    """Загрузить всех сотрудников → {id: {name, position, department}}."""
    log.info("Загружаю список сотрудников...")
    users_raw = client.call_all("user.get", {"FILTER": {"ACTIVE": True}})
    users = {}
    for u in users_raw:
        uid = str(u.get("ID", ""))
        name = f"{u.get('NAME', '')} {u.get('LAST_NAME', '')}".strip()
        users[uid] = {
            "name": name or f"User {uid}",
            "position": u.get("WORK_POSITION", ""),
            "department": u.get("UF_DEPARTMENT", []),
            "email": u.get("EMAIL", ""),
        }
    log.info("Загружено %d сотрудников", len(users))
    return users


def get_chats(client: BitrixClient) -> list[dict]:
    """Загрузить все групповые чаты через im.recent.list."""
    log.info("Загружаю список чатов...")
    all_chats: list[dict] = []
    offset = 0
    limit = 200

    while True:
        data = client.call("im.recent.list", {
            "SKIP_DIALOG": "Y",         # пропускаем личные чаты
            "SKIP_OPENLINES": "Y",      # пропускаем открытые линии
            "OFFSET": offset,
            "LIMIT": limit,
        })
        result = data.get("result", {})
        items = result.get("items", [])
        if not items:
            break
        all_chats.extend(items)
        has_more = result.get("hasMore", False)
        if not has_more:
            break
        offset += limit
        log.info("  ... загружено %d чатов, продолжаю", len(all_chats))

    log.info("Всего групповых чатов: %d", len(all_chats))
    return all_chats


def filter_chats(chats: list[dict], include_all: bool = False) -> list[dict]:
    """Фильтрация чатов по целевым ключевым словам."""
    if include_all:
        return chats

    filtered = []
    for chat in chats:
        title = (chat.get("title", "") or "").lower()
        if any(kw in title for kw in TARGET_CHAT_KEYWORDS):
            filtered.append(chat)
    return filtered


def export_messages(client: BitrixClient, dialog_id: str, chat_title: str) -> list[dict]:
    """Выгрузить ВСЕ сообщения из одного чата через im.dialog.messages.get."""
    log.info("Выгружаю сообщения из '%s' (%s)...", chat_title, dialog_id)
    all_messages: list[dict] = []
    first_id = 0  # начинаем с самого первого сообщения

    while True:
        params: dict = {
            "DIALOG_ID": dialog_id,
            "LIMIT": 50,
        }
        if first_id == 0:
            params["FIRST_ID"] = 0
        else:
            params["FIRST_ID"] = first_id

        try:
            data = client.call("im.dialog.messages.get", params)
        except RuntimeError as e:
            log.error("Ошибка при выгрузке '%s': %s", chat_title, e)
            break

        result = data.get("result", {})
        messages = result.get("messages", [])

        if not messages:
            break

        all_messages.extend(messages)

        # Определяем следующий first_id
        max_id = max(m.get("id", 0) for m in messages)
        if max_id <= first_id:
            break
        first_id = max_id

        if len(all_messages) % 500 == 0:
            log.info("  ... %s: %d сообщений загружено", chat_title, len(all_messages))

    log.info("  '%s': итого %d сообщений", chat_title, len(all_messages))
    return all_messages


def save_json(data: object, filename: str) -> Path:
    """Сохранить данные в JSON файл."""
    path = EXPORT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return path


def _parse_date(s: str) -> date_type | None:
    """Парсинг даты из строки Bitrix (ISO-подобный формат)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def filter_messages_by_date(
    messages: list[dict],
    since: date_type | None = None,
    until: date_type | None = None,
) -> list[dict]:
    """Фильтрация сообщений по дате (клиент-сайд)."""
    if not since and not until:
        return messages
    filtered = []
    for m in messages:
        d = _parse_date(m.get("date", ""))
        if d is None:
            continue
        if since and d < since:
            continue
        if until and d > until:
            continue
        filtered.append(m)
    return filtered


def export_tasks(
    client: BitrixClient,
    users: dict,
    since: date_type | None = None,
    until: date_type | None = None,
) -> list[dict]:
    """Выгрузить задачи из Bitrix24."""
    log.info("Выгружаю задачи...")
    filter_params: dict = {}
    if since:
        filter_params[">=CREATED_DATE"] = since.strftime("%Y-%m-%dT00:00:00")
    if until:
        filter_params["<=CREATED_DATE"] = until.strftime("%Y-%m-%dT23:59:59")

    params = {
        "filter": filter_params,
        "select": [
            "ID", "TITLE", "DESCRIPTION", "REAL_STATUS", "PRIORITY",
            "RESPONSIBLE_ID", "CREATED_BY", "DEADLINE",
            "CREATED_DATE", "CHANGED_DATE", "CLOSED_DATE",
            "GROUP_ID", "TAGS", "AUDITORS", "ACCOMPLICES",
        ],
    }
    tasks = client.call_all("tasks.task.list", params, result_key="tasks")

    for t in tasks:
        resp_id = str(t.get("responsibleId", t.get("RESPONSIBLE_ID", "")))
        creator_id = str(t.get("createdBy", t.get("CREATED_BY", "")))
        t["responsible_name"] = users.get(resp_id, {}).get("name", f"User {resp_id}")
        t["creator_name"] = users.get(creator_id, {}).get("name", f"User {creator_id}")

    log.info("Загружено %d задач", len(tasks))
    return tasks


def export_task_comments(
    client: BitrixClient,
    tasks: list[dict],
    users: dict,
) -> list[dict]:
    """Выгрузить комментарии ко всем задачам."""
    log.info("Выгружаю комментарии к %d задачам...", len(tasks))
    results = []

    for i, task in enumerate(tasks):
        task_id = task.get("id", task.get("ID"))
        try:
            data = client.call("task.commentitem.getlist", {"TASKID": int(task_id)})
            raw_comments = data.get("result", [])
        except (RuntimeError, Exception) as e:
            log.debug("Ошибка комментариев задачи %s: %s", task_id, e)
            raw_comments = []

        comments = []
        for c in raw_comments:
            if str(c.get("AUTHOR_ID", "")) == "0":
                continue  # системные комментарии
            text = c.get("POST_MESSAGE", "")
            if not text or len(text.strip()) < 2:
                continue
            author_id = str(c.get("AUTHOR_ID", ""))
            comments.append({
                "author_id": author_id,
                "author_name": users.get(author_id, {}).get("name", f"User {author_id}"),
                "text": text[:3000],
                "date": c.get("POST_DATE", ""),
            })

        results.append({
            "task_id": task_id,
            "title": task.get("title", task.get("TITLE", "")),
            "status": task.get("status", task.get("REAL_STATUS", "")),
            "priority": task.get("priority", task.get("PRIORITY", "")),
            "responsible_name": task.get("responsible_name", ""),
            "creator_name": task.get("creator_name", ""),
            "created_date": task.get("createdDate", task.get("CREATED_DATE", "")),
            "changed_date": task.get("changedDate", task.get("CHANGED_DATE", "")),
            "closed_date": task.get("closedDate", task.get("CLOSED_DATE", "")),
            "deadline": task.get("deadline", task.get("DEADLINE", "")),
            "group_id": task.get("groupId", task.get("GROUP_ID", "")),
            "comments": comments,
            "comment_count": len(comments),
        })

        if (i + 1) % 50 == 0:
            log.info("  ... %d/%d задач обработано", i + 1, len(tasks))

    total_comments = sum(r["comment_count"] for r in results)
    log.info("Комментариев: %d к %d задачам", total_comments, len(tasks))
    return results


# ── Основная логика ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bitrix24 Chat & Task Export")
    parser.add_argument("--export", action="store_true", help="Запустить экспорт сообщений из чатов")
    parser.add_argument("--all", action="store_true", help="Экспортировать ВСЕ чаты, не только целевые")
    parser.add_argument("--resume", action="store_true", help="Пропускать уже выгруженные чаты")
    parser.add_argument("--tasks", action="store_true", help="Экспортировать задачи и комментарии")
    parser.add_argument("--since", type=str, default=None, help="Дата начала (YYYY-MM-DD)")
    parser.add_argument("--until", type=str, default=None, help="Дата конца (YYYY-MM-DD)")
    args = parser.parse_args()

    since = date_type.fromisoformat(args.since) if args.since else None
    until = date_type.fromisoformat(args.until) if args.until else None

    if not WEBHOOK_URL or WEBHOOK_URL == "/":
        log.error("Bitrix_rest_api не задан в .env")
        sys.exit(1)

    client = BitrixClient(WEBHOOK_URL)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Шаг 0: Проверка scope ──
    log.info("=" * 60)
    log.info("Проверяю права вебхука...")
    scopes = check_scope(client)
    log.info("Доступные scope: %s", ", ".join(scopes) if scopes else "(пусто)")

    if "im" not in scopes:
        log.error(
            "❌ Scope 'im' НЕ найден! Нужно добавить в настройках вебхука:\n"
            "   Bitrix24 → Приложения → Вебхуки → Редактировать → "
            "Поставить галочку 'Чат и уведомления (im)'"
        )
        sys.exit(1)

    log.info("✅ Scope 'im' доступен")

    # ── Шаг 1: Пользователи ──
    users = get_users(client)
    save_json(users, "users.json")

    # ── Шаг 2: Список чатов ──
    all_chats_raw = get_chats(client)

    # Упрощаем структуру чатов для вывода
    chats_simplified = []
    for c in all_chats_raw:
        chat_id = c.get("chat_id", c.get("id", ""))
        dialog_id = c.get("id", "")
        # Для групповых чатов dialog_id = "chatXXX"
        if isinstance(dialog_id, int):
            dialog_id = f"chat{dialog_id}"
        elif not str(dialog_id).startswith("chat"):
            dialog_id = f"chat{chat_id}"

        chats_simplified.append({
            "chat_id": chat_id,
            "dialog_id": dialog_id,
            "title": c.get("title", "Без названия"),
            "type": c.get("type", ""),
            "counter": c.get("counter", 0),
            "date_update": c.get("date_update", ""),
        })

    # Фильтруем
    target_chats = filter_chats(chats_simplified, include_all=args.all)

    log.info("=" * 60)
    log.info("Целевые чаты для экспорта (%d из %d):", len(target_chats), len(chats_simplified))
    for i, c in enumerate(target_chats, 1):
        log.info("  %2d. %-40s [%s]", i, c["title"], c["dialog_id"])

    save_json(chats_simplified, "chats.json")

    if not args.export and not args.tasks:
        log.info("=" * 60)
        log.info("Для экспорта чатов: --export [--since YYYY-MM-DD] [--until YYYY-MM-DD]")
        log.info("Для экспорта задач:  --tasks [--since YYYY-MM-DD] [--until YYYY-MM-DD]")
        return

    # ── Шаг 3: Экспорт сообщений ──
    if args.export:
        if since or until:
            log.info("Фильтр по дате: %s — %s", since or "начало", until or "сегодня")

        log.info("=" * 60)
        log.info("Начинаю экспорт сообщений из %d чатов...", len(target_chats))
        total_messages = 0
        export_stats = []

        for chat in target_chats:
            filename = f"messages_{chat['dialog_id'].replace('chat', 'chat_')}.json"
            if args.resume and (EXPORT_DIR / filename).exists():
                log.info("⏭  Пропускаю '%s' — уже выгружен", chat["title"])
                with open(EXPORT_DIR / filename, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                if since or until:
                    messages = filter_messages_by_date(messages, since, until)
                total_messages += len(messages)
                export_stats.append({
                    "chat": chat["title"],
                    "dialog_id": chat["dialog_id"],
                    "message_count": len(messages),
                    "filename": filename,
                })
                continue
            messages = export_messages(client, chat["dialog_id"], chat["title"])
            if since or until:
                before = len(messages)
                messages = filter_messages_by_date(messages, since, until)
                log.info("  Фильтр по дате: %d → %d сообщений", before, len(messages))
            if messages:
                save_json(messages, filename)
                total_messages += len(messages)
                export_stats.append({
                    "chat": chat["title"],
                    "dialog_id": chat["dialog_id"],
                    "message_count": len(messages),
                    "filename": filename,
                })

        # ── Мета-информация ──
        meta = {
            "export_date": datetime.now().isoformat(),
            "total_chats": len(target_chats),
            "total_messages": total_messages,
            "since": str(since) if since else None,
            "until": str(until) if until else None,
            "chats": export_stats,
            "users_count": len(users),
        }
        save_json(meta, "export_meta.json")

        log.info("=" * 60)
        log.info("✅ Экспорт чатов завершён!")
        log.info("   Чатов: %d", len(target_chats))
        log.info("   Сообщений: %d", total_messages)
        log.info("   Файлы: %s", EXPORT_DIR)

    # ── Шаг 4: Экспорт задач ──
    if args.tasks:
        if "task" not in scopes:
            log.error(
                "❌ Scope 'task' НЕ найден! Нужно добавить в настройках вебхука:\n"
                "   Bitrix24 → Приложения → Вебхуки → Редактировать → "
                "Поставить галочку 'Задачи (task)'"
            )
            sys.exit(1)

        log.info("=" * 60)
        log.info("✅ Scope 'task' доступен")
        tasks_since = since or date_type(2025, 10, 1)
        tasks_until = until
        log.info("Экспорт задач с %s%s", tasks_since, f" по {tasks_until}" if tasks_until else "")

        tasks = export_tasks(client, users, tasks_since, tasks_until)
        save_json(tasks, "tasks.json")

        tasks_with_comments = export_task_comments(client, tasks, users)
        save_json(tasks_with_comments, "tasks_with_comments.json")

        log.info("=" * 60)
        log.info("✅ Экспорт задач завершён!")
        log.info("   Задач: %d", len(tasks))
        log.info("   С комментариями: %s", EXPORT_DIR / "tasks_with_comments.json")


if __name__ == "__main__":
    main()
