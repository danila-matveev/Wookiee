# Smart Conductor — Report Controller Agent

**Дата:** 2026-03-21
**Спек:** A (Notification cleanup + Controller agent + Fix generation)
**Статус:** Review

---

## 1. Проблема

Текущая система v3 имеет 4 критических проблемы:

1. **Спам уведомлений** — watchdog heartbeat каждые 6ч, data_ready_check каждый час, anomaly monitor, ETL-статусы — всё шлётся отдельными сообщениями в Telegram
2. **Пустые отчёты** — отчёты за 17-18 марта попали в Notion как "Не удалось сформировать ответ" без ошибок и диагностики
3. **Молчаливые failures** — отчёт за 19 марта не был сформирован автоматически, никаких ошибок не записано
4. **Отсутствие контроля качества** — сгенерированный отчёт отправляется без проверки содержимого

## 2. Решение: Smart Conductor

Новый LangGraph микро-агент `report-conductor`, который стоит между cron-триггерами и оркестратором. Вызывается на лёгкой модели (GLM-4.7-flash, ~$0.001/вызов) только при необходимости принять решение.

### 2.1 Принципы

- **Data-first**: отчёт запускается только после подтверждения готовности данных обоих каналов (WB + OZON)
- **Минимум шума**: в Telegram только полезные сообщения (данные готовы, отчёт готов, алерт)
- **LLM для решений, скрипты для рутины**: gates check — скрипт; валидация отчёта — LLM
- **Защита от циклов**: max 3 попытки на отчёт, дедлайн 12:00, state tracking

### 2.2 Архитектура

```
06:00-12:00  Cron hourly → data_ready_check (скрипт, без LLM)
               │
               ├─ WB gates pass? + OZON gates pass?
               │           │              │
               │          ДА (оба)       НЕТ → молчим, ждём
               │           │
               │           ▼
               │   check_report_schedule() — детерминированная логика
               │   (день недели, число месяца, что уже сделано)
               │           │
               │           ▼
               │   Telegram: "✅ Данные готовы. Запускаю: [список]"
               │           │
               │           ▼
               │   Последовательная генерация отчётов
               │           │
               │           ▼
               │   Conductor LLM: validate(result, previous_report)
               │           │
               │      ┌────┴────┐
               │     OK       FAIL
               │      │         │
               │      ▼         ▼
               │   Deliver   Retry (до 2 раз через DateTrigger, 1→5 мин)
               │   Notion +    → если fail → алерт с причиной
               │   Telegram
               │
12:00  deadline_check:
               │
               ▼
         Если отчёты не запущены → Conductor LLM: диагностика
         → Telegram: 1 алерт с причиной и рекомендацией
```

### 2.3 Компонент: `agents/v3/conductor/`

**Файлы:**
- `conductor.py` — основная логика (schedule, validate, diagnose)
- `schedule.py` — детерминированное расписание отчётов
- `validator.py` — LLM-валидация результата отчёта
- `state.py` — работа с conductor_log в StateStore

**Промпт агента:** `agents/v3/agents/report-conductor.md`

### 2.4 Tools Conductor

| Tool | Назначение | LLM? |
|------|-----------|------|
| `check_report_schedule` | Какие отчёты нужны сегодня + какие уже сделаны | Нет |
| `validate_report` | Проверка: секции не пустые, цифры адекватные, сравнение с предыдущим отчётом | Да (light) |
| `get_failure_context` | Диагностика: статус gates, последний ETL, ошибки в логах | Нет (данные), Да (анализ) |

**Conductor НЕ делает:**
- Не запускает отчёты сам (это делает scheduler)
- Не доставляет отчёты в Notion/Telegram (это делает delivery router)
- Не анализирует бизнес-данные (это делает orchestrator)

**Conductor ОТПРАВЛЯЕТ в Telegram напрямую** (операционные уведомления):
- "Данные готовы, запускаю отчёты" — перед генерацией
- Алерты при ошибках — после исчерпания retry

**Conductor решает:**
- Какие отчёты запустить → возвращает `list[ReportType]`
- Отчёт прошёл валидацию? → `pass` / `retry` / `fail`
- При ошибке: → `wait` / `retry` / `escalate` + текст алерта
- Edge case (один канал готов, другой нет): → `wait` / `partial` + пометка

## 3. Расписание отчётов

### 3.1 Детерминированная логика

