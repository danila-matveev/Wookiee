# Людмила — ИИ-агент проджект-менеджер (Retired Plan)

> Статус: RETIRED | Исходный план: 2026-02-19 | Архивирован: 2026-02-21

## 1. Цель

Превратить Людмилу из Telegram-бота, который создаёт задачи, в **полноценного ИИ-сотрудника** компании:
- Реальный пользователь в Битрикс24 (не чат-бот)
- Участник групповых чатов в Telegram и Битрикс24
- Проджект-менеджер: контроль дедлайнов, мониторинг чатов, автопостановка задач
- Обработка стенограмм созвонов, фото, скриншотов, файлов
- Настоящий ReAct-агент, а не линейный скрипт

---

## 2. Архитектура

### 2.1 Общая схема

```
╔══════════════════════════════════════════════════════════════════════════╗
║                         3 ИНТЕРФЕЙСА                                    ║
║                  (входы и выходы одного агента)                          ║
╠═════════════════════╦═════════════════════╦══════════════════════════════╣
║  TG: Личные чаты     ║  TG: Групповые чаты  ║ Битрикс24: "Людмила"       ║
║  (aiogram polling)   ║  (aiogram polling)   ║ (реальный пользователь)    ║
║                      ║                      ║                             ║
║  - Команды/меню      ║  - Мониторинг всех   ║ - Участник чатов            ║
║  - Постановка задач  ║    сообщений         ║ - Наблюдатель задач         ║
║  - Загрузка фото,    ║  - Обнаружение       ║ - Участник проектов         ║
║    файлов, стено-    ║    пропущенных       ║ - Комментарии к задачам     ║
║    грамм созвонов    ║    ответов           ║ - Дайджесты                 ║
║  - @Людмила          ║  - Action items      ║ - @Людмила в чатах          ║
║                      ║  - @Людмила          ║                             ║
╠═════════════════════╩═════════════════════╩══════════════════════════════╣
║                     │             │              │                        ║
║                     ▼             ▼              ▼                        ║
║          ┌───────────────────────────────────────────────────┐           ║
║          │              TRANSPORT ADAPTER                     │           ║
║          │                                                    │           ║
║          │  Вход:  текст / фото / файл / аудио               │           ║
║          │         + user_id + transport_type + chat_type     │           ║
║          │                                                    │           ║
║          │  Выход: OrchestratorResult → форматирование:       │           ║
║          │         TG → HTML + InlineKeyboard                │           ║
║          │         B24 → BBCode + KEYBOARD array             │           ║
║          └────────────────────┬──────────────────────────────┘           ║
║                               │                                          ║
║                               ▼                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║                     ЯДРО АГЕНТА (ReAct Loop)                             ║
║                   НЕ скрипт, а полноценный агент                         ║
║                                                                          ║
║  ┌────────────────────────────────────────────────────────────────┐      ║
║  │                     AGENT EXECUTOR                              │      ║
║  │            (Think → Act → Observe → Repeat)                     │      ║
║  │            max_iterations: 10, timeout: 120s                    │      ║
║  │                                                                 │      ║
║  │   Playbook: playbook.md (обновляется через feedback)            │      ║
║  │   LLM: GLM-4.7 (основной) через OpenRouter                     │      ║
║  │                                                                 │      ║
║  │   ┌──────────────────────────────────────────────────────┐     │      ║
║  │   │                 TOOLS (function calling)               │     │      ║
║  │   │                                                        │     │      ║
║  │   │   Задачи и CRM                                        │     │      ║
║  │   │   ├── create_task()        → задача в Битрикс24       │     │      ║
║  │   │   ├── get_user_tasks()     → задачи пользователя      │     │      ║
║  │   │   ├── comment_on_task()    → комментарий к задаче     │     │      ║
║  │   │   ├── create_meeting()     → встреча в календаре      │     │      ║
║  │   │   ├── get_overdue_tasks()  → просроченные задачи      │     │      ║
║  │   │   └── get_unanswered()     → неотвеченные сообщения   │     │      ║
║  │   │                                                        │     │      ║
║  │   │   Аналитика (от Олега)                                 │     │      ║
║  │   │   ├── get_brand_finance()  → финансы WB/OZON          │     │      ║
║  │   │   ├── get_model_breakdown()→ разбивка по моделям      │     │      ║
║  │   │   ├── get_daily_trend()    → тренды за день           │     │      ║
║  │   │   ├── get_advertising()    → рекламная статистика     │     │      ║
║  │   │   └── ... (12 инструментов)                           │     │      ║
║  │   │                                                        │     │      ║
║  │   │   Мультимодальность                                    │     │      ║
║  │   │   ├── analyze_image()      → Vision: фото/скриншот    │     │      ║
║  │   │   ├── parse_document()     → PDF, DOCX, XLS           │     │      ║
║  │   │   └── process_transcript() → стенограмма созвона      │     │      ║
║  │   │                                                        │     │      ║
║  │   │   Контекст и память                                    │     │      ║
║  │   │   ├── get_user_context()   → история (Supabase)       │     │      ║
║  │   │   ├── get_team_structure() → оргструктура             │     │      ║
║  │   │   └── search_history()     → поиск в чатах            │     │      ║
║  │   └──────────────────────────────────────────────────────┘     │      ║
║  └────────────────────────────────────────────────────────────────┘      ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║                     ПРОАКТИВНЫЙ СЛОЙ (Scheduler)                         ║
║                                                                          ║
║  ┌───────────────────┐ ┌───────────────────┐ ┌────────────────────────┐ ║
║  │  TASK MONITOR      │ │  CHAT MONITOR      │ │  DIGEST & REPORTS      │ ║
║  │                    │ │  (TG + B24)         │ │                        │ ║
║  │  Каждый час:       │ │                     │ │  Утро (по TZ юзера):  │ ║
║  │  • дедлайн 24ч →   │ │  Realtime:          │ │  • персональный        │ ║
║  │    reminder        │ │  • @Людмила →       │ │    дайджест             │ ║
║  │    (по TZ юзера)   │ │    ответ в чате     │ │                        │ ║
║  │  • просрочено →    │ │  • action item →    │ │  Пн 09:00 МСК:        │ ║
║  │    эскалация       │ │    предложить       │ │  • командная сводка    │ ║
║  │  • новая задача → │ │    создать задачу   │ │                        │ ║
║  │    проверка        │ │  • пропущенное →    │ │  После стенограммы:    │ ║
║  │    качества        │ │    напомнить        │ │  • задачи из созвона   │ ║
║  │                    │ │  • обычное →        │ │  • summary в чат B24   │ ║
║  │                    │ │    пропустить       │ │                        │ ║
║  └───────────────────┘ └───────────────────┘ └────────────────────────┘ ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║                     ДАННЫЕ И СЕРВИСЫ                                     ║
║                                                                          ║
║  ┌─────────────┐ ┌─────────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ║
║  │BitrixService│ │ data_layer  │ │ UserCache │ │Supabase│ │ Notion   │ ║
║  │(tasks, im,  │ │(WB/OZON    │ │(сотрудн.  │ │(память,│ │(стено-   │ ║
║  │ users, cal) │ │ PostgreSQL) │ │ + TZ)     │ │контекст│ │ граммы)  │ ║
║  └─────────────┘ └─────────────┘ └──────────┘ └────────┘ └──────────┘ ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

### 2.2 Принцип: один мозг — три лица

```
                       ┌──────────────────────────┐
                       │     AGENT EXECUTOR         │
                       │     (ReAct Loop)           │
                       │                            │
                       │  Playbook + LLM + Tools    │
                       │  GLM-4.7 через OpenRouter  │
                       └──┬──────────┬──────────┬──┘
                          │          │          │
               ┌──────────┘          │          └──────────┐
               ▼                     ▼                     ▼
      ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
      │  TG: Личные      │  │  TG: Групповые   │  │  Битрикс24           │
      │                  │  │                   │  │  (реальный юзер)     │
      │  Формат: HTML    │  │  Формат: HTML     │  │  Формат: BBCode      │
      │  Транспорт:      │  │  Транспорт:       │  │  Транспорт:          │
      │  aiogram         │  │  aiogram          │  │  aiohttp webhook     │
      │  message.answer()│  │  message.reply()  │  │  im.message.add()    │
      └─────────────────┘  └─────────────────┘  └─────────────────────┘
