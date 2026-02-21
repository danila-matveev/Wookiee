# Development History

> Последние 10 записей. Старые записи переносятся в docs/archive/.
> Шаблон: [templates/development-history.md](templates/development-history.md)

---

## [2026-02-21] Cleanup & Stabilization: runtime contour narrowed

### Что сделано
- Добавлен baseline-отчёт: `docs/archive/baseline-2026-02-21.md` и pre-cleanup tag `pre-cleanup-2026-02-21`
- Исправлены падения price-analysis тестов:
  - контракт спроса: `orders_count` (основной) + deprecated fallback `sales_count`
  - нормализация нечисловых метрик регрессии (NaN/inf не выходят в публичный результат)
  - стабилизирован recommendation flow для fallback-режима
- Добавлен quality gate CI: `.github/workflows/ci.yml` (Python 3.11, compileall, pytest)
- Обновлён deploy sequencing: деплой запускается после успешного CI на `main`
- Реструктурирован модуль WB локализации:
  - активный runtime перенесён в `services/wb_localization/`
  - новый entrypoint: `python -m services.wb_localization.run_localization`
  - `services/vasily_api` переведён на новый сервисный модуль
- Удалены из активного контура `agents/lyudmila` и агентный runtime Василия:
  - код перенесён в архив: `docs/archive/retired_agents/`
  - историческая дока Людмилы перенесена в `docs/archive/agents/lyudmila-bot.md`
- Планы нормализованы:
  - active: `docs/plans/ibrahim-deploy-and-etl.md`
  - retired: `docs/archive/plans/lyudmila-bitrix24-agent-retired.md`

### Зачем
Зафиксировать рабочий прод-контур после переноса проекта на новый сервер, убрать лишний runtime-слой и сделать релизы зависимыми от реального состояния тестов.

### Обновлено
- [x] `agents/oleg/services/price_analysis/regression_engine.py`
- [x] `agents/oleg/services/price_analysis/recommendation_engine.py`
- [x] `.github/workflows/ci.yml`
- [x] `.github/workflows/deploy.yml`
- [x] `services/wb_localization/*`
- [x] `services/vasily_api/app.py`
- [x] `docs/index.md`, `docs/architecture.md`, `docs/agents/README.md`, `docs/QUICKSTART.md`, `docs/guides/environment-setup.md`
- [x] `README.md`, `AGENTS.md`, `docs/adr.md`

---

## [2026-02-18] Fix: ложноположительное уведомление "Данные готовы"

### Что сделано
- Ужесточены пороги проверки готовности данных в `DataFreshnessService`: выручка 50%→70%, маржа 50%→90%
- Добавлена проверка абсолютного заполнения маржи (>= 90% от общего числа строк)
- Добавлена санитарная проверка маржа/выручка (>= 5%)
- Добавлена проверка MAX(date) = вчера
- Уведомление теперь показывает % заполнения маржи
- Синхронизированы пороги CLI-скрипта `check_data_ready.py`

### Зачем
18.02.2026 агент Олег отправил уведомление "Данные за 17.02.2026 готовы", но маржинальные данные WB не были полностью загружены (Power BI показывал "WB до 16.02"). Пороги 50% были слишком мягкими.

### Обновлено
- [x] `agents/oleg/services/data_freshness_service.py` (пороги + новые проверки)
- [x] `scripts/check_data_ready.py` (синхронизация порогов)
- [x] `docs/database/DATA_QUALITY_NOTES.md` (п.12)

---

## [2026-02-16] Уровни автономии, классификация по роли, экономические правила

### Что сделано
- Добавлены уровни автономии (0-3) в `docs/guides/agent-principles.md` — каждый инструмент агента получает явный уровень
- Обновлён реестр инструментов — добавлена колонка "Автономия"
- Добавлена 3-слойная классификация агентов (сенсор/аналитик/исполнитель) в `docs/architecture.md`
- Добавлены экономические правила в `AGENTS.md` — минимальная достаточность модели, confidence-based routing
- ADR-006 зафиксирован с backlog будущих улучшений

### Зачем
Формализация правил из `06-rules-and-templates.md` (Блок 3: агентный проект). При масштабировании системы агентов нужны чёткие правила: что агент делает сам, какую модель использовать, как классифицировать агентов по роли.

### Обновлено
- [x] `docs/guides/agent-principles.md` (секция 2.5 + реестр)
- [x] `docs/architecture.md` (классификация по роли)
- [x] `AGENTS.md` (экономика агентов)
- [x] `docs/adr.md` (ADR-006)

---

## [2026-02-16] Рефрейминг документации: Data Hub → AI Agent System

