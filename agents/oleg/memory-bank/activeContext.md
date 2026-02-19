# Олег — Активный контекст

## Текущее состояние
**Дата:** 2026-02-18  
**Статус:** Production (92%) - Global MSK Compliance + Data Freshness Hardening  
**Развёртывание:** Docker на сервере, production Telegram

## Что работает
✅ Очередь доставки (`delivery_queue`): разделение генерации и отправки  
✅ Автономный планировщик (не зависит от Telegram API)  
✅ Автоматическое восстановление пропущенных отчётов (3-day lookback)  
✅ Ежедневные/недельные/месячные автоматические отчёты  
✅ Произвольные аналитические запросы через Telegram  
✅ Финансовая аналитика (12 tools)  
✅ Ценовая аналитика (Advanced Elasticity: контроль рекламы, гибридные источники заказов)  
✅ Маркетинговая воронка (CPO, CTR, CR)  
✅ Мониторинг свежести данных: кросс-чек источников + 50% revenue gate + logistics check (logist/logist_end > 0)  
✅ Глобальный Moscow Timezone: синхронизация времени во всех аналитических модулях  
✅ Smart date adjustment (корректировка периодов)  
✅ Синхронизация отчётов с Notion  
✅ Верификация данных vs OneScreen/PowerBI  

## Что НЕ работает
❌ **Feedback handler не подключён** — Олег НЕ учится на ошибках автоматически  
❌ **Tool crash убивает ReAct loop** — нет graceful degradation  
❌ **Нет checkpoint'ов** — crash в середине анализа = потеря прогресса  
❌ **Контекст не сжимается** — длинные диалоги переполняют context window  
❌ **FSM в MemoryStorage** — сессии теряются при перезапуске  
❌ **Нет rate limiting** — один пользователь может спамить дорогие запросы  

## Текущие задачи
Нет активных задач. Система в стабильном состоянии.

## Планируемые улучшения (Roadmap)

### Версия 1.1 (Q1 2026)
- [ ] Подключить feedback handler — /feedback команда + inline кнопки ✅/❌
- [ ] Try-catch в tool calls — graceful degradation при ошибках БД
- [ ] Checkpoints в ReAct loop — сохранять прогресс, resume при crash
- [ ] Context compression — summarize старые сообщения при превышении 80% context window

### Версия 1.2 (Q2 2026)
- [ ] Multi-turn диалоги — память о предыдущих запросах в сессии
- [ ] Проактивные алерты — уведомления при падении маржи > 15%
- [ ] Voice input — анализ голосовых сообщений Telegram
- [ ] A/B тестирование prompts — эксперименты с формулировками system prompt

### Версия 2.0 (Q3 2026)
- [ ] Автоматические рекомендации — не только анализ, но и готовые action items
- [ ] Интеграция с Excel — экспорт отчётов в .xlsx
- [ ] Web dashboard — визуализация трендов (альтернатива Telegram)
- [ ] Multi-user permissions — разные уровни доступа (viewer, analyst, admin)

## Известные проблемы

### Критические (🔴 High)
1. **Feedback handler не подключён**  
   - Влияние: Олег НЕ учится на ошибках, playbook не обновляется автоматически  
   - Решение: Создать `handlers/feedback.py`, добавить команды `/feedback`, inline кнопки ✅/❌  

2. **Tool crash убивает ReAct loop**  
   - Влияние: При ошибке в одном tool весь анализ падает  
   - Решение: Обернуть tool calls в try-except, возвращать `{"error": "..."}` вместо raise  

### Средние (🟡 Medium)
3. **Нет checkpoint'ов в ReAct loop**  
   - Влияние: Crash в середине анализа = потеря всего прогресса (10 tool calls могут пропасть)  
   - Решение: Сохранять intermediate results в SQLite после каждого tool call  

4. **Контекст не сжимается**  
   - Влияние: Длинные диалоги переполняют context window  
   - Решение: Summarization старых сообщений при превышении 80% лимита  

5. **Нет rate limiting**  
   - Влияние: Один пользователь может спамить дорогие ReAct запросы  
   - Решение: Лимит 10 запросов/час на пользователя  

### Низкие (🟢 Low)
6. **FSM в MemoryStorage**  
   - Влияние: Сессии пользователей теряются при перезапуске бота  
   - Решение: Переключиться на Redis/SQLite storage  

7. **Отчёты WB/OZON расходятся на ~7%**  
   - Влияние: Известное расхождение OZON выручки с OneScreen  
   - Статус: Задокументировано в `DATA_QUALITY_NOTES.md`  

## Последние изменения

### 2026-02-19 (Terminology & Goals Update)
- **Переход на «Маржинальность»**: Во всём проекте (playbook, projectbrief, сообщения бота) термин «Маржа %» заменён на «Маржинальность %» для соответствия финансовым стандартам компании.
- **Актуализация целей**: Цели обновлены на **февраль 2026**:
    - Минимум: 5 млн ₽ маржи, 20% маржинальность.
    - Средний: 6.5 млн ₽, 23%.
    - Высокий: 8 млн ₽, 25%.
- **Корреляция и Реклама**: В плейбуке уточнены разделы по анализу рекламы (раздел 10) и управлению СПП.

