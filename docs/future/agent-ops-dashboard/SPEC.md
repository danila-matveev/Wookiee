# Wookiee Hub — Agent Operations Dashboard

> Единый документ: UI/UX Spec + Implementation Plan.
> Дата: 2026-04-01. Источники: UI/UX Spec (Notion), multi-agent review (6 агентов).

---

# Часть 1: UI/UX Spec

## Context

Wookiee имеет развитую мульти-агентную систему (Oleg v2: Reporter, Marketer, Funnel, Researcher, Advisor, Validator) с оркестратором, pipeline delivery, circuit breaker, anomaly detection и watchdog. Но **нет UI для наблюдения за агентами** — текущая страница `/system/agents` это заглушка (`ModuleStub`). Вся телеметрия уходит в SQLite (`state_store`) и Telegram, без визуализации.

Цель: спроектировать Agent Operations Dashboard внутри существующего Wookiee Hub (React + TypeScript + Tailwind + shadcn/ui + Zustand), который даст полный обзор работы агентской системы.

Вдохновление: AxionAI Fleet Operations dashboard — но адаптировано под реальную архитектуру Wookiee.

---

## Архитектура раздела

Заменяем заглушку `/system/agents` на полноценный раздел с вложенными маршрутами (по аналогии с `/system/matrix-admin`):

```
/system/agents              → Overview (главный дашборд)
/system/agents/fleet        → Agent Fleet (список агентов с детализацией)
/system/agents/pipelines    → Pipeline History (отчёты, gate checks)
/system/agents/logs         → Activity Log (все действия системы)
/system/agents/costs        → Cost Tracker (расходы по агентам/моделям)
/system/agents/health       → System Health (диагностика, circuit breakers)
```

> **MVP**: только `/system/agents` (Overview). Остальные sub-pages — Phase 2+.

---

## Страница 1: Overview (`/system/agents`)

Главный экран — snapshot состояния всей агентской системы за последние 24 часа.

### 1.1 Summary Cards (верхняя полоса, 4 карточки)

| Карточка | Данные | Источник | Тренд |
|----------|--------|----------|-------|
| **Активных агентов** | Кол-во агентов со статусом != OPEN (circuit breaker) | `CircuitBreaker.status()` по каждому агенту | — |
| **Отчётов сегодня** | Успешно доставленных отчётов | `report_log` WHERE status='success' AND date=today | vs вчера |
| **Success Rate** | % успешных pipeline runs за 7д | `report_log` success / total | vs предыдущие 7д |
| **Расход за сутки** | Сумма cost_usd за 24ч | `report_log.cost_usd` + `recommendation_log.advisor_cost_usd + validator_cost_usd` | vs вчера |

Дизайн: иконка слева, число крупно, тренд (▲/▼ с процентом) справа. Цвета: `--wk-green` для позитива, `--wk-red` для негатива. Sparkline 7 дней под числом.

### 1.2 Agent Fleet Status (левая колонка, ~60% ширины)

Компактная таблица всех агентов системы:

| Agent | Role | Status | Last Run | Runs (24h) | Errors (24h) | Avg Duration |
|-------|------|--------|----------|------------|--------------|-------------|
| 🔵 Reporter | Аналитик | `Running` | 5m ago | 8 | 0 | 45s |
| 🟢 Marketer | Маркетинг | `Idle` | 2h ago | 3 | 1 | 32s |
| 🟢 Funnel (Макар) | Воронка | `Idle` | 1d ago | 1 | 0 | 28s |
| 🟡 Researcher | Исследователь | `Idle` | 6h ago | 2 | 0 | 67s |
| 🟢 Advisor | Рекомендации | `Idle` | 3h ago | 4 | 0 | 15s |
| 🔴 Validator | Качество | `CB Open` | 1d ago | 0 | 3 | — |

Статусы с badge-компонентом:
- `Running` — синий, анимация пульса
- `Idle` — серый/зелёный
- `CB Open` — красный (circuit breaker сработал)
- `CB Half-Open` — жёлтый (пробует восстановиться)
- `Cooldown` — оранжевый

Клик по строке → Phase 2: Sheet panel справа (480px) с детальной информацией.

### 1.3 Live Activity Feed (правая колонка, ~40% ширины)