```python
def get_today_reports(date) -> list[ReportType]:
    reports = [DAILY]  # всегда

    if date.weekday() == 0:  # понедельник
        reports += [WEEKLY, MARKETING_WEEKLY, FUNNEL_WEEKLY, PRICE_WEEKLY]

    if date.weekday() == 4:  # пятница
        reports += [FINOLOG_WEEKLY]

    if date.day <= 7 and date.weekday() == 0:  # первый понедельник месяца
        reports += [MONTHLY, MARKETING_MONTHLY, PRICE_MONTHLY]

    return reports
```

### 3.2 Полный список типов отчётов

| Тип | Периодичность | Когда | Примечание |
|-----|--------------|-------|-----------|
| `DAILY` | Ежедневно | Каждый день | Фин + краткий маркетинг |
| `WEEKLY` | Еженедельно | Понедельник | Фин с глубоким анализом |
| `MONTHLY` | Ежемесячно | Первый понедельник месяца | Фин с YoY, стратегия |
| `MARKETING_WEEKLY` | Еженедельно | Понедельник | Маркетинг + ROMI |
| `MARKETING_MONTHLY` | Ежемесячно | Первый понедельник месяца | Маркетинг глубокий |
| `FUNNEL_WEEKLY` | Еженедельно | Понедельник | Воронка WB по моделям |
| `PRICE_WEEKLY` | Еженедельно | Понедельник | **NEW** — ценовая динамика, СПП, прогноз |
| `PRICE_MONTHLY` | Ежемесячно | Первый понедельник месяца | Ценовые паттерны, эластичность |
| `FINOLOG_WEEKLY` | Еженедельно | Пятница | ДДС (cash flow) |

> **Примечание:** `PRICE_WEEKLY` — новый тип. В текущем коде есть только `monthly_price_analysis`.
> Нужно создать промпт `agents/v3/agents/price-weekly.md` и добавить метод в оркестратор.
> Содержание: динамика СПП, средние цены заказов vs продаж, прогноз выручки на 3-7 дней.

### 3.3 Единый шаблон по глубине

Daily / Weekly / Monthly отличаются **только глубиной**, не структурой:
- **Daily**: текущие цифры, сравнение с вчера, краткие гипотезы
- **Weekly**: + тренды за неделю, системные паттерны, top/bottom unit economics
- **Monthly**: + YoY сравнение, стратегические выводы, лучшая/худшая неделя

## 4. Изменения в Scheduler (v3)

### 4.1 Текущие 15 cron-джобов → 4 триггера

| Триггер | Расписание | Что делает |
|---------|-----------|-----------|
| `data_ready_check` | Hourly 06:00-12:00 MSK, :00 мин | Gates check → conductor → генерация → валидация → deliver |
| `deadline_check` | 12:00 MSK | Если ничего не запущено → conductor диагностика → алерт |
| `catchup_check` | 15:00 MSK | Если daily не сгенерирован → повторная проверка gates + генерация |
| `anomaly_monitor` | Каждые `ANOMALY_MONITOR_INTERVAL_HOURS` (default 4ч) в :30 | Дедуплицированный (1 алерт / метрику / 24ч) |
| `notion_feedback` | 08:00 MSK | PromptTuner — без изменений |

### 4.2 Что убирается

- `daily_report`, `weekly_report`, `monthly_report` — заменены `data_ready_check` + conductor
- `weekly_marketing_bundle`, `marketing_monthly` — заменены conductor schedule
- `monthly_price_analysis`, `finolog_weekly` — заменены conductor schedule
- `watchdog_heartbeat` — только лог, не Telegram
- `etl_daily_sync`, `etl_weekly_analysis` — остаются, уведомления только при ошибках
- `promotion_scan` — остаётся как есть

### 4.3 Логика `data_ready_check`

```python
async def data_ready_check():
    # 1. Проверяем gates (скрипт, без LLM)
    wb_gates = await check_gates("wb")
    ozon_gates = await check_gates("ozon")

    # 2. Оба канала готовы?
    if not (wb_gates.can_generate and ozon_gates.can_generate):
        return  # молчим, ждём следующего часа

    # 3. Какие отчёты нужны сегодня?
    today = date.today()
    schedule = get_today_reports(today)

    # 4. Фильтруем уже сделанные
    done = await conductor_state.get_successful(today)
    pending = [r for r in schedule if r not in done]
    if not pending:
        return  # всё уже сделано

    # 5. Telegram: данные готовы
    await telegram.send(format_data_ready(wb_gates, ozon_gates, pending))

    # 6. Генерация + валидация
    for report_type in pending:
        await generate_and_validate(report_type, today)
```

