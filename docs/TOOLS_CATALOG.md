# Каталог инструментов Wookiee

Полный справочник скиллов, сервисов и скриптов проекта. Обновлён 15 апреля 2026.

---

## 1. Скиллы (проектные)

### 1.1 /finance-report — Финансовый анализ

**Статус:** ✅ v3, работает

Глубокий финансовый анализ бренда (WB+OZON). 3-волновой аналитический движок (детекция аномалий → диагностика причин → стратегия действий), 2 канальных аналитика (WB + OZON), верификатор, синтезайзер. Генерирует 12-секционный отчёт с callout-блоками, публикует в Notion.

- **Источники данных:** PostgreSQL (WB/OZON), Supabase (статусы моделей), plan_article (план из БД)
- **Результат:** MD файл + Notion страница
- **Запуск:** `/finance-report 2026-04-10` (дневной) | `/finance-report 2026-03-30 2026-04-05` (недельный)
- **Расположение:** `.claude/skills/finance-report/`

---

### 1.2 /marketing-report — Маркетинговый анализ

**Статус:** ✅ v1, работает

Анализ маркетинга: P&L по каналам, 3 воронки трафика (органика WB, платный WB, OZON), данные из Google Sheets (блогеры, ВК/Яндекс, SMM), матрица эффективности моделей (Growth/Harvest/Optimize/Cut).

- **Источники данных:** PostgreSQL (WB/OZON), Google Sheets (3 таблицы: блогеры, внешний трафик, SMM)
- **Результат:** MD файл + Notion страница
- **Запуск:** `/marketing-report 2026-04-10` | `/marketing-report 2026-03-30 2026-04-05`
- **Расположение:** `.claude/skills/marketing-report/`

---

### 1.3 /analytics-report — Мета-оркестратор аналитики

**Статус:** ⏳ Не готов (Plan 5)

Вызывает `/finance-report` + `/marketing-report` + `/funnel-report` последовательно, собирает единый сводный отчёт. Пока не реализован до конца.

- **Расположение:** `.claude/skills/analytics-report/`

---

### 1.4 /abc-audit — ABC-аудит товарной матрицы

**Статус:** ⏳ Требует тестирования

ABC-классификация артикулов по марже и обороту. Матрица 3x3 (ABC x ROI), color_code анализ, рекомендации по каждому артикулу. 6 субагентов: сборщик данных, классификатор, аналитик цен, аналитик запасов, стратег, синтезайзер.

- **Источники данных:** PostgreSQL (abc_date), Supabase (статусы)
- **Результат:** MD файл + Notion страница
- **Запуск:** `/abc-audit` | `/abc-audit 2026-03-01 2026-03-31`
- **Расположение:** `.claude/skills/abc-audit/`

---

### 1.5 /reviews-audit — Аудит отзывов и возвратов

**Статус:** ⏳ Требует тестирования

Глубокий анализ отзывов, вопросов и возвратов WB. LLM-кластеризация текстов, модельные карточки, gap-анализ, публикация в Notion.

- **Источники данных:** WB API (отзывы, вопросы), PostgreSQL (возвраты)
- **Результат:** Notion страница с модельными карточками
- **Запуск:** `/reviews-audit` | `/reviews-audit wendy`
- **Расположение:** `.claude/skills/reviews-audit/`

---

### 1.6 /market-review — Обзор рынка и конкурентов

**Статус:** ⏳ Требует тестирования

Ежемесячный обзор рынка через MPStats. Динамика категории, отслеживание конкурентов, сравнение топ-моделей. Публикация в Notion.

- **Источники данных:** MPStats API
- **Результат:** Notion страница
- **Запуск:** `/market-review`
- **Расположение:** `.claude/skills/market-review/`

---

### 1.7 /monthly-plan — Месячный бизнес-план

**Статус:** ⏳ Требует обновления

Генерация бизнес-плана на месяц через multi-wave агентную архитектуру. Таргеты по выручке, марже, рекламе. Действия по моделям.

- **Источники данных:** PostgreSQL (исторические данные), план из БД
- **Результат:** MD файл + Notion страница
- **Запуск:** `/monthly-plan` | `/monthly-plan 2026-05`
- **Расположение:** `.claude/skills/monthly-plan/`

---

### 1.8 /content-search — Поиск фото бренда

