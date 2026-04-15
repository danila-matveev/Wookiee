"""
Knowledge Base tools for MCP integration.

Two groups:
- KB_SEARCH_TOOL_DEFINITIONS — search only (available to all agents)
- KB_MANAGE_TOOL_DEFINITIONS — add/update/delete/stats (Christina only)
- KB_TOOL_DEFINITIONS — backward-compatible alias for search tools
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# KB API URL — Docker network or localhost
KB_API_URL = os.getenv("KB_API_URL", "http://localhost:8002")

# ── Search tools (all agents) ─────────────────────────────────

KB_SEARCH_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Поиск по базе знаний Wookiee (7000+ чанков). "
                "Источники: course (курс Let's Rock, 8 модулей WB), "
                "playbook (правила агентов, пороги, формулы), "
                "reference (метрики KPI, схема БД, качество данных), "
                "agent_spec (архитектура, роли агентов), "
                "guide (принципы разработки). "
                "Содержит: продвижение, юнит-экономику, воронку, SEO, рекламу, "
                "5 рычагов маржи, ABC-анализ, бизнес-правила Wookiee."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос на русском языке",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Количество результатов (по умолчанию 5)",
                        "default": 5,
                    },
                    "module": {
                        "type": "string",
                        "description": (
                            "Фильтр по модулю: 1-8, processes, special. "
                            "1=продвижение, 2=юнит-экономика, 3=воронка продаж, "
                            "4=контент, 5=реклама, 6=аналитика, 7=масштабирование, "
                            "8=автоматизация, special=агенты/KB"
                        ),
                    },
                    "source_tag": {
                        "type": "string",
                        "enum": ["course", "playbook", "reference", "agent_spec", "guide"],
                        "description": (
                            "Фильтр по источнику: "
                            "course=курс Let's Rock, "
                            "playbook=правила агентов, "
                            "reference=метрики/БД/качество данных, "
                            "agent_spec=архитектура/спеки, "
                            "guide=гайды разработки"
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    }
]

# ── Management tools (Christina only) ─────────────────────────

KB_MANAGE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "add_knowledge",
            "description": (
                "Добавить новые знания в базу знаний. "
                "Текст будет разбит на чанки, превращён в эмбеддинги и сохранён в Supabase pgvector."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Текст знаний для добавления",
                    },
                    "title": {
                        "type": "string",
                        "description": "Название/заголовок контента (используется как file_name)",
                    },
                    "module": {
                        "type": "string",
                        "description": (
                            "Модуль: 1-8, processes, manual. "
                            "1=продвижение, 2=юнит-экономика, 3=воронка, "
                            "4=контент, 5=реклама, 6=аналитика, 7=масштабирование, "
                            "8=автоматизация"
                        ),
                    },
                    "content_type": {
                        "type": "string",
                        "enum": ["theory", "template", "example"],
                        "description": "Тип контента: theory (теория), template (шаблон), example (пример)",
                        "default": "theory",
                    },
                    "source_tag": {
                        "type": "string",
                        "enum": ["manual", "insight", "playbook"],
                        "description": "Источник: manual (от пользователя), insight (от Олега), playbook (из плейбука)",
                        "default": "manual",
                    },
                },
                "required": ["text", "title", "module"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_knowledge",
            "description": (
                "Обновить существующий контент в KB. "
                "Удаляет старые чанки по file_name и загружает новый текст."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Имя файла/записи для обновления",
                    },
                    "text": {
                        "type": "string",
                        "description": "Новый текст",
                    },
                    "module": {
                        "type": "string",
                        "description": "Модуль (1-8, processes, manual)",
                    },
                },
                "required": ["file_name", "text", "module"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_knowledge",
            "description": "Удалить контент из KB по имени файла или модулю.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Имя файла для удаления (все чанки этого файла)",
                    },
                    "module": {
                        "type": "string",
                        "description": "Модуль для удаления (все чанки этого модуля). Используй ОСТОРОЖНО.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_knowledge_modules",
            "description": "Показать все модули в базе знаний с количеством чанков и файлов.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_knowledge_files",
            "description": "Показать файлы в базе знаний. Можно фильтровать по модулю.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": "Фильтр по модулю (опционально)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kb_stats",
            "description": "Детальная статистика базы знаний: по модулям, источникам, статусу верификации.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_knowledge",
            "description": "Пометить файл как проверенный (verified) или снять пометку.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": "Имя файла для пометки",
                    },
                    "verified": {
                        "type": "boolean",
                        "description": "true = проверен, false = не проверен",
                        "default": True,
                    },
                },
                "required": ["file_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_project_knowledge",
            "description": (
                "Синхронизировать все знания проекта с KB. "
                "Читает плейбуки, справочники, спеки агентов и гайды из файлов проекта "
                "и загружает новые/обновлённые в Supabase pgvector. "
                "Уже загруженные файлы пропускаются (используй force=true для перезагрузки). "
                "14 файлов: 4 плейбука, 4 справочника, 4 спеки агентов, 2 гайда."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "true = перезагрузить все файлы (удалить старые чанки + загрузить заново)",
                        "default": False,
                    },
                },
            },
        },
    },
]

# Backward-compatible alias
KB_TOOL_DEFINITIONS = KB_SEARCH_TOOL_DEFINITIONS


# ── Executors ──────────────────────────────────────────────────


async def _api_call(method: str, path: str, json_body: dict = None, params: dict = None) -> str:
    """Call KB API endpoint with fallback."""
    import httpx

    url = f"{KB_API_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            if method == "GET":
                resp = await client.get(url, params=params)
            elif method == "POST":
                resp = await client.post(url, json=json_body)
            elif method == "DELETE":
                resp = await client.delete(url)
            elif method == "PATCH":
                resp = await client.patch(url, params=params)
            else:
                return json.dumps({"error": f"Unknown method: {method}"})
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        logger.warning("KB API call failed (%s %s): %s — trying direct", method, path, e)
        return None  # Caller handles fallback


async def _search_via_api(query: str, limit: int = 5, module: str = None, source_tag: str = None) -> str:
    """Call KB API search endpoint."""
    import httpx

    payload = {"query": query, "limit": limit, "min_score": 0.4}
    if module:
        payload["module"] = module
    if source_tag:
        payload["source_tag"] = source_tag

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{KB_API_URL}/search", json=payload)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        logger.error("KB API search failed: %s", e)
        return await _search_direct(query, limit, module, source_tag=source_tag)


async def _search_direct(query: str, limit: int = 5, module: str = None, source_tag: str = None) -> str:
    """Direct search without API (fallback for same-container deployment)."""
    try:
        from services.knowledge_base.search import search_knowledge
        kwargs = dict(query=query, limit=limit, module=module, min_score=0.4)
        if source_tag:
            kwargs["source_tag"] = source_tag
        results = await search_knowledge(**kwargs)
        return json.dumps({
            "results": results,
            "count": len(results),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Direct fallbacks for manage tools ─────────────────────────


async def _direct_add_knowledge(text, title, module, content_type, source_tag) -> str:
    """Direct add knowledge without API."""
    try:
        from services.knowledge_base.ingest import ingest_text
        chunks = await ingest_text(
            text=text, file_name=title, module=module,
            content_type=content_type, source_tag=source_tag,
        )
        return json.dumps({"status": "ok", "chunks_inserted": chunks, "file_name": title},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def _direct_delete(file_name=None, module=None) -> str:
    """Direct delete without API."""
    try:
        from services.knowledge_base.store import KnowledgeStore
        store = KnowledgeStore()
        if file_name:
            deleted = store.delete_by_file(file_name)
            return json.dumps({"status": "ok", "deleted": deleted, "file_name": file_name})
        elif module:
            deleted = store.delete_by_module(module)
            return json.dumps({"status": "ok", "deleted": deleted, "module": module})
        return json.dumps({"error": "Укажи file_name или module"})
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def _direct_store_call(method_name: str, **kwargs) -> str:
    """Direct store method call without API."""
    try:
        from services.knowledge_base.store import KnowledgeStore
        store = KnowledgeStore()
        result = getattr(store, method_name)(**kwargs)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Main executor ─────────────────────────────────────────────


async def execute_kb_tool(tool_name: str, arguments: dict) -> str:
    """Execute a KB tool. Compatible with MCP server executor interface."""

    # Search
    if tool_name == "search_knowledge_base":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        module = arguments.get("module")
        source_tag = arguments.get("source_tag")
        return await _search_via_api(query, limit, module, source_tag=source_tag)

    # Add knowledge
    if tool_name == "add_knowledge":
        text = arguments.get("text", "")
        title = arguments.get("title", "untitled")
        module = arguments.get("module", "manual")
        content_type = arguments.get("content_type", "theory")
        source_tag = arguments.get("source_tag", "manual")

        result = await _api_call("POST", "/ingest_text", json_body={
            "text": text, "file_name": title, "module": module,
            "content_type": content_type, "source_tag": source_tag,
        })
        if result is not None:
            return result
        return await _direct_add_knowledge(text, title, module, content_type, source_tag)

    # Update knowledge (delete + re-add)
    if tool_name == "update_knowledge":
        file_name = arguments.get("file_name", "")
        text = arguments.get("text", "")
        module = arguments.get("module", "manual")

        # Delete old
        del_result = await _api_call("DELETE", f"/file/{file_name}")
        if del_result is None:
            await _direct_delete(file_name=file_name)

        # Re-add
        result = await _api_call("POST", "/ingest_text", json_body={
            "text": text, "file_name": file_name, "module": module,
            "content_type": "theory", "source_tag": "manual",
        })
        if result is not None:
            return result
        return await _direct_add_knowledge(text, file_name, module, "theory", "manual")

    # Delete knowledge
    if tool_name == "delete_knowledge":
        file_name = arguments.get("file_name")
        module = arguments.get("module")

        if file_name:
            result = await _api_call("DELETE", f"/file/{file_name}")
            if result is not None:
                return result
        elif module:
            result = await _api_call("DELETE", f"/module/{module}")
            if result is not None:
                return result

        return await _direct_delete(file_name=file_name, module=module)

    # List modules
    if tool_name == "list_knowledge_modules":
        result = await _api_call("GET", "/modules")
        if result is not None:
            return result
        return await _direct_store_call("list_modules")

    # List files
    if tool_name == "list_knowledge_files":
        module = arguments.get("module")
        params = {"module": module} if module else None
        result = await _api_call("GET", "/files", params=params)
        if result is not None:
            return result
        return await _direct_store_call("list_files", module=module)

    # KB stats
    if tool_name == "get_kb_stats":
        result = await _api_call("GET", "/detailed_stats")
        if result is not None:
            return result
        return await _direct_store_call("get_detailed_stats")

    # Verify knowledge
    if tool_name == "verify_knowledge":
        file_name = arguments.get("file_name", "")
        verified = arguments.get("verified", True)
        result = await _api_call("PATCH", f"/verify/{file_name}", params={"verified": verified})
        if result is not None:
            return result
        return await _direct_store_call("mark_verified", file_name=file_name, verified=verified)

    # Sync project knowledge files
    if tool_name == "sync_project_knowledge":
        force = arguments.get("force", False)
        return await _sync_project_knowledge(force)

    return json.dumps({"error": f"Unknown KB tool: {tool_name}"}, ensure_ascii=False)


async def _sync_project_knowledge(force: bool = False) -> str:
    """Run project knowledge ingestion (same logic as ingest_knowledge.py)."""
    try:
        from services.knowledge_base.scripts.ingest_knowledge import ingest_knowledge
        total = await ingest_knowledge(force=force)
        return json.dumps({
            "status": "ok",
            "chunks_ingested": total,
            "force": force,
            "message": f"Синхронизация завершена: {total} новых чанков загружено",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("sync_project_knowledge failed: %s", e, exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)
