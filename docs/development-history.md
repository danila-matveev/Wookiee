# Development History

> Последние 10 записей. Старые записи переносятся в docs/archive/.
> Шаблон: [templates/development-history.md](templates/development-history.md)

---

## 2026-04-26 — Refactor v3 Phase 1 (PRs #51-58)

8-PR рефакторинг + Stage C верификация:
- PR #51: Удаление бинарного мусора (604 MB output/, playwright snapshots, docx/png клиппер)
- PR #52: Hardening .gitignore (output/, .playwright-mcp/, *.docx)
- PR #53: Коммит активных неотслеживаемых сервисов + READMEs (creative_kb, wb_logistics_api, wb_localization calculators)
- PR #54: Удаление мёртвого кода (mcp_servers/, finolog_categorizer, knowledge_base, abc_analysis*, stale scripts/docs)
- PR #55: Retirement Oleg V2 — финансовый AI-агент выведен из продакшена
- PR #56: Hub trim — 2 модуля (Комьюнити + Агенты), comms→community rename, +supabase-js
- PR #57: Docs-unification — ONBOARDING, docs/skills/, module READMEs, observability→tool_telemetry
- PR #58: Stage C верификация-фиксы — purge `.planning/{archive/v1.0,milestones,phases,research,debug}/` (190 файлов, ~1 MB), +7 docs/config с устаревшими путями (services.observability, agents/oleg, services/marketplace_etl)

Итог: ≥780 MB освобождено на диске, репозиторий очищен от Oleg V2, Hub сокращён ~65% по файлам, чёткий active runtime список (8 сервисов + 14 скиллов).

Ручной post-step (F3): пользователь удаляет 4 `wookiee-*` записи из `.claude/settings.local.json` (gitignored, нельзя автоматизировать через PR).

---

## [2026-04-15] WB Tariffs ETL: bootstrap миграции, исторический импорт и daily cron

### Что сделано
- Обновлена миграция `007_create_wb_tariffs.py`: подключение переведено на `SUPABASE_*`, в таблицу `public.wb_tariffs` добавлен `storage_coef`, а RLS/policies сделаны идемпотентными для повторного запуска.
- В `shared/data_layer/_connection.py` добавлен единый helper `_get_supabase_connection()`, и логистический аудит переведён на него для чтения и записи тарифов.
- `tariff_collector.py` теперь сохраняет `storage_coef`, использует `SUPABASE_*` и остаётся безопасным для повторного запуска через `ON CONFLICT`.
- Добавлен исторический импорт `import_historical_tariffs.py`: чтение Excel `Тарифы на логискику.xlsx`, batched upsert по 1000 строк и логирование прогресса.
- Добавлен bootstrap-скрипт `setup_wb_tariffs.py`: применяет миграцию, импортирует историю, дозаполняет gap через WB API и печатает итоговую верификацию `COUNT/MIN/MAX`.
- Добавлена host-level cron-обёртка `cron_tariff_collector.sh` для сервера Timeweb и обновлена документация по ручной установке `crontab`.
- Расширены тесты логистического аудита для parsing/ETL helper-логики и обновлены README/algorithm docs под новый поток тарифов.

### Зачем
До изменения таблица `wb_tariffs` не была развернута в Supabase, исторические коэффициенты жили только в локальном Excel, а ежедневный сбор не был подготовлен к серверному cron. Из-за этого Tier 2 lookup в логистическом аудите был ненадёжен и зависел от ручной подготовки окружения.

### Обновлено
- [x] `database/sku/scripts/migrations/007_create_wb_tariffs.py`
- [x] `shared/data_layer/_connection.py`
- [x] `services/logistics_audit/calculators/warehouse_coef_resolver.py`
- [x] `services/logistics_audit/etl/tariff_collector.py`
- [x] `services/logistics_audit/etl/import_historical_tariffs.py`
- [x] `services/logistics_audit/etl/setup_wb_tariffs.py`
- [x] `services/logistics_audit/etl/cron_tariff_collector.sh`
- [x] `tests/services/logistics_audit/test_api_parsing.py`
- [x] `tests/services/logistics_audit/test_tariff_etl.py`
- [x] `README.md`
- [x] `services/logistics_audit/README.md`
- [x] `docs/logistics-audit-algorithm-v2.md`
- [x] `docs/development-history.md`

---

## [2026-02-25] Аудит SKU Database + ТЗ Dashboard каталога

### Что сделано
- **Cleanup database/sku/**: удалены мёртвые скрипты (`examples.py`, `db_shell.py`, `import_to_supabase.py`, `diagnose_security.py`), удалены `docker-compose.yml` и `deploy 2.sh`
- Удалён неиспользуемый `MAPPING_ARTIKULY` из `config/mapping.py`
- Синхронизированы `schema.sql` и `models.py` с живой БД (добавлен `tip_kollekcii`)
- Добавлен триггер аудита на `modeli_osnova` (ранее отсутствовал)
- Обновлён `database/sku/README.md` (убраны ссылки на несуществующие файлы)
- **Полный аудит БД**: программное чтение всех 7 каталожных листов Google Sheets через gspread, сравнение 90+ колонок Sheets с 16 таблицами Supabase
- **10 предложений по улучшению БД**: от импорта Ozon-склеек (CRITICAL) до compound UNIQUE на artikuly
- **ТЗ дашборда каталога**: архитектура, ER-диаграмма, 12 модулей UI с wireframes, 7 user journeys с блок-схемами, RBAC (3 роли), workflow статусов, Mermaid-диаграммы

### Зачем
Подготовка к созданию визуального дашборда управления товарным каталогом (замена Google Sheets). Аудит выявил 5 критических проблем (пустая таблица `skleyki_ozon`, ~60 неимпортируемых колонок, хардкод в views).

### Обновлено
- [x] `database/sku/config/mapping.py` (удалён MAPPING_ARTIKULY)
- [x] `database/sku/database/schema.sql` (tip_kollekcii)
- [x] `database/sku/database/models.py` (tip_kollekcii)
- [x] `database/sku/database/triggers.sql` (modeli_osnova trigger)
- [x] `database/sku/README.md` (полное обновление)
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