Лента последних событий с polling каждые 30 секунд:

| Время | Событие |
|-------|---------|
| 09:15 | ✅ **Reporter** → Daily Report (WB) → Notion опубликован · 2m14s · $0.08 |
| 09:12 | ✅ **Gate Check** → WB Hard Gates → 3/3 passed |
| 09:10 | ⚠️ **Anomaly** → Revenue WB → -22% vs avg · critical |
| 08:45 | ✅ **Advisor** → Recommendations → 3 рекомендации · 8s · $0.02 |
| 08:30 | ❌ **Marketer** → Marketing Daily → Empty response (retry 1) · 120s · $0.04 |
| 08:32 | 🔄 **Marketer** → Marketing Daily → Retry successful · 45s · $0.03 |
| 06:00 | ✅ **Watchdog** → Heartbeat → All healthy |
| 23:00 | 🛑 **Circuit Breaker** → Validator → 3 consecutive failures |

Типы событий (иконки/цвета):
- ✅ Success — `--wk-green`
- ❌ Error — `--wk-red`
- ⚠️ Warning/Anomaly — `--wk-yellow`
- 🔄 Retry — `--wk-blue`
- 🛑 Circuit Breaker — `--wk-red`
- 📊 Gate Check — `--accent`

### 1.4 Pipeline Timeline (нижняя секция)

Горизонтальный timeline за последние 7 дней:

```
Пн 24  [daily ✓] [weekly ✓] [mkt_daily ✓] [mkt_weekly ✓]        4✓
Вт 25  [daily ✓] [mkt_daily ✓] [funnel ✕]                       2✓ 1✕
Ср 26  [daily ✓] [mkt_daily ✓]                                   2✓
Чт 27  [daily ✓] [mkt_daily ⚠] [ozon −]                         1✓ 1⚠ 1−
Пт 28  [daily ✓] [mkt_daily ✓] [advisor ✓]                      3✓
Сб 29  [daily ✓] [mkt_daily −]                                   1✓ 1−
Вс 30  [daily ✓] [mkt_daily ✕] [advisor ✓]                      2✓ 1✕
```

Цвета: зелёный = success, красный = failed, жёлтый = degraded, серый = skipped.

### 1.5 Circuit Breakers (нижняя левая)

6 карточек — по одной на агента:
- Имя + badge (CLOSED/OPEN/HALF_OPEN)
- Progress bar: failures 0/3, 1/3, 2/3, 3/3
- При OPEN: cooldown timer + **кнопка Reset**

### 1.6 Cost Breakdown (нижняя правая)

Горизонтальные бары расходов по агентам за 24ч с процентами. Total в заголовке.

### 1.7 Alert Banner + Live Indicator

- **Alert Banner**: sticky над контентом при CB Open / critical anomaly. Dismissible.
- **Live Indicator**: пульсирующая точка в header + время. Жёлтый при staleness >2min, красный при offline.

---

## Страница 2: Agent Fleet (`/system/agents/fleet`) — Phase 2

Детальные карточки каждого агента.

### Agent Card — Tabs:

**Tab: Конфигурация**
- System Prompt (read-only, code block)
- Модель (тир), Temperature, Max iterations, Timeout
- Tools: список с группировкой (Financial, Price, Marketing, Funnel)

**Tab: История запусков**

| Дата/Время | Task Type | Статус | Chain Steps | Duration | Cost | Notion URL |
|------------|-----------|--------|-------------|----------|------|------------|
| 31.03 09:15 | daily_report | ✅ | 2 | 2m 14s | $0.08 | 🔗 |
| 31.03 08:30 | marketing_daily | ❌→✅ | 3 (retry) | 2m 45s | $0.07 | 🔗 |

Expandable row → Chain visualization:
```
Step 1: Reporter (45s, $0.04) → "Собери данные по WB за 30.03"
  └─ 8 tool calls: get_daily_summary, get_margin_data, ...
Step 2: Researcher (67s, $0.03) → "Проанализируй аномалию маржи -12%"
  └─ 4 tool calls
Step 3: Synthesize → Markdown report (2s, $0.01)
```

**Tab: Error Log**