```python
async def generate_and_validate(report_type, date, attempt=1):
    MAX_ATTEMPTS = 3

    # Записываем старт
    await conductor_state.log(date, report_type, status="running", attempt=attempt)

    # Генерация через orchestrator
    result = await orchestrator.run(report_type, date)

    # Валидация через conductor LLM
    previous = await get_previous_report(report_type)
    validation = await conductor.validate(result, previous)

    if validation.verdict == "pass":
        # Deliver: Notion → Telegram
        notion_url = await delivery.to_notion(result)
        await delivery.to_telegram(result.telegram_summary, notion_url)
        await conductor_state.log(date, report_type, status="success",
                                   notion_url=notion_url)
    elif validation.verdict == "retry" and attempt < MAX_ATTEMPTS:
        # Retry через отложенный APScheduler DateTrigger (не блокирует event loop)
        pause = timedelta(minutes=1 if attempt == 1 else 5)
        scheduler.add_job(
            generate_and_validate,
            trigger=DateTrigger(run_date=datetime.now(MSK) + pause),
            args=[report_type, date, attempt + 1],
            id=f"retry_{report_type}_{date}_{attempt+1}",
            replace_existing=True,
        )
        await conductor_state.log(date, report_type, status="retrying",
                                   attempt=attempt, error=validation.reason)
    else:
        # Все попытки исчерпаны или verdict == "fail" → алерт
        await telegram.send(format_alert(report_type, validation.reason, attempt))
        await conductor_state.log(date, report_type, status="failed",
                                   error=validation.reason)
```

> **Важно:** retry реализован через `DateTrigger`, а не `asyncio.sleep`,
> чтобы не блокировать event loop и не задерживать генерацию остальных отчётов.

## 5. Telegram — форматы сообщений

### 5.1 Данные готовы (1 раз в день)

```
✅ Данные за 20 марта готовы

WB: обновлено в 06:41 МСК | Заказы: 1350 | Выручка: 104% от нормы
OZON: обновлено в 07:06 МСК | Заказы: 152 | Выручка: 68% от нормы ⚠️

📊 Запускаю отчёты: Daily фин, Weekly маркетинг
```

### 5.2 Отчёт готов (по одному на каждый тип)

```
📊 Ежедневный фин анализ за 20 марта 2026

📈 План-Факт (Март): Выручка +20.2% (прогноз), Маржа +7.2%. Статус: ✅

💰 Финансы:
• Выручка: 1.37М ₽ (+1.2%)
• Маржа: 332К ₽ (+28.9%)
• DRR: 2.6% (-4.4 п.п.)

🏪 Каналы:
• WB: 1.23М ₽ +8.9% (Маржа +46%)
• OZON: 142К ₽ -37.3% (Маржа -51%)

🔥 Драйверы: Charlotte, Joy, Vuki (WB)
🔻 Антидрайверы: Wendy, Audrey (OZON)

💡 Что делать:
1. [P0] OZON Wendy/Audrey — проверить наличие и цены
2. [P1] WB Charlotte — масштабировать (оборач. 0.8 дня — риск OOS)

📎 Полный отчёт в Notion
```

### 5.3 Алерт при проблемах

```
⚠️ Проблема с формированием отчётов

Статус: Daily фин — ❌ не сформирован (3/3 попытки)
Причина: LLM timeout (OpenRouter 504, модель z-ai/glm-4.7)
Диагностика: данные в БД корректны, gates OK

Действие: жду восстановления API, повторю при следующей проверке
```

### 5.4 Правила уведомлений

- В обычный день: 2 сообщения (данные готовы + отчёт)
- В понедельник: 1 + N отчётов (до 5-6)
- Первый понедельник месяца: 1 + N (до 8-9)
- Anomaly alert: отдельный, не чаще 1 раз/24ч на метрику
- Watchdog, ETL, промежуточные проверки — **только в логи, не в Telegram**

## 6. StateStore: conductor_log

**Таблица `conductor_log` в v3_state.db:**

| Поле | Тип | Назначение |
|------|-----|-----------|
| `date` | TEXT | Дата отчёта (2026-03-20) |
| `report_type` | TEXT | daily / weekly / monthly / marketing_weekly / ... |
| `status` | TEXT | scheduled / running / success / failed / retrying |
| `attempts` | INT | Счётчик попыток (0 → 1 → 2 → 3 max) |
| `data_ready_at` | TEXT | Когда gates прошли (ISO timestamp) |
| `started_at` | TEXT | Когда запущена генерация |
| `finished_at` | TEXT | Когда завершена |
| `validation_result` | TEXT | pass / retry / fail + причина |
| `notion_url` | TEXT | Ссылка на созданную страницу |
| `error` | TEXT | Текст ошибки (если есть) |

