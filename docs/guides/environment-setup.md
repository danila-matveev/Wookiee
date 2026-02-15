# Настройка окружения

## Требования

- Python 3.11+
- PostgreSQL клиент (psycopg2)
- Docker (опционально, для продакшена бота)

## Установка

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd Wookiee
```

### 2. Создать корневой `.env`

```bash
cp .env.example .env
# Заполнить реальные значения
```

### 3. Зависимости для скриптов

```bash
pip install psycopg2-binary python-dotenv
```

### 4. Telegram-бот

```bash
cd bot
pip install -r requirements.txt
cp .env.example .env
# Заполнить реальные значения
```

### 5. SKU Database (при необходимости)

```bash
cd wookiee_sku_database
pip install -r requirements.txt
cp .env.example .env
# Заполнить реальные значения
```

## Трёхуровневая защита .env

| Уровень | Файл | Назначение |
|---------|------|-----------|
| Git | `.gitignore` | .env не попадает в репозиторий |
| AI-агенты | `.cursorignore` | .env не виден Cursor и другим AI |
| IDE | `.vscode/settings.json` | .env виден разработчику в IDE |

## Запуск

### Скрипты (из корня проекта)

```bash
python scripts/daily_analytics.py --date 2026-02-08 --save --notion
python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-07 --save
python scripts/monthly_analytics.py --month 2026-01 --save --notion
```

### Бот

```bash
# Напрямую
python -m bot.main

# Docker (продакшен)
docker-compose up -d
```