| Время | Тип | Сообщение | Контекст |
|-------|-----|-----------|----------|
| 08:30 | LLM Empty | Empty response from MAIN tier | marketing_daily, retry triggered |
| 07:15 | Timeout | Tool execution exceeded 30s | get_weekly_comparison |
| Вчера 23:00 | CB Open | 3 consecutive failures | Validator |

**Tab: Архитектура** — мини-схема flow данных для агента (SVG).

---

## Страница 3: Pipeline History (`/system/agents/pipelines`) — Phase 2

Expandable cards для каждого pipeline run:

```
┌─────────────────────────────────────────────────────────┐
│ 📊 Daily Report (WB) — 31.03.2026, 09:15               │
│ Status: ✅ Delivered  |  Duration: 2m 14s  |  $0.08     │
│ ▸ Gate Check (3/3 hard ✅, 3/3 soft ✅)                  │
│ ▸ Pre-flight Telegram ✅                                 │
│ ▸ LLM Chain (2 steps, 0 retries)                        │
│ ▸ Section Validation ✅ (6/6 sections)                   │
│ ▸ Substantiality ✅ (1,847 chars, 8 headings)            │
│ ▸ Notion Publish ✅ → [link]                             │
│ ▸ Telegram Notification ✅                               │
└─────────────────────────────────────────────────────────┘
```

Фильтры: по типу отчёта, статусу, дате, lead-агенту.

Gate History подтаблица: timeline прохождения gates за период.

---

## Страница 4: Activity Log (`/system/agents/logs`) — Phase 2

Единый лог всех событий с фильтрами:
- По источнику: Pipeline, Gates, Anomaly, Advisor, Watchdog, Circuit Breaker
- По severity: Info, Warning, Error, Critical
- По агенту
- По дате
- Full-text search

---

## Страница 5: Cost Tracker (`/system/agents/costs`) — Phase 3

- Summary: сегодня / неделя / месяц (прогноз)
- Cost Breakdown по агентам (bar chart)
- Cost by Model Tier (LIGHT/MAIN/HEAVY/FREE): вызовы, tokens, стоимость
- Daily Cost Timeline: stacked area chart 30 дней
- Cost per Report Type: avg cost, chain steps, duration, runs/week

---

## Страница 6: System Health (`/system/agents/health`) — Phase 2

- Health Status Cards: PostgreSQL, LLM API, Data Gates WB/OZON, ETL, Notion, Telegram
- Circuit Breaker Panel (визуальное состояние + reset)
- Watchdog History (heartbeats, failure alerts)
- Anomaly History: метрика, канал, отклонение, severity

---

## Компонентная структура

```
src/pages/system/
  agents-overview.tsx              → Overview dashboard (MVP)
  agents-layout.tsx                → Layout с sub-navigation tabs (Phase 2)
  agents-fleet.tsx                 → Fleet + detail panel (Phase 2)
  agents-pipelines.tsx             → Pipeline history (Phase 2)
  agents-logs.tsx                  → Activity log (Phase 2)
  agents-costs.tsx                 → Cost tracker (Phase 3)
  agents-health.tsx                → System health (Phase 2)

src/components/agents/
  agent-metric-card.tsx            → KPI карточка с sparkline
  agent-fleet-table.tsx            → Fleet таблица с статусами
  activity-feed.tsx                → Live event feed
  pipeline-timeline.tsx            → 7-дневный grid
  circuit-breaker-grid.tsx         → CB panel с reset кнопкой
  cost-breakdown.tsx               → Cost bars
  live-indicator.tsx               → Polling status
  alert-banner.tsx                 → Critical alerts
  agent-detail-sheet.tsx           → Sheet panel при клике (Phase 2)
  pipeline-run-card.tsx            → Expandable pipeline card (Phase 2)
  cost-breakdown-chart.tsx         → Bar chart расходов (Phase 3)
  cost-timeline-chart.tsx          → Line chart daily costs (Phase 3)
  health-status-card.tsx           → Карточка компонента (Phase 2)
  anomaly-table.tsx                → Таблица аномалий (Phase 2)

src/stores/
  agent-ops.ts                     → Zustand store (Phase 2)

src/lib/api/
  agents-api.ts                    → Typed API client

src/types/
  agent-ops.ts                     → TypeScript типы

src/hooks/
  use-polling-query.ts             → Polling хук с stale-while-revalidate
```