**Дедупликация anomaly alerts:**
- Ключ в таблице `state`: `anomaly_alert:{channel}:{metric}:{date}`
- Значение: timestamp последнего алерта
- Проверка: если < 24ч → молчим

## 7. Валидация отчёта (Conductor LLM)

### 7.1 Что проверяет validate_report

1. **Полнота секций**: все обязательные секции присутствуют и не пустые
2. **Telegram summary**: существует, длина 200-2000 символов
3. **Адекватность цифр**: сравнение с предыдущим отчётом — отклонение > 10x → подозрительно
4. **Формат**: toggle-заголовки, таблицы, интерпретации после таблиц

### 7.2 Результат валидации

```python
class ValidationVerdict(str, Enum):
    PASS = "pass"     # Отчёт OK → deliver
    RETRY = "retry"   # Отчёт плохой, стоит повторить генерацию
    FAIL = "fail"     # Критическая проблема, retry не поможет → алерт

@dataclass
class ValidationResult:
    verdict: ValidationVerdict
    reason: str        # Причина (для логов/алерта)
    details: dict      # Детали (пустые секции, аномальные цифры)
```

## 8. Защита от бесконечных циклов

| Механизм | Значение |
|----------|---------|
| Max attempts на отчёт | 3 (с паузой 1 мин → 5 мин) |
| Max LLM-вызовов conductor на цикл | 3 (schedule + validate + error) |
| Дедлайн | 12:00 MSK — после него только алерт, без retry |
| State tracking | conductor_log: не повторяет `status=success` |
| Дедупликация уведомлений | 1 "данные готовы" в день, 1 алерт на метрику в 24ч |

## 9. Edge Cases

| Ситуация | Решение |
|----------|--------|
| WB готов, OZON нет | Ждём оба до дедлайна 12:00. Если к 12:00 один не пришёл → conductor решает: partial + пометка или алерт |
| Данные пришли после 12:00 | `catchup_check` в 15:00 MSK проверит gates повторно. Если данные появились → генерирует только `DAILY` (остальные ждут завтра). Если нет → принятая потеря дня |
| Orchestrator вернул пустой отчёт | validate → retry (до 3 раз) → fail → алерт |
| Один отчёт из пачки упал | Остальные доставляются. Упавший — retry/алерт отдельно |
| Повторный деплой в середине дня | conductor_log проверяет что уже сделано — не дублирует |
| Weekend (суббота/воскресенье) | Отчёты генерируются как обычно (daily). Anomaly thresholds x1.5 |

## 10. Cost Estimation

| Компонент | Вызовов/день | Модель | Cost/день |
|-----------|-------------|--------|-----------|
| validate_report | 1-8 (по числу отчётов) | GLM-4.7-flash | ~$0.005 |
| failure diagnosis | 0-2 (только при ошибках) | GLM-4.7-flash | ~$0.002 |
| Итого conductor | | | ~$0.005-0.01 |

Worst case (понедельник, все 6 отчётов fail 3x): ~$0.03-0.05/день. Всё ещё дёшево.

Основной cost остаётся в orchestrator (генерация отчётов).

## 11. StateStore: миграция

Таблица `conductor_log` создаётся как новая таблица в `v3_state.db` рядом с существующей `kv_store`.

**Реализация:** новый класс `ConductorState` в `agents/v3/conductor/state.py` (не расширение `StateStore`):
- `ConductorState.log()` — записать/обновить статус
- `ConductorState.get_successful(date)` — список успешных отчётов за дату
- `ConductorState.get_attempts(date, report_type)` — текущее число попыток
- `ConductorState.ensure_table()` — CREATE TABLE IF NOT EXISTS (вызывается при старте)

## 12. Rollback Plan

Старый scheduler (`_setup_scheduler` с 15 cron-джобами) сохраняется в коде за feature flag:

```python
USE_CONDUCTOR = config.get("USE_CONDUCTOR", True)

if USE_CONDUCTOR:
    setup_conductor_scheduler()  # новые 5 триггеров
else:
    setup_legacy_scheduler()     # старые 15 cron-джобов
```

Если conductor имеет системный баг → деплой с `USE_CONDUCTOR=false` восстанавливает старое поведение.

---

**Спек B** (переформатирование шаблонов отчётов в новый стиль) — отдельный документ.