```

### 2.3 Скрипт vs Агент — ключевое отличие

```
БЫЛО (скрипт, линейный):            СТАЛО (агент, ReAct loop):

текст → detect_intent()              текст / фото / файл
  │                                       │
  ├─ "task" → structure_task()            ▼
  │              → confirm               Agent Executor
  │              → create_task()         (Think → Act → Observe → Repeat)
  │                                        │
  ├─ "meeting" → structure_meeting()       ├─ Think: "Пользователь прислал
  │              → confirm                 │   фото ТЗ и просит поставить
  │              → create_meeting()        │   задачу. Сначала распознаю."
  │                                        │
  └─ "unknown" → "не понял"               ├─ Act: analyze_image(photo)
                                           │
                                           ├─ Observe: "ТЗ на разработку
  Жёсткий путь,                            │   лендинга, срок: 28.02"
  нет гибкости,                            │
  нет мультимодальности,                   ├─ Act: get_team_structure()
  нет аналитики                            │
                                           ├─ Think: "Лендинг — задача
                                           │   для дизайнера + разработчика"
                                           │
                                           ├─ Act: create_task(...)
                                           │
                                           └─ Act: comment_on_task(...)

                                     Гибкий, адаптивный,
                                     мультимодальный,
                                     сам выбирает инструменты