---

## Дизайн-принципы

1. **Консистентность с Hub** — shadcn/ui, CSS custom properties, Inter Variable
2. **Dark-first** — OKLCH токены, все компоненты dark-native
3. **Information density** — аналитический dashboard, много данных
4. **Drill-down pattern** — Overview → Fleet → Agent Detail → Run Detail
5. **Polling, не WebSocket** — 30с интервал, простота
6. **Responsive** — desktop first (1280px+), не ломается на планшете
7. **Русский UI + английские термины** — заголовки на русском, статусы (Running, Idle, CB Open) на английском

---

# Часть 2: Implementation Plan

> Синтез ревью 5 агентов. Решения по конфликтам и фазирование.

## Принятые решения

### 1. Scope: безжалостный MVP

Данила управляет системой в одиночку. 6 агентов, 2-4 запуска в день. Это НЕ Datadog для 500 микросервисов. Берём только то, что реально нужно одному человеку для утренней проверки и диагностики сбоя.

### 2. Backend: API внутри процесса Oleg

FastAPI на порту 8091 внутри процесса Oleg. Единственный правильный вариант — нужен доступ к in-memory CircuitBreaker и live agent state.

### 3. Таблицы: event_log — ДА, остальное — отложено

- **PM**: "zero new tables" — идеалистично, activity feed невозможно на UNION из 3 таблиц.
- **Developer**: 3 таблицы — anomaly_log и circuit_breaker_log заменяем записями в event_log с event_type + metadata JSON.
- **Agent Expert**: llm_call_log + tool_call_log + trace_id — Phase 3.

**Решение**: 1 новая таблица `event_log`. CB и anomaly — event_type записи. trace_id — Phase 3.

### 4. Интерактивность: Sheet drill-down Phase 2, CB Reset — Phase 1

Sheet drill-down для агента — Phase 2. Time picker (3 пресета: 24ч/7д/30д) — Phase 2. Alert banner — Phase 1B. CB Reset кнопка — Phase 1B.

### 5. Telemetry: собирать trace_id СЕЙЧАС, отображать ПОТОМ

В Phase 1C: trace_id в ChainResult и report_log + расширяем report_log (tokens, retry_count). Полная telemetry — Phase 3.

---

## MVP Scope (Phase 1)

### Что входит

1. **Summary KPI Cards** (4 шт)
2. **Agent Fleet Table**: 6 агентов с CB state
3. **Activity Feed**: unified event log, 30 событий, auto-refresh 30с
4. **Circuit Breaker Panel**: 6 карточек + кнопка Reset
5. **Cost Breakdown**: бары по агентам за сутки
6. **Alert Banner**: critical алерты над контентом
7. **LiveIndicator**: пульс + "обновлено Xс назад"
8. **Pipeline Timeline**: 7-дневный grid
9. **CB Reset**: единственная write-операция в MVP

### Что НЕ входит (и почему)

| Фича | Почему НЕ в MVP |
|------|----------------|
| Time Range Picker | При 2-4 запусках/день фиксированные периоды достаточны |
| Agent Detail Sheet | 6 агентов видны в таблице. Phase 2 |
| Sub-pages (fleet, logs, pipelines, costs, health) | Overview достаточно для MVP. Phase 2+ |
| WebSocket/SSE | Polling 30с достаточно |
| llm_call_log / tool_call_log | Серьёзная инструментация. Phase 3 |
| Chain Waterfall View | Требует trace_id + llm_call_log. Phase 3 |
| Manual Report Trigger | SSH остаётся запасным. Phase 2 |
| Anomaly threshold editor | Редко меняются. Phase 3 |

---

## Backend Architecture

**Размещение**: `agents/oleg/api/` — FastAPI app, mount в процесс Oleg, порт 8091.

### API Endpoints (MVP)

| Method | Path | Описание | Источник |
|--------|------|----------|----------|
| GET | `/api/agents/overview` | 4 KPI метрики | report_log + CB in-memory |
| GET | `/api/agents` | Fleet table data | registry + report_log + CB |
| GET | `/api/agents/{name}` | Detail по агенту | registry + report_log + CB + tools |
| GET | `/api/agents/activity` | Unified feed | event_log |
| GET | `/api/agents/pipeline/timeline` | 7-дневный grid | report_log |
| GET | `/api/agents/costs` | Cost breakdown | report_log |
| GET | `/api/agents/health` | Health check | watchdog.check_health() |
| POST | `/api/agents/{name}/circuit-breaker/reset` | Сброс CB | in-memory CB |