### Что сделано
- Обновлено позиционирование проекта: из "Wookiee Analytics — Data Hub" в "Wookiee — AI Agent System"
- Ключевой принцип: агенты — ядро системы, боты — только интерфейсы
- Обновлены: `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/architecture.md`, `docs/agents/README.md`, `docs/index.md`
- Создана документация агента Ибрагим: `docs/agents/ibrahim.md`
- Добавлена команда `/update-docs` для регулярной проверки актуальности документации
- Расширены DoD и PR-шаблон: обязательная проверка документации при архитектурных изменениях
- Добавлено правило в AGENTS.md: обновление документации при архитектурных изменениях
- ADR-004 и ADR-005 зафиксированы

### Зачем
Проект эволюционировал из аналитической платформы в систему AI-агентов для управления бизнесом. Документация не отражала новую концепцию. Также отсутствовал процесс регулярного обновления документации при изменениях проекта.

### Обновлено
- [x] `README.md`, `AGENTS.md`, `CLAUDE.md` (рефрейминг)
- [x] `docs/architecture.md` (полная переработка)
- [x] `docs/agents/README.md`, `docs/index.md` (обновление реестра)
- [x] `docs/agents/ibrahim.md` (создан)
- [x] `.claude/commands/update-docs.md` (создан)
- [x] `docs/guides/dod.md`, `.github/PULL_REQUEST_TEMPLATE.md` (расширены)
- [x] `docs/adr.md` (ADR-004, ADR-005)

### Следующие шаги
- Обновить docs/agents/telegram-bot.md (рефрейминг Олега как AI-агента, не бота)
- Обновить docs/agents/lyudmila-bot.md (аналогично)

---

## [2026-02-11] IEE-агент Людмила — полная реализация

### Что сделано
- Создан модуль `lyudmila_bot/` — отдельный Telegram-бот (aiogram 3.15)
- Bitrix24 async-обёртка (`services/bitrix_service.py`) через `asyncio.to_thread()`
- Кеш сотрудников с нечётким поиском русских имён (54 уменьшительных, thefuzz)
- SQLite хранилище пользователей и лога действий
- Email-авторизация через Bitrix24
- Claude API клиент (Sonnet 4.5) — мозг Людмилы
- ИИ-ассистент создания задач: валидация процесс/задача, чеклист, целевой результат
- ИИ-ассистент создания встреч: повестка, подготовка, pre-reading
- Утренний дайджест с ИИ-подсказками (per-user timezone, APScheduler)
- Личность Людмилы: промпты, характер, правила (`persona.py`)
- UX без тупиков: кнопка «Назад» на каждом экране, `/menu` из любого FSM-состояния
- Документация: `docs/agents/lyudmila-bot.md`, обновлены `docs/agents/README.md`, `AGENTS.md`

### Зачем
Команде Wookiee нужен ИИ-ассистент для структурной работы с CRM Bitrix24. Людмила экономит время: трансформирует сырые описания задач и встреч в бизнес-ориентированные документы с чёткими целевыми результатами.

### Обновлено
- [x] `lyudmila_bot/` (24 Python-файла, ~123 KB)
- [x] `docs/agents/lyudmila-bot.md` (создан)
- [x] `docs/agents/README.md` (добавлена Людмила)
- [x] `AGENTS.md` (добавлен компонент)
- [x] `docs/development-history.md` (эта запись)

### Следующие шаги
- Live-тестирование бота в Telegram
- Dockerfile + docker-compose для деплоя
- ADR для архитектурного решения (отдельный бот vs модуль)

---

## [2026-02-09] Реструктуризация проекта под 2030ai/project_template

### Что сделано
- Создан AGENTS.md как единый источник правил для AI-агентов
- CLAUDE.md переписан в тонкую обёртку-ссылку на AGENTS.md
- Создана структура docs/ (index, architecture, adr, guides, templates)
- scripts/config.py переведён на python-dotenv (секреты убраны из кода)
- .gitignore расширен, добавлен .cursorignore
- Санированы bot/.env.example и docs/database/DATABASE_REFERENCE.md
- Создан корневой .env.example
- Добавлены .claude/commands/ и .claude/skills/

### Зачем
Подготовка проекта к публикации на GitHub. Стандартизация документации для AI-agent-first разработки.

### Обновлено
- [x] AGENTS.md (создан)
- [x] CLAUDE.md (переписан)
- [x] README.md (обновлён)
- [x] docs/ (создана вся структура)
- [x] .gitignore (расширен)
- [x] ADR-001, ADR-002, ADR-003

### Следующие шаги
- Инициализация git-репозитория и первый push на GitHub
- Настройка CI/CD (GitHub Actions)
