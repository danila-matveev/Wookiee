# Руководство по разработке Wookiee Analytics

## Требования

- **Python 3.11+**
- **PostgreSQL** (доступ к базе данных)
- **Настроенный `.env`** (см. `.env.example`)

## Начало работы

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd Wookiee

# 2. Настроить окружение
cp .env.example .env
# Отредактировать .env — добавить credentials для БД и API

# 3. Установить зависимости
pip install -r requirements.txt
```

## Структура проекта

```
Wookiee/
├── agents/          # AI-агенты (каждый в своей папке)
├── shared/          # Общая библиотека (data_layer, config, utils)
├── scripts/         # CLI-скрипты и утилиты
├── services/        # Доменные сервисы
├── docs/            # Документация
└── deploy/          # Docker и деплой
```

## Процесс разработки

### 1. Создать ветку

Именование по типу изменений:

```bash
git checkout -b feature/new-agent-logic
git checkout -b fix/margin-calculation
git checkout -b docs/update-playbook
git checkout -b refactor/data-layer-cleanup
```

### 2. Внести изменения

Следуй правилам кодирования (см. ниже).

### 3. Проверить по DoD

Перед коммитом проверь чеклист из `docs/guides/dod.md`:

- Код работает и протестирован
- Документация обновлена
- Конфиденциальные данные не попали в коммит
- Соблюдены конвенции проекта

### 4. Обновить историю (если значимое изменение)

Если изменение влияет на архитектуру или бизнес-логику, добавь запись в `docs/development-history.md`.

### 5. Создать Pull Request

Опиши изменения, укажи связанные задачи.

## Конвенции кода

### Работа с данными

- **DB-запросы**: только через `shared/data_layer.py`
- **Конфигурация**: только через `shared/config.py` (читает `.env`)
- **GROUP BY по модели**: ВСЕГДА использовать `LOWER(model)` для нормализации
- **Процентные метрики**: только средневзвешенные (не простые средние)
- **Проблемы с данными**: фиксировать в `docs/database/DATA_QUALITY_NOTES.md`

### Примеры

```python
# Правильно
from shared.data_layer import fetch_data
from shared.config import Config

df = fetch_data("SELECT model, SUM(revenue) FROM sales GROUP BY LOWER(model)")
api_key = Config.NOTION_API_KEY

# Неправильно
import psycopg2  # ❌ прямое подключение к БД
API_KEY = "sk-..."  # ❌ хардкод секретов
```

## Разработка агентов

### Принципы

- Каждый агент изолирован в `agents/<name>/`
- Структура агента:
  - `service.py` — основная логика
  - `playbook.md` — инструкции для LLM (единственный источник истины)
  - `README.md` — описание для разработчиков
- Переиспользование кода: только из `shared.*`, никогда из другого агента
- Подробнее: `docs/guides/agent-principles.md`

### Пример структуры агента

```
agents/<your_agent>/
├── service.py          # Основная логика агента
├── playbook.md         # LLM-инструкции (единственный источник истины)
├── README.md           # Описание для разработчиков
└── utils.py            # Вспомогательные функции (опционально)
```

> Примечание: на момент 2026-04 Phase 1 рефакторинг (PRs #51-58) вывел все исторические агенты (Oleg, Lyudmila, Vasily) в архив `docs/archive/retired_agents/`. См. `docs/adr.md` ADR-009.

## Безопасность

### Секреты

- **Никогда не хардкодить** API-ключи, пароли, токены
- Все секреты в `.env` (файл в `.gitignore`)
- Использовать только через `shared/config.py`

### Supabase / PostgreSQL

- **RLS (Row Level Security) включён** для всех таблиц
- При создании новой таблицы:
  1. Включить RLS: `ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;`
  2. Создать политики доступа
- Подробнее: `sku_database/README.md`

### Проверка перед коммитом

```bash
# Убедись, что нет секретов в изменениях
git diff | grep -E "(api_key|password|token|secret)"
```

## Полезные ссылки

- [AGENTS.md](AGENTS.md) — главные правила проекта
- [docs/guides/dod.md](docs/guides/dod.md) — Definition of Done
- [docs/guides/agent-principles.md](docs/guides/agent-principles.md) — принципы агентов
- [docs/development-history.md](docs/development-history.md) — история изменений
- [docs/database/DATA_QUALITY_NOTES.md](docs/database/DATA_QUALITY_NOTES.md) — известные проблемы данных

## Вопросы?

Проверь документацию в `docs/` или спроси в команде.