```

### 2.4 Обработка стенограммы созвона

```
Пользователь загружает стенограмму
(TG: файл / Notion: ссылка / B24: вложение)
       │
       ▼
┌──────────────────────────┐
│  process_transcript()     │
│  (tool в ReAct loop)      │
│                           │
│  1. Парсинг файла         │
│     (txt / md / pdf)      │
│                           │
│  2. LLM-анализ:           │
│     • участники            │
│     • решения              │
│     • action items         │
│     • сроки                │
│     • ответственные        │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  Агент сам решает:        │
│                           │
│  create_task() x N       │──── → Задачи в Битрикс24
│  send_summary()          │──── → Итог в групповой чат B24
│  notify_users()          │──── → Личные уведомления (по TZ)
│  save_to_context()       │──── → Суммари в Supabase (память)
└──────────────────────────┘
```

### 2.5 Мониторинг чатов (TG + B24)

```
Сообщение в групповом чате
(Telegram или Битрикс24)
       │
       ▼
┌───────────────────────────────────────────┐
│  Chat Monitor (работает по каждому msg)    │
│                                            │
│  1. Это @Людмила?                          │
│     ДА → Agent Executor → ответ в чате     │
│                                            │
│  2. Это action item?                       │
│     "Надо сделать...", "Кто возьмёт?",     │
│     "К пятнице нужно..."                   │
│     ДА → предложить создать задачу         │
│                                            │
│  3. Пропущенный ответ?                     │
│     Подрядчик написал >4 часов назад,      │
│     никто не ответил                       │
│     ДА → напомнить ответственному          │
│                                            │
│  4. Обычная переписка?                     │
│     ДА → сохранить контекст, молчать       │
└───────────────────────────────────────────┘
```

### 2.6 Timezone-aware уведомления

```
Уведомление для пользователя
       │
       ▼