### 2026-02-18 (Moscow Timezone Compliance + Data Freshness Hardening)
- **Глобальная синхронизация (MSK)**: 
    - Создан `time_utils.py` с функцией `get_now_msk()`.
    - Рефакторинг всех модулей (`agent_runner`, `scheduled_reports`, `query_understanding`, `price_tools`, `learning_store`, `promotion_analyzer`, `hypothesis_tester`): удалены прямые вызовы `datetime.now()` и `date.today()`.
    - Все отчеты и аналитика теперь жестко привязаны к "Europe/Moscow", что гарантирует консистентность "вчера" и "сегодня" между сервером, БД и Telegram-ботом.
- **Hardening `DataFreshnessService`**:
    - **Source Cross-Check**: Новая проверка: `sum(count_orders)` в `abc_date` должна совпадать с реальным количеством строк в `orders` (допуск 5%). Защита от неполного ETL.
    - **Financial Quality Gates**: 
        - Выручка (revenue): порог снижен до 50% от 7-дневного среднего (адаптация под реальные просадки).
        - Логистика (logistics): введена обязательная проверка `SUM > 0` отдельно для WB (`logist`) и Ozon (`logist_end`).
- **UI/UX**: В Telegram-хендлерах исправлена логика определения вчерашнего дня, учитывающая смещение часовых поясов.

### 2026-02-18 (Model Selector + Rolling Backtest)
- **`estimate_price_elasticity` → оркестратор**:
    - Функция переписана: теперь вызывает `_select_best_model` (Linear vs Quadratic).
    - Backward-compatible: все старые ключи (`elasticity`, `r_squared`, `p_value`, `confidence_interval_95`) сохранены в корне ответа.
    - Новые ключи: `selected_model`, `selection_status`, `reason_code`, `backtest_results`.
- **Rolling Walk-Forward Backtesting** (`_backtest_single_model`):
    - 3 скользящих окна, метрики: WAPE и MAE на out-of-sample.
    - Сравнение с Naive (t-1) и MA-7 baseline: модель должна превосходить на ≥10% WAPE.
    - Overfit detection: `test_wape / train_wape > 1.5` → отбраковка.
    - Score = `median_test_wape + λ * (n_params / n_obs)` (complexity penalty).
- **Strict Pipeline** (`_select_best_model`): Sufficiency → Validity → Quality → Score.
    - Tie-breaking: Linear предпочитается если `score_quad - score_linear < 0.01`.
    - `reason_code`: `insufficient_data` / `low_price_variation` / `positive_elasticity` / `low_predictive_power`.
- **`recommendation_engine.py`**: Quality Gates делегированы к `selection_status` из оркестратора. Legacy-fallback сохранён.
- **Жёсткое требование `orders_count`**:
    - `sales_count` (выкупы) **полностью исключён** из расчёта эластичности.
    - Если `orders_count` отсутствует в данных → `error: missing_orders_count`.

### 2026-02-18 (Advanced Price Analysis — ранее)
- **Гибридный источник**: Заказы из `orders` (первоисточник API), расходы/реклама из `abc_date`.
- **Мультифакторная эластичность**: `ln(orders) ~ ln(price) + ln(adv_internal) + ln(adv_external)`.
- **HAC ковариация**: `cov_type='HAC'` с динамическим `maxlags` для устойчивости к автокорреляции.
- **Блокирующая логика (Strict Priority)**: INSUFFICIENT_DATA → FAIL → CONFOUNDED → PASS.

### 2026-02-17
- **Архитектурный сплит**: Проект разделен на `agent_runner.py` (Producer) и `main.py` (Consumer).
- **Delivery Queue**: Добавлена таблица в SQLite для межпроцессного взаимодействия. Бот теперь просто "доставщик".
- **Надёжность**: Агент теперь умеет восстанавливать пропущенные отчёты за последние 3 дня при перезапуске.
- **Инфраструктура**: Обновлены Docker-конфиги, добавлены PID-блокировки для предотвращения запуска двух агентов одновременно.
- **Бизнес-логика**: Все правила аналитики интегрированы в `playbook.md` и код агента. Внедрены принципы «скрытого контекста» (без ссылок на плейбук в отчетах) и многофакторного анализа.

### 2026-02-16
- Smart date adjustment: все отчёты автоматически корректируют период по доступности данных
- `analyze_deep()` используется ВЕЗДЕ (ручные + автоматические отчёты)
- OpenRouter (kimi-k2.5) стал primary LLM провайдером
- `data_freshness` добавлен в DI middleware
- Paragraph-based HTML chunking для Telegram
- `data_availability_note` — LLM знает про недостающие даты

### 2026-02-12
- Trade-off анализ: снижение рекламы → рост маржи/ед, НО падение трафика
- Драйверы/анти-драйверы маржи — обязательная секция в отчётах
- Средняя цена/ед — обязательная метрика
- Проверка трафика при изменении рекламы

### 2026-02-11
- Исправлена формула маржи WB: `marga - nds - reclama_vn`
- Верификация vs OneScreen (расхождение < 1%)
- Два формата вывода: краткая сводка + подробный отчёт

## Метрики использования

### Январь 2026 (тестовая среда)
- Uptime: 98.5%
- Error rate: 1.5%
- Success rate (tool calls): 99.2%
- Средняя стоимость запроса: $0.05
- Среднее время выполнения: 45 сек

### Основные причины ошибок
- PostgreSQL timeouts: 0.8%
- LLM API timeouts: 0.5%
- Invalid user input: 0.2%

## Ближайшие действия
Нет запланированных действий. Система в стабильном состоянии, работает в production.