### API Endpoints (Phase 2+)

```
GET /api/agents/fleet/:name/runs    → история запусков агента
GET /api/agents/fleet/:name/errors  → ошибки агента
GET /api/agents/pipelines           → pipeline runs (paginated, filterable)
GET /api/agents/pipelines/:id       → детальный run с gate checks и chain steps
GET /api/agents/gates               → gate history (paginated)
GET /api/agents/logs                → unified event stream (paginated, filterable)
GET /api/agents/costs/summary       → cost summary (today, week, month)
GET /api/agents/costs/by-tier       → breakdown по model tiers
GET /api/agents/costs/timeline      → daily costs за период
GET /api/agents/costs/by-report     → avg cost per report type
GET /api/agents/health/breakers     → circuit breaker states
GET /api/agents/health/watchdog     → watchdog event history
GET /api/agents/health/anomalies    → anomaly history
```

### Data Model Changes

1. Новая таблица `event_log`:
```sql
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    agent TEXT,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    cost_usd REAL,
    metadata TEXT  -- JSON
);
CREATE INDEX idx_event_log_ts ON event_log(timestamp DESC);
CREATE INDEX idx_event_log_agent ON event_log(agent);
```

2. Расширение report_log:
```sql
ALTER TABLE report_log ADD COLUMN notion_url TEXT;
```

3. Точки записи в event_log (5 мест):
   - `report_pipeline.py` — report_complete / report_failed / report_skipped
   - `anomaly_monitor.py` — anomaly_alert
   - `gate_checker.py` — gate_check
   - `circuit_breaker.py` — circuit_breaker_trip / circuit_breaker_reset
   - `watchdog.py` — watchdog_heartbeat

### Backend File Structure

```
agents/oleg/api/
  __init__.py
  app.py            # FastAPI app с CORS
  deps.py           # DI: state_store, orchestrator ref
  schemas.py        # Pydantic response models
  registry.py       # Static agent metadata (6 agents)
  routes/
    __init__.py
    overview.py     # GET /overview
    agents.py       # GET /agents, GET /agents/{name}, POST /cb/reset
    activity.py     # GET /activity
    pipeline.py     # GET /pipeline/timeline
    costs.py        # GET /costs
    health.py       # GET /health
```

---

## API Contract — TypeScript Interfaces

```typescript
// --- Overview ---
interface AgentOverview {
  active_agents: number;
  total_agents: number;
  blocked_agents: { name: string; reason: string }[];
  reports_today: number;
  reports_7d_series: number[];
  success_rate_7d: number;
  success_rate_trend: number;
  cost_today_usd: number;
  cost_7d_series: number[];
  last_heartbeat: string;
  system_healthy: boolean;
  timestamp: string;
}

// --- Fleet ---
interface AgentSummary {
  name: string;
  display_name: string;
  role: string;
  model_tier: "LIGHT" | "MAIN" | "HEAVY" | "FREE";
  status: "running" | "idle" | "error" | "cb_open" | "disabled";
  circuit_breaker: {
    state: "closed" | "open" | "half_open";
    failure_count: number;
    failure_threshold: number;
    cooldown_sec: number;
    last_failure: number | null;
  };
  last_run_at: string | null;
  runs_today: number;
  errors_today: number;
  avg_duration_ms: number;
  cost_today_usd: number;
}

interface AgentListResponse {
  agents: AgentSummary[];
}

// --- Activity Feed ---
interface ActivityEvent {
  id: number;
  timestamp: string;
  event_type: string;
  agent: string;
  summary: string;
  status: "success" | "error" | "warning" | "info";
  duration_ms?: number;
  cost_usd?: number;
  metadata: Record<string, unknown>;
}

interface ActivityFeedResponse {
  events: ActivityEvent[];
  has_more: boolean;
}

// --- Pipeline Timeline ---
interface TimelineDay {
  date: string;
  weekday: string;
  reports: {
    report_type: string;
    display_name: string;
    status: "success" | "failed" | "degraded" | "skipped";
    duration_ms: number;
    cost_usd?: number;
  }[];
  stats: { success: number; failed: number; degraded: number; skipped: number };
}

interface PipelineTimelineResponse {
  days: TimelineDay[];
}

// --- Costs ---
interface AgentCost {
  agent: string;
  cost_usd: number;
  pct: number;
  runs: number;
}

interface CostsResponse {
  period_days: number;
  total_usd: number;
  by_agent: AgentCost[];
  daily_series: { date: string; cost_usd: number }[];
}

// --- Health ---
interface HealthCheck {
  component: string;
  status: "ok" | "warning" | "error";
  detail: string;
}

interface HealthResponse {
  overall: "healthy" | "degraded" | "unhealthy";
  checks: HealthCheck[];
  circuit_breakers: AgentSummary["circuit_breaker"][];
  last_heartbeat: string;
  uptime_hours: number;
}

// --- CB Reset ---
interface CBResetResponse {
  name: string;
  previous_state: string;
  new_state: string;
  reset_at: string;
}
```