┌─────────────────────────────────────────┐
│  UserCache → bitrix_user.TIME_ZONE      │
│                                          │
│  Персональные:                           │
│  • дайджест утром → по TZ пользователя  │
│  • напоминание о дедлайне → по TZ       │
│  • итог созвона → по TZ                 │
│                                          │
│  Командные:                              │
│  • еженедельная сводка → МСК 09:00      │
│  • эскалация просрочки → МСК            │
└─────────────────────────────────────────┘
```

---

## 3. Настройка Битрикс24 (одноразово, вручную)

| # | Действие | Детали |
|---|----------|--------|
| 1 | Создать пользователя "Людмила" | Админ-панель → Сотрудники → Пригласить. Имя, должность "PM (ИИ)", аватар |
| 2 | Создать локальное приложение | Разработчики → Локальное приложение. Scopes: `im, task, user, calendar, crm` |
| 3 | Авторизовать от имени Людмилы | OAuth flow → `access_token` + `refresh_token` → `.env` |
| 4 | Подписать на события | Скрипт `register_events.py` → `event.bind` |
| 5 | Добавить в чаты и проекты | Как обычного сотрудника |

---

## 4. Структура файлов

### Новые файлы

```
agents/lyudmila/
├── bitrix_bot/                             # Bitrix24 интерфейс
│   ├── __init__.py
│   ├── webhook_server.py                   # aiohttp: приём событий
│   ├── bitrix_user_client.py               # API от имени Людмилы
│   ├── event_router.py                     # маршрутизация событий
│   ├── format_adapter.py                   # HTML ↔ BBCode
│   └── session_manager.py                  # состояние диалогов B24
│
├── core/                                    # Ядро агента (transport-agnostic)
│   ├── __init__.py
│   ├── agent_executor.py                   # ReAct loop (Think→Act→Observe)
│   ├── agent_tools.py                      # Определения всех tools
│   ├── tool_executor.py                    # Выполнение tools
│   ├── transport_adapter.py                # Нормализация входа/выхода
│   └── playbook.md                         # Знания и правила агента
│
├── monitors/                                # Проактивный слой
│   ├── __init__.py
│   ├── chat_monitor.py                     # Мониторинг чатов TG + B24
│   └── task_monitor.py                     # Контроль дедлайнов
│
├── handlers/                                # TG-хендлеры (групповые чаты)
│   └── group_chat.py                       # НОВЫЙ: мониторинг TG-групп
│
├── scripts/
│   ├── create_bitrix_user.py               # Создание пользователя
│   └── register_events.py                  # Подписка на события
│
├── services/                                # Существующие + новые
│   ├── multimodal_service.py               # НОВЫЙ: Vision + парсинг файлов
│   └── transcript_service.py               # НОВЫЙ: обработка стенограмм
```

### Модифицируемые файлы

| Файл | Что меняется |
|------|-------------|
| `config.py` | + `BITRIX_APP_CLIENT_ID`, `BITRIX_APP_SECRET`, `BITRIX_USER_ACCESS_TOKEN`, `BITRIX_USER_REFRESH_TOKEN`, `BITRIX_USER_ID`, `BITRIX_BOT_PORT`, `BITRIX_APP_TOKEN`, `VISION_MODEL` |
| `main.py` | + запуск aiohttp webhook рядом с TG polling через `asyncio.gather()` |
| `persona.py` | + промпты: `CHAT_ANALYSIS_PROMPT`, `TASK_QUALITY_PROMPT`, `TRANSCRIPT_PROMPT`. Расширение intent: + "analytics", + "chat_action" |
| `AGENT_SPEC.md` | Полное обновление спецификации |

### Переиспользуемые компоненты (без изменений)

| Компонент | Файл | Роль |
|-----------|------|------|
| LyudaAI | `services/lyuda_ai.py` | Intent detection, structuring (уже на OpenRouter) |
| BitrixService | `services/bitrix_service.py` | CRUD задач, пользователей |
| BitrixClient | `shared/clients/bitrix_oauth.py` | OAuth token management |
| OpenRouterClient | `shared/clients/openrouter_client.py` | Единый LLM-провайдер |
| DigestService | `services/digest_service.py` | Утренние дайджесты |
| WeeklyDigestService | `services/weekly_digest_service.py` | Еженедельные сводки |
| UserCache | `services/user_cache.py` | Кеш сотрудников |
| execute_tool (Олег) | `agents/oleg/services/agent_tools.py` | 12 аналитических инструментов |
| data_layer | `shared/data_layer.py` | SQL-запросы к WB/OZON |

---

## 5. Потоки данных

### 5.1 Реактивные (по событиям)

```
Сообщение в TG-группе → aiogram handler
  → chat_monitor
    ├── @Людмила? → Agent Executor → message.reply() (HTML)
    ├── action item? → предложить задачу в чате
    ├── пропущенный ответ? → напомнить ответственному
    └── обычное → сохранить контекст, молчать

