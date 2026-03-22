"""
Content Knowledge Base MCP tools.

Provides search_content, list_content, get_content_stats tools
for integration with the v3 multi-agent system.
"""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


CONTENT_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": (
                "Векторный поиск по контенту бренда (фото, изображения) на Яндекс.Диске. "
                "Используй текстовый запрос + метаданные-фильтры (модель, цвет, категория, артикул). "
                "Возвращает превью-ссылки и similarity scores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Текстовый запрос для поиска (на русском или английском)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Макс. количество результатов (по умолчанию 10)",
                        "default": 10,
                    },
                    "model_name": {
                        "type": "string",
                        "description": (
                            "Фильтр по модели: Alice, Audrey, Bella, Charlotte, Eva, "
                            "Joy, Lana, Miafull, Moon, Ruby, Space, Valery, Vuki, Wendy"
                        ),
                    },
                    "color": {
                        "type": "string",
                        "description": "Фильтр по цвету: black, white, beige, brown, light_beige",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Фильтр по категории контента: фото, маркетплейсы, "
                            "дизайн, аб_тесты, сайт, lamoda, блогеры"
                        ),
                    },
                    "sku": {
                        "type": "string",
                        "description": "Фильтр по артикулу WB (например 257144777)",
                    },
                    "min_similarity": {
                        "type": "number",
                        "description": "Минимальный порог сходства (по умолчанию 0.3)",
                        "default": 0.3,
                    },
                    "include_preview": {
                        "type": "boolean",
                        "description": "Генерировать превью-ссылки (по умолчанию true)",
                        "default": True,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_content",
            "description": (
                "Список контента по метаданные-фильтрам (без векторного поиска). "
                "Используй для просмотра всех фото модели/цвета/категории."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Фильтр по модели",
                    },
                    "color": {
                        "type": "string",
                        "description": "Фильтр по цвету",
                    },
                    "category": {
                        "type": "string",
                        "description": "Фильтр по категории контента",
                    },
                    "sku": {
                        "type": "string",
                        "description": "Фильтр по артикулу",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Макс. количество (по умолчанию 50)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Смещение для пагинации",
                        "default": 0,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_content_stats",
            "description": (
                "Статистика по проиндексированному контенту: "
                "количество по категориям, моделям, дата последней индексации."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


async def execute_content_tool(tool_name: str, arguments: dict) -> str:
    """Execute a content KB tool and return JSON result."""
    try:
        if tool_name == "search_content":
            from .search import search_content
            result = await search_content(
                query=arguments["query"],
                limit=arguments.get("limit", 10),
                model_name=arguments.get("model_name"),
                color=arguments.get("color"),
                category=arguments.get("category"),
                sku=arguments.get("sku"),
                min_similarity=arguments.get("min_similarity", 0.3),
                include_preview=arguments.get("include_preview", True),
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        elif tool_name == "list_content":
            from .store import ContentStore
            store = ContentStore()
            result = store.list_content(
                model_name=arguments.get("model_name"),
                color=arguments.get("color"),
                category=arguments.get("category"),
                sku=arguments.get("sku"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )
            return json.dumps({"total": len(result), "items": result}, ensure_ascii=False, default=str)

        elif tool_name == "get_content_stats":
            from .store import ContentStore
            store = ContentStore()
            result = store.get_stats()
            return json.dumps(result, ensure_ascii=False, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error("Content tool %s failed: %s", tool_name, e)
        return json.dumps({"error": str(e)})