---

## Polling Strategy

| Endpoint | Интервал | Обоснование |
|----------|----------|-------------|
| /overview | 30с | KPI cards |
| /agents | 30с | Fleet status |
| /activity | 30с | Feed |
| /pipeline/timeline | 5 мин | Исторические данные |
| /costs | 5 мин | Агрегат |
| /health | 60с | Редко меняется |

---

## Фазы реализации

### Phase 1A: Backend Foundation (1 день)

**Цель**: API запущен, curl отвечает JSON.

Файлы создать:
- `agents/oleg/api/__init__.py`
- `agents/oleg/api/app.py` — FastAPI app с CORS
- `agents/oleg/api/deps.py` — DI (state_store, orchestrator ref)
- `agents/oleg/api/schemas.py` — Pydantic models
- `agents/oleg/api/registry.py` — AGENT_REGISTRY dict (6 агентов)
- `agents/oleg/api/routes/__init__.py`
- `agents/oleg/api/routes/overview.py`
- `agents/oleg/api/routes/agents.py`
- `agents/oleg/api/routes/costs.py`
- `agents/oleg/api/routes/health.py`

Файлы модифицировать:
- `agents/oleg/storage/state_store.py` — добавить event_log, метод log_event(), ALTER report_log
- `agents/oleg/main.py` — mount FastAPI на порту 8091
- `agents/oleg/executor/circuit_breaker.py` — добавить reset() если нет

**Критерий**: `curl http://localhost:8091/api/agents/overview` → валидный JSON.

### Phase 1B: Frontend Overview (1-2 дня)

**Цель**: страница /system/agents показывает живые данные.

Файлы создать (8 компонентов + страница + types + hook):
- `src/components/agents/agent-metric-card.tsx`
- `src/components/agents/agent-fleet-table.tsx`
- `src/components/agents/activity-feed.tsx`
- `src/components/agents/pipeline-timeline.tsx`
- `src/components/agents/circuit-breaker-grid.tsx`
- `src/components/agents/cost-breakdown.tsx`
- `src/components/agents/live-indicator.tsx`
- `src/components/agents/alert-banner.tsx`
- `src/pages/agents-overview.tsx`
- `src/types/agent-ops.ts`
- `src/hooks/use-polling-query.ts`

Файлы модифицировать:
- `src/router.tsx` — заменить stub
- `src/index.css` — добавить `--wk-*-surface` токены

Layout:
```
[AlertBanner]                                               -- sticky
[MetricCard] [MetricCard] [MetricCard] [MetricCard]         -- grid-cols-4
[FleetTable ──────────────] [ActivityFeed]                   -- grid-cols-[1.5fr_1fr]
[PipelineTimeline ────────────────────]                      -- full-width
[CircuitBreakerGrid] [CostBreakdown]                        -- grid-cols-2
```

**Критерий**: страница открывается, данные из API, auto-refresh 30с, CB Reset работает.

### Phase 1C: Event Integration (0.5 дня)

**Цель**: event_log заполняется реальными данными.

