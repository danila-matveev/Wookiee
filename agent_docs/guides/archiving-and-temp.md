# Архивация и временные файлы

## Development History

- Хранить последние 10 записей в `agent_docs/development-history.md`
- Старые записи переносить в `agent_docs/archive/development-history-YYYY.md`

## Отчёты

- Сгенерированные отчёты в `reports/` — git-ignored
- Синхронизируются с Notion через `notion_sync.py`

## Архивация важных файлов

- Директория: `archive/` в корне репозитория
- Именование: `[YYYY-MM-DD_HH-MM]_original_name.ext`
- Добавлять header-комментарий с датой, причиной и ссылкой на новую версию

НЕ архивировать:
- Временные файлы
- Файлы git
- Секреты (.env)
- Бинарные файлы
- .gitignore файлы

## Временные файлы

- Использовать Python `tempfile` модуль
- Не создавать temp файлы в корне проекта
- Очищать после использования
