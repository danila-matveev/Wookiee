# services/content_kb/

Векторный поиск по фото-контенту (Яндекс Диск → Gemini Embedding → pgvector).

## Назначение

Индексирует изображения с Яндекс Диска через Gemini Embedding API, хранит векторы в Supabase (pgvector). Обеспечивает семантический поиск по контент-базе (~7K объектов).

## Запуск

```bash
python -m services.content_kb.indexer      # индексация/обновление
python -m services.content_kb.search "запрос"  # поиск
```

## Связанное

- Скилл `/content-search` — поиск через Claude Code
- MCP сервер: `services/content_kb/mcp_server.py`
