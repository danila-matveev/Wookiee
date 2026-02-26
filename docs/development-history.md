# Development History

> Последние 10 записей. Старые записи переносятся в docs/archive/.
> Шаблон: [templates/development-history.md](templates/development-history.md)

---

## [2026-02-25] Аудит SKU Database + ТЗ Dashboard каталога

### Что сделано
- **Cleanup sku_database/**: удалены мёртвые скрипты (`examples.py`, `db_shell.py`, `import_to_supabase.py`, `diagnose_security.py`), удалены `docker-compose.yml` и `deploy 2.sh`
- Удалён неиспользуемый `MAPPING_ARTIKULY` из `config/mapping.py`
- Синхронизированы `schema.sql` и `models.py` с живой БД (добавлен `tip_kollekcii`)
- Добавлен триггер аудита на `modeli_osnova` (ранее отсутствовал)
- Обновлён `sku_database/README.md` (убраны ссылки на несуществующие файлы)
- **Полный аудит БД**: программное чтение всех 7 каталожных листов Google Sheets через gspread, сравнение 90+ колонок Sheets с 16 таблицами Supabase
- **10 предложений по улучшению БД**: от импорта Ozon-склеек (CRITICAL) до compound UNIQUE на artikuly
- **ТЗ дашборда каталога**: архитектура, ER-диаграмма, 12 модулей UI с wireframes, 7 user journeys с блок-схемами, RBAC (3 роли), workflow статусов, Mermaid-диаграммы

### Зачем
Подготовка к созданию визуального дашборда управления товарным каталогом (замена Google Sheets). Аудит выявил 5 критических проблем (пустая таблица `skleyki_ozon`, ~60 неимпортируемых колонок, хардкод в views).

### Обновлено
- [x] `sku_database/config/mapping.py` (удалён MAPPING_ARTIKULY)
- [x] `sku_database/database/schema.sql` (tip_kollekcii)
- [x] `sku_database/database/models.py` (tip_kollekcii)
- [x] `sku_database/database/triggers.sql` (modeli_osnova trigger)
- [x] `sku_database/README.md` (полное обновление)
- [x] `docs/plans/2026-02-25-db-audit-results.md` (создан)
- [x] `docs/plans/2026-02-25-db-improvement-proposals.md` (создан)
- [x] `docs/plans/2026-02-25-dashboard-tz.md` (создан)
- [x] `docs/index.md` (добавлены новые планы)
- [x] `docs/development-history.md` (эта запись)

---

## [2026-02-23] Таблица 1.1: реклама WB/OZON (adv_internal/adv_external)

### Что сделано
- В таблице «1.1 Ключевые метрики» внутренняя/внешняя реклама оказались перепутаны и внутренняя не включала OZON из-за старого workaround в `shared/data_layer.py`.
- После обновления ETL WB поля `reclama` / `reclama_vn` снова соответствуют схеме, поэтому маппинг вернули к штатному: `adv_internal = SUM(reclama)`, `adv_external = SUM(reclama_vn)` во всех WB-запросах.
- Обновлён плейбук Олега и data quality notes, чтобы зафиксировать новый (нормальный) маппинг и напоминание о сверке с PowerBI.

### Обновлено
- [x] `shared/data_layer.py`
- [x] `agents/oleg/playbook.md`
- [x] `docs/database/DATA_QUALITY_NOTES.md`
- [x] `docs/development-history.md`

---

## [2026-02-21] WB таблицы 5.1/5.2: исправлен маппинг рекламы в playbook

### Что сделано
- Проверена цепочка расчёта и передачи полей рекламы для таблиц «5.1 Драйверы прибыли (WB)» и «5.2 Анти‑драйверы (WB)».
- Подтверждено, что Python/SQL маппинг в runtime корректный: WB отдаёт `adv_internal`/`adv_external` из `shared/data_layer.py`.
- Найдена корневая причина: в `agents/oleg/playbook.md` были противоречивые инструкции (местами устаревший маппинг `reclama`/`reclama_vn`), из-за чего LLM путал колонки внутренней и внешней рекламы именно в WB-таблицах.
- В playbook унифицированы правила: использовать только нормализованные поля tool-ответов `adv_internal` и `adv_external`; отдельно зафиксирован фактический backend-маппинг для WB и OZON.

### Обновлено
- [x] `agents/oleg/playbook.md`
- [x] `docs/development-history.md`

---

## [2026-02-21] Таблица 1.1 (Notion): Оборачиваемость и Годовой ROI %

### Что сделано
- В отчёте Notion в таблице «1.1 Ключевые метрики» не отображались «Годовой ROI %», а «Оборачиваемость продаж (дни)» была 0.
- В плейбуке добавлено явное требование заполнять строки «Оборачиваемость продаж (дни)» и «Годовой ROI %» из `brand.current.turnover_days` и `brand.current.roi_annual`.
- В описание инструмента `get_brand_finance` добавлено указание на поля `turnover_days` и `roi_annual` для таблицы 1.1.
- В `get_total_avg_stock` добавлен fallback: при отсутствии данных за период используется средний остаток за последние 7 дней (учитывает задержку ETL).
- В `agents/oleg/services/agent_tools.py` исправлен расчёт годового ROI: теперь используется `turnover_raw` (без раннего округления оборачиваемости), что устраняет искажение `roi_annual`.
- В `agents/oleg/services/agent_tools.py` уточнена точность `Δ абс.` для оборачиваемости: `turnover_days_change_abs` сохраняется с 1 знаком после запятой.
- В ответе `get_brand_finance` добавлен явный блок `brand.key_metrics_1_1` с полями `turnover_days` и `roi_annual` (current/previous/change_abs/change_pct) для более надёжной передачи в LLM при заполнении таблицы 1.1.

### Обновлено
- [x] `agents/oleg/playbook.md`
- [x] `agents/oleg/services/agent_tools.py`
- [x] `shared/data_layer.py`
- [x] `docs/development-history.md`

---

## [2026-02-21] WB: исправлен маппинг внутренняя/внешняя реклама в таблицах драйверов/анти-драйверов

### Что сделано
- В таблице «5.2 Анти-драйверы (WB)» (и 5.1, 6.1, 6.2) колонки «Внутр. реклама (тек)» и «Внешн. реклама (тек)» заполнялись неверно.
- Причина: в источнике WB внутренняя реклама приходит в `reclama_vn`, внешняя — в `reclama`; маппинг в коде был обратным.
- Во всех WB-запросах в `shared/data_layer.py` исправлен маппинг: `adv_internal = SUM(reclama_vn)`, `adv_external = SUM(reclama)`.

### Обновлено
- [x] `shared/data_layer.py` (все функции, возвращающие adv_internal/adv_external для WB)
- [x] `docs/database/DATA_QUALITY_NOTES.md` (раздел 11)
- [x] `docs/development-history.md`

---

## [2026-02-21] Deep Price Analysis System: high-precision elasticity

### Что сделано
- Внедрен `DeepElasticityService`: высокоточный анализ эластичности на основе поартикульных заказов (`orders`/`postings`).
- Реализована сегментация SKU по ролям: 'Развитие' (Продается, Новый, Запуск) vs 'Ликвидация' (Выводим).
- Внедрен механизм First-Sale Alignment (отсечение периодов до первого заказа SKU).
- Реализован расчет средневзвешенной цены дня (Weighted Average Price) для групп SKU с учетом объема заказов.
- Добавлен инструмент `get_deep_price_analysis` для агента Олега.
- Исправлены ошибки типизации (Decimal/float) при передаче данных в регрессионный движок.
- Актуализирована документация аналитического контура.

### Зачем
Повысить точность ценовых рекомендаций за счет анализа спроса на уровне первоисточника (заказы) и разделения стратегий для новинок и выводимых товаров.

### Обновлено
- [x] `agents/oleg/services/price_analysis/deep_elasticity_service.py` (создан)
- [x] `agents/oleg/services/price_tools.py` (добавлен инструмент)
- [x] `agents/oleg/services/price_analysis/regression_engine.py` (fix typing)
- [x] `docs/agents/analytics-engine.md`
- [x] `docs/development-history.md`

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