Сообщение в B24-чате → ONIMESSAGEADD → webhook_server
  → event_router
    → chat_monitor (тот же!)
      ├── @Людмила? → Agent Executor → im.message.add() (BBCode)
      ├── action item? → предложить задачу
      └── ...

Новая задача в B24 → ONTASKADD → webhook_server
  → task_monitor
    → Agent Executor → AI-проверка качества → comment_on_task()

Загрузка стенограммы → TG / B24
  → Agent Executor
    → process_transcript() → create_task() x N → send_summary()
```

### 5.2 Проактивные (по расписанию)

```
Каждый час → task_monitor.check_deadlines()
  ├── дедлайн через 24ч → reminder (по TZ пользователя)
  ├── дедлайн сегодня → утреннее напоминание (по TZ)
  ├── просрочено → комментарий + уведомление постановщику
  └── просрочено >3 дней → эскалация в групповой чат

Утро (по TZ каждого юзера) → digest_service
  → персональный дайджест → TG + B24 личное сообщение

Пн 09:00 МСК → weekly_service
  → командная сводка → B24 групповой чат + TG-группа

Раз в 4 часа → chat_monitor.check_unanswered()
  → неотвеченные >4ч → напоминание ответственному
```

---

## 6. Фазы реализации

### Фаза 1: Ядро агента (ReAct loop)

**Цель**: заменить линейный скрипт на полноценный ReAct-агент

| Задача | Файл | Описание |
|--------|------|----------|
| Agent Executor | `core/agent_executor.py` | Think→Act→Observe цикл, max 10 итераций |
| Tool definitions | `core/agent_tools.py` | Все tools в формате OpenAI function calling |
| Tool executor | `core/tool_executor.py` | Выполнение tools, возврат результата |
| Playbook | `core/playbook.md` | Знания агента (из persona.py + расширение) |
| Transport adapter | `core/transport_adapter.py` | AgentMessage ↔ OrchestratorResult |

**Проверка**: тот же TG-бот, но внутри работает ReAct loop вместо if/else

### Фаза 2: Мультимодальность

**Цель**: фото, скриншоты, файлы, стенограммы

| Задача | Файл | Описание |
|--------|------|----------|
| Vision service | `services/multimodal_service.py` | analyze_image() через Vision API |
| Document parser | `services/multimodal_service.py` | PDF, DOCX, XLS → текст |
| Transcript service | `services/transcript_service.py` | Стенограмма → задачи + summary |
| Config | `config.py` | + `VISION_MODEL` |

**Проверка**: отправить фото ТЗ в TG → агент распознаёт и создаёт задачу

### Фаза 3: TG групповые чаты

**Цель**: Людмила — участник рабочих TG-групп

| Задача | Файл | Описание |
|--------|------|----------|
| Group handler | `handlers/group_chat.py` | aiogram handler для групповых чатов |
| Chat monitor | `monitors/chat_monitor.py` | Анализ сообщений: action items, пропущенные |
| Persona prompts | `persona.py` | + `CHAT_ANALYSIS_PROMPT` |

**Проверка**: в TG-группе написать "надо сделать отчёт к пятнице" → Людмила предложит задачу

### Фаза 4: Битрикс24 пользователь

**Цель**: реальный аккаунт Людмилы в B24

| Задача | Файл | Описание |
|--------|------|----------|
| Config | `config.py` | + все BITRIX_APP_* переменные |
| User client | `bitrix_bot/bitrix_user_client.py` | im.message.add, task.comment от имени Людмилы |
| Webhook server | `bitrix_bot/webhook_server.py` | aiohttp, валидация app_token |
| Event router | `bitrix_bot/event_router.py` | ONIMESSAGEADD, ONTASKADD, ONTASKUPDATE |
| Format adapter | `bitrix_bot/format_adapter.py` | HTML ↔ BBCode |
| Session manager | `bitrix_bot/session_manager.py` | Состояние диалогов B24 |
| Main.py | `main.py` | + запуск aiohttp через asyncio.gather() |
| Setup scripts | `scripts/` | create_bitrix_user.py, register_events.py |

**Проверка**: написать @Людмила в B24-чате → получить ответ

### Фаза 5: PM-контроль задач

**Цель**: проактивный контроль как проджект-менеджер

| Задача | Файл | Описание |
|--------|------|----------|
| Task monitor | `monitors/task_monitor.py` | Дедлайны, просрочки, качество новых задач |
| Persona prompts | `persona.py` | + `TASK_QUALITY_PROMPT`, `DEADLINE_REMINDER_PROMPT` |
| TZ-aware scheduling | `services/scheduler_service.py` | Уведомления по TZ пользователя из Битрикс24 |

**Проверка**: создать задачу без дедлайна → Людмила пишет комментарий

### Фаза 6: Аналитика + сводки в B24

**Цель**: аналитика WB/OZON + дайджесты через оба канала

| Задача | Файл | Описание |
|--------|------|----------|
| Oleg tools import | `core/agent_tools.py` | + 12 инструментов аналитики |
| Intent "analytics" | `persona.py` | Расширение intent detection |
| Дайджесты в B24 | `main.py` | + рассылка через im.message.add |

**Проверка**: @Людмила какая маржа за вчера? → данные WB/OZON в чате

### Фаза 7: Укрепление

| Задача | Описание |
|--------|----------|
| nginx + HTTPS | Reverse proxy для webhook endpoint, Let's Encrypt |
| Rate limiting | Контроль частоты исходящих сообщений |
| Логирование | Структурированные логи для всех событий |
| Документация | Обновление AGENT_SPEC.md, docs/ |
| Тесты | Интеграционные тесты для ReAct loop и tools |

---

## 7. Стек технологий

| Слой | Технология |
|------|-----------|
| Agent loop | ReAct (Think→Act→Observe), max 10 итераций |
| LLM (основной) | GLM-4.7 через OpenRouter |
| LLM (быстрый) | GLM-4.7-flash через OpenRouter (intent detection) |
| LLM (vision) | модель с Vision API через OpenRouter |
| TG framework | aiogram 3.15 |
| B24 webhook | aiohttp (транзитивная зависимость aiogram) |
| Scheduler | APScheduler |
| Данные | PostgreSQL (WB/OZON), Supabase (память), SQLite (локальный кеш) |
| OAuth | shared/clients/bitrix_oauth.py |

**Новые pip-зависимости: НЕТ** (aiohttp уже есть через aiogram)

---

## 8. Верификация по фазам

| # | Тест | Ожидание |
|---|------|----------|
| 1 | TG: "Поставь задачу Насте — отчёт к пятнице" | Агент через ReAct: structure → create → comment |
| 2 | TG: отправить фото ТЗ | Агент: analyze_image → create_task |
| 3 | TG: загрузить стенограмму созвона | Агент: extract tasks → create x N → summary |
| 4 | TG-группа: "надо сделать отчёт" | Людмила предлагает создать задачу |
| 5 | TG-группа: подрядчик написал 4ч назад без ответа | Людмила напоминает ответственному |
| 6 | B24: @Людмила в чате | Ответ в BBCode |
| 7 | B24: новая задача без дедлайна | Комментарий с рекомендацией |
| 8 | B24: просроченная задача | Напоминание исполнителю (по его TZ) |
| 9 | Любой канал: "какая маржа за вчера?" | Данные WB/OZON из инструментов Олега |
| 10 | Пн 09:00 МСК | Командная сводка в B24-чат и TG-группу |
