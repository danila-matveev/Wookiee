# IEE-агент Людмила

## Бизнес-описание

**Назначение:** Офис-менеджер и бизнес-ассистент команды Wookiee. Прослойка между сотрудниками и CRM Bitrix24.

**Миссия:** Экономить время команды и повышать эффективность через структурную работу с задачами и встречами.

**Характер:** Дружелюбная, но настойчивая — не даёт ставить размытые задачи, помогает делать работу правильно.

**Статус:** Активен (production)

**Какие задачи решает:**
- Утренний дайджест — встречи, задачи, просрочки с ИИ-подсказками (в таймзоне пользователя)
- Постановка задач — ИИ-помощь в формулировке, целевой результат, чеклист
- Создание встреч — повестка, подготовка, что изучить заранее
- Контроль качества — не принимает размытые задачи и процессы
- Email-авторизация через Bitrix24

**Кто использует:** Вся команда Wookiee

---

## Технические детали

### Стек

| Компонент | Технология |
|-----------|-----------|
| Framework | aiogram 3.15 (Telegram Bot API) |
| Scheduling | APScheduler 3.10.4 (per-user timezone) |
| AI | Claude API (Sonnet 4.5) |
| CRM | Bitrix24 REST API (webhook) |
| Хранилище | SQLite (пользователи, лог действий) |
| Поиск имён | thefuzz (нечёткий поиск, 54 уменьш. имени) |

### Архитектура

```
Telegram User
    ↓
lyudmila_bot/main.py (инициализация, DI middleware, роутинг)
    ↓
lyudmila_bot/handlers/
    ├── auth.py              → email-авторизация через Bitrix24
    ├── menu.py              → главное меню и навигация
    ├── task_creation.py     → создание задач (FSM + ИИ)
    ├── meeting_creation.py  → создание встреч (FSM + ИИ)
    ├── digest.py            → дайджест (ручной/автоматический)
    └── common.py            → UX утилиты (кнопки, ошибки)
    ↓
lyudmila_bot/services/
    ├── lyuda_ai.py          → МОЗГ: Claude API + системные промпты
    ├── bitrix_service.py    → async-обёртка Bitrix24 API
    ├── user_cache.py        → кеш сотрудников + нечёткий поиск
    ├── auth_service.py      → email-авторизация + сессии
    ├── digest_service.py    → сборка дайджеста (Bitrix + ИИ)
    ├── scheduler_service.py → APScheduler (per-user timezone)
    └── db_service.py        → SQLite CRUD
    ↓
Bitrix24 REST API (webhook)
```

### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `lyudmila_bot/main.py` | Точка входа, LyudmilaBot, DI middleware |
| `lyudmila_bot/config.py` | Конфигурация из .env |
| `lyudmila_bot/persona.py` | Личность Людмилы: промпты, правила |
| `lyudmila_bot/services/lyuda_ai.py` | Claude API клиент |
| `lyudmila_bot/services/bitrix_service.py` | Async Bitrix24 API |
| `lyudmila_bot/services/user_cache.py` | Кеш сотрудников |
| `lyudmila_bot/handlers/task_creation.py` | ИИ-создание задач |
| `lyudmila_bot/handlers/meeting_creation.py` | ИИ-создание встреч |
| `lyudmila_bot/models/` | Модели: BotUser, TaskStructure, MeetingStructure |

### Конфигурация (.env)

```env
# Telegram
LYUDMILA_BOT_TOKEN=...

# Bitrix24
Bitrix_rest_api=https://wookiee.bitrix24.ru/rest/1/xxxx/

# AI
CLAUDE_API_KEY=...
```

---

## Запуск и использование

### Запуск

```bash
cd /path/to/Wookiee
python -m lyudmila_bot.main
```

### Команды бота

| Команда | Действие |
|---------|---------|
| `/start` | Авторизация (ввод email) |
| `/menu` | Главное меню (сбрасывает FSM) |
| `/logout` | Выход из системы |

### Меню

1. **Поставить задачу** → описание → ИИ → превью → Bitrix24
2. **Создать встречу** → описание → ИИ → превью → Bitrix24
3. **Мой дайджест** → встречи + задачи + просрочки + подсказки
4. **Настройки** → таймзон, вкл/выкл дайджест

---

## Зависимости

- **Внутренние:** `wookiee_sku_database/Bitrix/client.py` (паттерн webhook)
- **Внешние:** Bitrix24 REST API, Claude API, Telegram Bot API

---

## Ссылки

- Исходный код: [`lyudmila_bot/`](../lyudmila_bot/)
- Bitrix24 клиент: [`wookiee_sku_database/Bitrix/`](../wookiee_sku_database/Bitrix/)
- Аналитический бот Рома: [`agents/telegram-bot.md`](telegram-bot.md)
- Правила проекта: [`AGENTS.md`](../AGENTS.md)