Файлы модифицировать:
- `agents/oleg/pipeline/report_pipeline.py` — log_event() в complete/fail/skip
- `agents/oleg/anomaly/anomaly_monitor.py` — log_event() при алерте
- `agents/oleg/pipeline/gate_checker.py` — log_event() при проверке
- `agents/oleg/executor/circuit_breaker.py` — log_event() при trip/reset
- `agents/oleg/watchdog/watchdog.py` — log_event() при heartbeat
- `agents/oleg/api/routes/activity.py` — NEW: GET /activity
- `agents/oleg/api/routes/pipeline.py` — NEW: GET /pipeline/timeline

**Критерий**: после pipeline run, GET /activity → 3+ событий. Activity Feed показывает реальные данные.

### Phase 2: Interactivity (2 дня)

1. Agent Detail Sheet (клик по строке Fleet)
2. Activity Feed фильтры (All / Errors / Warnings)
3. Сортировка Fleet Table
4. Time preset selector (24ч / 7д / 30д)
5. Pipeline block tooltip
6. Error detail Sheet
7. Manual Report Trigger
8. Sub-pages: fleet, logs, pipelines, health

### Phase 3: Agent Observability (2-3 дня)

Backend: trace_id, TelemetryBuffer, llm_call_log, tool_call_log, расширение report_log.
Frontend: Chain Waterfall View, Tool Analytics, Cost by Model Tier, Quality Trends.

### Phase 4: Cost Tracker (1-2 дня)

Cost summary, breakdown charts, timeline, cost per report type.

---

## Критерии приёмки

### Phase 1
- [ ] `/system/agents` открывается без ошибок
- [ ] 4 KPI карточки с реальными данными
- [ ] Fleet Table: 6 агентов с реальными статусами
- [ ] CB Panel с кнопкой Reset (работает)
- [ ] Activity Feed с реальными событиями
- [ ] Pipeline Timeline: 7 дней
- [ ] Cost Breakdown за сутки
- [ ] LiveIndicator: "обновлено Xс назад", "Offline" при 3 failed fetches
- [ ] AlertBanner при CB Open / critical anomaly
- [ ] Auto-refresh 30с без перезагрузки
- [ ] Responsive: md стекается, lg как в мокапе
- [ ] Утренняя проверка: за 10с видно состояние системы

---

## Риски

| Риск | Impact | Mitigation |
|------|--------|------------|
| FastAPI в Oleg — attack surface | Medium | CORS localhost + Hub domain |
| SQLite write lock при event_log | Low | WAL mode, записи <1KB |
| Порт 8091 не проброшен через nginx | Blocker | proxy_pass в nginx на Timeweb |
| event_log пустой до первого run | UX | Empty state: "Следующий запуск: 09:00" |
| CB state теряется при рестарте | Known | CB persistence — Phase 3 |
| Oleg может не поддерживать async FastAPI | Medium | uvicorn в отдельном thread |

---

## Решения по конфликтам экспертов

| Конфликт | Решение | Обоснование |
|----------|---------|-------------|
| PM: 0 tables vs Dev: 3 vs Expert: 2 | 1 таблица (event_log) | CB/anomaly как event_type + JSON metadata |
| UX Critic: "too static" vs Simplicity | Базовая интерактивность Phase 1 (CB Reset, auto-refresh, alert). Drill-down — Phase 2 | 6 агентов, 2-4 запуска/день |
| Designer: 9 компонентов | 8 в Phase 1B | Правильная модульность, не bloat |
| Dev: polling 15-30s vs Expert: flush buffer | Polling 30с. Event_log — сразу. TelemetryBuffer — Phase 3 | При 2-4 запусках/день 30с достаточно |
| Expert: llm_call_log NOW | Phase 3 | Инструментация через 5 слоёв — сначала рабочий dashboard |

---

## Mockup

HTML мокап: `wookiee-hub/mockups/agent-dashboard.html`

## Reviews

- `wookiee-hub/mockups/reviews/01-ux-critic.md` — UX/UI review (5.5/10)
- `wookiee-hub/mockups/reviews/02-product-manager.md` — Feature Matrix
- `wookiee-hub/mockups/reviews/04-designer.md` — Design recommendations
- `wookiee-hub/mockups/reviews/05-developer.md` — Technical architecture
- `wookiee-hub/mockups/reviews/06-agent-expert.md` — Agent observability