**Статус:** ⏳ Требует тестирования

Интерактивный поиск фото из Content KB (~10K изображений). Vector search через pgvector. Помогает подобрать контент под маркетинговую воронку.

- **Источники данных:** PostgreSQL/pgvector (Content KB)
- **Результат:** Список фото с превью
- **Запуск:** `/content-search модель на пляже` | `/content-search каталожное фото Ruby`
- **Расположение:** `.claude/skills/content-search/`

---

### 1.9 /funnel-report — Воронка продаж WB

**Статус:** ✅ v1, работает

Воронка по моделям WB (переходы → корзина → заказы → выкупы). CRO как основная метрика, CR каждого шага с Δ п.п., экономика, значимые артикулы, рекомендации с ₽-эффектом.

- **Источники данных:** PostgreSQL (content_analysis, orders), WB API
- **Результат:** MD файл + Notion страница
- **Запуск:** `/funnel-report 2026-04-07 2026-04-13`
- **Расположение:** `.claude/skills/funnel-report/`

---

### 1.10 /finolog-dds-report — Сводка ДДС (Финолог)

**Статус:** ✅ v2, работает

Анализ ДДС из Финолога: остатки по компаниям (ИП + ООО), cashflow текущий vs предыдущий период, прогноз кассового разрыва через 3 сценария (оптимистичный/базовый/пессимистичный) **относительно плановых операций** (закупки, ФОТ, маркетинг, налоги). Еженедельный + ежемесячный.

Архитектура: Python collector → Analyst LLM → Verifier ‖ Synthesizer → Notion.

- **Источники данных:** Finolog API (остатки, транзакции, прогноз)
- **Коллектор:** `scripts/finolog_dds_report/collect_data.py`
- **Результат:** MD файл + Notion страница (5 секций weekly / 7 monthly)
- **Запуск:** `/finolog-dds-report` (прошлая неделя) | `/finolog-dds-report month` | `/finolog-dds-report 2026-04-01 2026-04-30`
- **Расположение:** `.claude/skills/finolog-dds-report/`

---

### 1.11 /logistics-report — Анализ логистики

**Статус:** ✅ v2, работает

Анализ логистических расходов WB+OZON, индекс локализации, возвраты (закрытый период с лагом 30+ дней), остатки с velocity-adjusted порогами (high/medium/low), рекомендации по допоставкам из МойСклад. Еженедельный + ежемесячный.

Архитектура: Python collector (5 блоков) → Analyst LLM → Verifier ‖ Synthesizer → Notion.

- **Источники данных:** PostgreSQL (abc_date WB/OZON), МойСклад API, vasily.db (ИЛ), inventory.py
- **Коллектор:** `scripts/logistics_report/collect_data.py`
- **Результат:** MD файл + Notion страница (7 секций)
- **Запуск:** `/logistics-report` (прошлая неделя) | `/logistics-report month` | `/logistics-report 2026-04-01 2026-04-30`
- **Расположение:** `.claude/skills/logistics-report/`

---

## 2. Скиллы (глобальные, используемые в Wookiee)

| Скилл | Что делает | Как вызвать |
|---|---|---|
| `/bitrix-task` | Создание задач в Битрикс24 через REST API | `поставь задачу ...` |
| `/bitrix-analytics` | Пульс команды — отчёт по активности в Битрикс24 за неделю | `/bitrix-analytics` |
| `/finolog` | ДДС: расходы, переводы, сводка по счетам, прогноз кассового разрыва | `запиши расход ...` |
| `/telegraph` | Публикация текстов на telegra.ph — мгновенная ссылка | `/telegraph` |
| `/gws-drive` | Google Drive: загрузка, скачивание, управление файлами | `загрузи на диск ...` |
| `/gws-sheets` | Google Sheets: чтение, запись, создание таблиц | `прочитай таблицу ...` |
| `/notebooklm` | Google NotebookLM: создание ноутбуков, артефактов | `/notebooklm` |
| `/workflow-diagram` | Генерация интерактивных workflow-диаграмм (HTML) | `/workflow-diagram ...` |

---

## 3. Сервисы (Python)

### 3.1 sheets_sync — Синхронизация данных в Google Sheets

Загружает данные со складов WB, OZON, МойСклада в Google Sheets. Поддерживает синхронизацию остатков, цен, отзывов, финансовых данных и поисковой аналитики.

