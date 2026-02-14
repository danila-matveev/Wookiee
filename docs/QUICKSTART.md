# Быстрый старт

Пять шагов от клонирования до первого отчёта.

## 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd Wookiee
```

## 2. Настроить окружение

```bash
cp .env.example .env
# Открыть .env и заполнить реальными значениями
```

**Минимум для скриптов:**
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` — PostgreSQL с данными WB/OZON

**Для Telegram-ботов дополнительно:**
- `TELEGRAM_BOT_TOKEN`, `BOT_PASSWORD_HASH` — Олег (финансы)
- `LYUDMILA_BOT_TOKEN` — Людмила (CRM)
- `ZAI_API_KEY` или `CLAUDE_API_KEY` — AI-модели

## 3. Установить зависимости

```bash
# Для скриптов
pip install psycopg2-binary python-dotenv pandas openpyxl

# Для Олега (Telegram-бот аналитики)
pip install -r agents/oleg/requirements.txt

# Для Людмилы (CRM-ассистент)
pip install -r agents/lyudmila/requirements.txt

# Для Василия (логистика WB)
pip install -r agents/vasily/requirements.txt
```

## 4. Запустить первый скрипт

```bash
python3 scripts/abc_analysis.py --help
```

Доступные скрипты: `scripts/daily_analytics.py`, `scripts/monthly_analytics.py`, `scripts/period_analytics.py`

## 5. Запустить бота (опционально)

```bash
# Олег — финансовый аналитик
python3 -m agents.oleg

# Людмила — CRM-ассистент
python3 -m agents.lyudmila

# Василий — логистика WB
python3 -m agents.vasily
```

## Docker (альтернатива)

```bash
docker compose -f deploy/docker-compose.yml up -d
```

## Что дальше?

- **[docs/index.md](index.md)** — навигация по документации
- **[AGENTS.md](../AGENTS.md)** — правила разработки для AI-агентов
- **[docs/guides/environment-setup.md](guides/environment-setup.md)** — подробная настройка окружения
