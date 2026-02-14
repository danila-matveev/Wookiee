# Конвенции логирования

## Telegram Bot

- Директория: `bot/logs/` (git-ignored)
- Уровень: контролируется переменной `LOG_LEVEL` в `.env` (по умолчанию: INFO)
- Формат: стандартный Python logging

## Analytics Scripts

- Вывод: stdout (Markdown-отчёты)
- Сохранение: `reports/` (git-ignored)
- Флаг `--save` сохраняет в файл
- Флаг `--notion` синхронизирует с Notion

## Data Pipeline

- Директория: `marketplace-data-pipeline/logs/` (git-ignored)
- Уровень: переменная `LOG_LEVEL`

## Общие правила

- Не логировать секреты (пароли, токены)
- Уровни: DEBUG для разработки, INFO для продакшена
- Логи старше 3 дней можно удалять