- **Источники:** WB API, OZON API, МойСклад API
- **Куда пишет:** Google Sheets
- **Запуск:** `python -m services.sheets_sync.runner wb_stocks` | `all` | `fin_data --start 01.01.2026 --end 07.01.2026`
- **Расположение:** `services/sheets_sync/`

---

### 3.2 content_kb — Индексатор изображений

Сканирует файлы на Яндекс.Диске, скачивает изображения, генерирует embeddings через Gemini Vision API, сохраняет в pgvector для семантического поиска.

- **Источники:** Yandex Disk API
- **Куда пишет:** PostgreSQL/pgvector
- **Запуск:** `python -m services.content_kb.scripts.index_all`
- **Расположение:** `services/content_kb/`
- **Используется в:** `/content-search`

---

### 3.3 knowledge_base — База знаний WB

FastAPI сервис для семантического поиска по учебному контенту (WB Let's Rock: теория, шаблоны, примеры). Чанкирует текст, ищет по similarity.

- **Источники:** PostgreSQL/pgvector
- **Запуск:** `uvicorn services.knowledge_base.app:app --reload`
- **Расположение:** `services/knowledge_base/`

---

### 3.4 logistics_audit — Аудит логистики WB

Рассчитывает переплату за логистику WB. Загружает отчёт WB, рассчитывает стоимость по формуле Оферты (Тариф x Коэф_склада x ИЛ), сравнивает с реальными удержаниями. Генерирует Excel с 11 листами.

- **Источники:** WB API (отчёты, тарифы, габариты), Supabase (тарифы складов)
- **Запуск:** `python -m services.logistics_audit.runner OOO 2026-01-01 2026-03-23`
- **Расположение:** `services/logistics_audit/`

---

### 3.5 wb_localization — Оптимизация индекса локализации

Рассчитывает ИЛ (Индекс Локализации) и ИРП (Индекс Распределения Продаж) для WB. Определяет оптимальные склады для перемещения товара, рассчитывает safety buffer.

- **Источники:** WB API (остатки, заказы, статистика), МойСклад API
- **Запуск:** `python services/wb_localization/run_localization.py --cabinet ooo --days 14`
- **Расположение:** `services/wb_localization/`

---

### 3.6 dashboard_api — Бэкенд WookieeHub

FastAPI сервис с роутами: ABC, Finance, Promo, Series, Stocks, Traffic, Comms. REST endpoints для аналитического дашборда.

- **Источники:** PostgreSQL/Supabase
- **Запуск:** `uvicorn services.dashboard_api.app:app --reload`
- **Расположение:** `services/dashboard_api/`

---

### 3.7 product_matrix_api — Управление товарной матрицей

FastAPI с двумя schema (public + hub). Управляет структурой товаров: статусы, модели, артикулы.

- **Источники:** PostgreSQL/Supabase
- **Запуск:** `uvicorn services.product_matrix_api.app:app --reload`
- **Расположение:** `services/product_matrix_api/`

---

### 3.8 vasily_api — Расчёт перестановок WB

HTTP endpoint для запуска оптимизации перестановок товаров между складами WB. Фоновый worker, статус через Google Apps Script.

- **Источники:** Google Sheets
- **Запуск:** `POST /run` (с X-API-KEY)
- **Расположение:** `services/vasily_api/`

---

### 3.9 observability — Логирование агентов

Fire-and-forget логирование запусков агентов в PostgreSQL. Не выбрасывает ошибки, не блокирует основной поток.

- **Куда пишет:** PostgreSQL/Supabase
- **Расположение:** `services/observability/`

---

## 4. Скрипты (Python)

### 4.1 collect_all.py — Сборщик данных для аналитики

Параллельная загрузка данных из WB, OZON, Google Sheets для аналитических отчётов. Генерирует JSON с 8 блоками: finance, inventory, pricing, advertising, traffic, sku_statuses, plan_fact, external_marketing.

- **Источники:** PostgreSQL (WB/OZON), Supabase, Google Sheets
- **Запуск:** `python scripts/analytics_report/collect_all.py --start 2026-04-05 --end 2026-04-12 --output /tmp/report.json`
- **Используется в:** `/finance-report`, `/marketing-report`

---

### 4.2 abc_analysis.py — ABC-анализ

Классифицирует артикулы внутри каждой модели: Лучшие / Хорошие / Неликвид / Новый. Опционально сохраняет в Notion.

- **Источники:** PostgreSQL (abc_date)
- **Запуск:** `python scripts/abc_analysis.py --channel wb --save --notion`

---

### 4.3 calc_irp.py — Калькулятор ИЛ/ИРП

Загружает заказы за 13 недель через WB Statistics API, определяет локализацию, применяет таблицу коэффициентов КТР/КРП, вычисляет средневзвешенные ИЛ и ИРП.

- **Источники:** WB API (statistics/orders)
- **Запуск:** `python scripts/calc_irp.py --top 20`

---

### 4.4 notion_sync.py — Синхронизация отчётов в Notion

Загружает/обновляет аналитические отчёты в Notion. Если страница существует — обновляет, если нет — создаёт новую.

- **Источники:** Markdown файлы, Notion API
- **Запуск:** `python scripts/notion_sync.py --file reports/2026-02-01_report.md`

---

### 4.5 returns_analysis.py — Анализ возвратов

Анализирует возвраты за 3 месяца по WB и OZON, группирует по модели, показывает суммы в штуках и рублях.

- **Источники:** PostgreSQL (abc_date, returns)
- **Запуск:** `python scripts/returns_analysis.py`

---

### 4.6 sync_sheets_to_supabase.py — Google Sheets → Supabase

Синхронизирует товарную матрицу из Google Sheets в PostgreSQL/Supabase. Таблицы: statusy, modeli, artikuly, tovary. Поддерживает --dry-run.

- **Источники:** Google Sheets API
- **Куда пишет:** PostgreSQL/Supabase
- **Запуск:** `python scripts/sync_sheets_to_supabase.py --level modeli --dry-run`

---

### 4.7 run_report.py — Unified report runner

Запускает отчёты в двух режимах: manual (конкретный тип) и schedule (cron-поллинг 07:00-18:00 МСК каждые 30 мин). Legacy — заменяется скиллами.

- **Запуск:** `python scripts/run_report.py --type daily`

---

## 5. Сводная таблица

| # | Инструмент | Тип | Статус |
|---|---|---|---|
| 1 | `/finance-report` | Скилл | ✅ |
| 2 | `/marketing-report` | Скилл | ✅ |
| 3 | `/analytics-report` | Скилл | ⏳ |
| 4 | `/abc-audit` | Скилл | ⏳ тест |
| 5 | `/reviews-audit` | Скилл | ⏳ тест |
| 6 | `/market-review` | Скилл | ⏳ тест |
| 7 | `/monthly-plan` | Скилл | ⏳ обновить |
| 8 | `/content-search` | Скилл | ⏳ тест |
| 9 | `/bitrix-task` | Глобальный | ✅ |
| 10 | `/bitrix-analytics` | Глобальный | ✅ |
| 11 | `/finolog` | Глобальный | ✅ |
| 12 | `/telegraph` | Глобальный | ✅ |
| 13 | `/gws-drive` | Глобальный | ✅ |
| 14 | `/gws-sheets` | Глобальный | ✅ |
| 15 | `/notebooklm` | Глобальный | ✅ |
| 16 | `/workflow-diagram` | Глобальный | ✅ |
| 17 | sheets_sync | Сервис | ✅ |
| 18 | content_kb | Сервис | ✅ |
| 19 | knowledge_base | Сервис | ✅ |
| 20 | logistics_audit | Сервис | ✅ |
| 21 | wb_localization | Сервис | ✅ |
| 22 | dashboard_api | Сервис | ✅ |
| 23 | product_matrix_api | Сервис | ✅ |
| 24 | vasily_api | Сервис | ✅ |
| 25 | observability | Сервис | ✅ |
| 26 | collect_all.py | Скрипт | ✅ |
| 27 | abc_analysis.py | Скрипт | ✅ |
| 28 | calc_irp.py | Скрипт | ✅ |
| 29 | notion_sync.py | Скрипт | ✅ |
| 30 | returns_analysis.py | Скрипт | ✅ |
| 31 | sync_sheets_to_supabase.py | Скрипт | ✅ |
| 32 | run_report.py | Скрипт | Legacy |
