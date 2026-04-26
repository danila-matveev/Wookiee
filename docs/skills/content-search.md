# /content-search — Поиск по контент-базе знаний

**Запуск:** `/content-search`

## Что делает

Выполняет семантический поиск по базе знаний контент-команды: фото товаров, референсы, описания. Использует vector search (pgvector) на эмбеддингах Gemini. Индексировано ~7K документов.

## Параметры

- `query` — поисковый запрос (обязательный)
- `top_k` — количество результатов (по умолчанию: 5)
- `filter` — фильтр по типу контента: `photo`, `reference`, `description`

## Результат

Список релевантных документов с similarity score выводится в stdout.

## Зависимости

- Supabase (pgvector, таблица `content_kb_embeddings`)
- OpenRouter API (Gemini Embeddings, `OPENROUTER_API_KEY`)
- `services/content_kb/`
