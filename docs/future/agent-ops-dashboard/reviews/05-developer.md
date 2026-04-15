# Agent 5: Developer — Technical Architecture

## Решение по сервису

**Новый FastAPI-сервис внутри процесса Oleg** (`agents/oleg/api/`) — НЕ расширение product_matrix_api.

Обоснование:
1. **Разные базы данных**: product_matrix_api работает с PostgreSQL (Supabase), agent ops читает из SQLite (`state_store.db`) и in-memory состояния Python-процесса Oleg.
2. **Разные lifecycle**: product_matrix_api — stateless CRUD, agent_ops — должен жить в одном процессе с Oleg для доступа к in-memory состоянию (circuit breakers, текущие chain runs).
3. **Изоляция отказов**: баг в дашборде не должен ронять товарную матрицу.
4. **Практическое решение**: API запускается как часть процесса Oleg (добавляется FastAPI app внутрь `agents/oleg/api/`), слушает на отдельном порту (например, 8091). Это позволяет напрямую читать in-memory состояние без IPC.

Архитектура:
```
agents/oleg/
  api/
    app.py          # FastAPI app, mount в main.py Oleg
    routes/
      overview.py   # GET /api/agents/overview
      agents.py     # GET /api/agents/{name}, GET /api/agents
      pipeline.py   # GET /api/agents/pipeline/...
      activity.py   # GET /api/agents/activity
      health.py     # GET /api/agents/health
    deps.py         # Dependency injection (state_store, orchestrator ref)
    schemas.py      # Pydantic response models
    registry.py     # Static agent metadata
```

---

## API Endpoints

### GET /api/agents/overview

Сводные метрики для карточек вверху дашборда.

**Источники данных**: `state_store.report_log` (SQLite), in-memory circuit breakers, in-memory orchestrator state.

```json
{
  "active_agents": 5,
  "total_agents": 6,
  "blocked_agents": [{"name": "validator", "reason": "circuit_breaker_open"}],
  "reports_today": 4,
  "reports_7d_series": [3, 4, 4, 3, 5, 4, 4],
  "success_rate_7d": 87.5,
  "success_rate_trend": -4.2,
  "cost_today_usd": 0.42,
  "cost_7d_series": [0.31, 0.38, 0.35, 0.42, 0.36, 0.40, 0.42],
  "last_heartbeat": "2026-03-31T06:15:00Z",
  "system_healthy": true,
  "timestamp": "2026-03-31T09:17:00+03:00"
}
```

### GET /api/agents

Список всех агентов с текущим статусом (таблица Fleet).

**Источники**: agent registry (статический), `state_store.report_log`, in-memory CB.

```json
{
  "agents": [
    {
      "name": "reporter",
      "display_name": "Reporter",
      "role": "Аналитик",
      "model_tier": "MAIN",
      "model": "z-ai/glm-4.7",
      "status": "idle",
      "circuit_breaker": {
        "state": "closed",
        "failure_count": 0,
        "failure_threshold": 3,
        "cooldown_sec": 300
      },
      "last_run_at": "2026-03-31T09:15:00+03:00",
      "runs_today": 8,
      "errors_today": 0,
      "avg_duration_ms": 45000,
      "cost_today_usd": 0.18,
      "tools_count": 8
    }
  ]
}
```

### GET /api/agents/{name}

Детальная информация по агенту (для страницы Fleet > Agent Detail).

**Источники**: agent registry, `state_store.report_log`, in-memory CB, agent class introspection.

```json
{
  "name": "reporter",
  "display_name": "Reporter",
  "role": "Аналитик",
  "description": "Основной агент финансовой аналитики. Генерирует ежедневные, еженедельные и месячные отчёты.",
  "model_tier": "MAIN",
  "model": "z-ai/glm-4.7",
  "max_iterations": 10,
  "tool_timeout_sec": 30.0,
  "total_timeout_sec": 300.0,
  "status": "idle",
  "circuit_breaker": {
    "state": "closed",
    "failure_count": 0,
    "failure_threshold": 3,
    "cooldown_sec": 300,
    "last_failure": null
  },
  "tools": [
    {"name": "get_brand_finance", "description": "Получить финансовые данные бренда за период"},
    {"name": "get_margin_levers", "description": "Анализ маржинальных рычагов"}
  ],
  "system_prompt_preview": "Ты — Reporter, аналитик бренда Wookiee...",
  "report_types": ["daily", "weekly", "monthly"],
  "stats_7d": {
    "total_runs": 28,
    "successful": 26,
    "failed": 2,
    "avg_duration_ms": 45000,
    "total_cost_usd": 1.24,
    "avg_chain_steps": 1.3
  },
  "recent_runs": [
    {
      "id": 142,
      "report_type": "daily",
      "status": "success",
      "created_at": "2026-03-31T09:15:00+03:00",
      "duration_ms": 134000,
      "cost_usd": 0.08,
      "chain_steps": 1,
      "error": null
    }
  ]
}
```

### GET /api/agents/activity

Unified activity feed (Live Activity panel).

**Query params**: `limit` (default 50), `agent` (filter), `status` (filter), `since` (ISO datetime).

**Источники**: `state_store.report_log` + новая таблица `event_log`.

```json
{
  "events": [
    {
      "id": 301,
      "timestamp": "2026-03-31T09:15:00+03:00",
      "event_type": "report_complete",
      "agent": "reporter",
      "summary": "Daily Report (WB) -> Notion опубликован",
      "status": "success",
      "duration_ms": 134000,
      "cost_usd": 0.08,
      "metadata": {
        "report_type": "daily",
        "notion_url": "https://notion.so/...",
        "chain_steps": 1
      }
    },
    {
      "id": 300,
      "timestamp": "2026-03-31T09:12:00+03:00",
      "event_type": "anomaly_alert",
      "agent": "anomaly_monitor",
      "summary": "WB Выручка: 1.2M vs avg 1.5M (-20%)",
      "status": "warning",
      "metadata": {
        "metric": "revenue",
        "channel": "wb",
        "deviation_pct": -20.0,
        "severity": "warning"
      }
    },
    {
      "id": 299,
      "timestamp": "2026-03-31T09:10:00+03:00",
      "event_type": "gate_check",
      "agent": "gate_checker",
      "summary": "Pre-flight: WB+OZON gates passed",
      "status": "success",
      "metadata": {
        "marketplace": "wb",
        "gates_passed": 4,
        "gates_failed": 0
      }
    },
    {
      "id": 298,
      "timestamp": "2026-03-31T08:00:00+03:00",
      "event_type": "circuit_breaker_trip",
      "agent": "validator",
      "summary": "Circuit breaker OPEN: 3 consecutive failures",
      "status": "error",
      "metadata": {
        "previous_state": "closed",
        "new_state": "open",
        "failure_count": 3
      }
    }
  ],
  "has_more": true
}
```

### GET /api/agents/pipeline/timeline

Timeline данные для pipeline visualization (7 дней).

**Query params**: `days` (default 7).

**Источники**: `state_store.report_log`, `state_store.gate_history`.

```json
{
  "days": [
    {
      "date": "2026-03-31",
      "weekday": "Пн",
      "reports": [
        {
          "report_type": "daily",
          "display_name": "Ежедн.",
          "status": "success",
          "duration_ms": 134000,
          "cost_usd": 0.08,
          "agent": "reporter",
          "notion_url": "https://notion.so/..."
        },
        {
          "report_type": "marketing_weekly",
          "display_name": "Марк. нед.",
          "status": "degraded",
          "duration_ms": 98000,
          "warnings": ["Section 'Блогеры' degraded to placeholder"]
        }
      ],
      "stats": {
        "success": 3,
        "failed": 1,
        "degraded": 0,
        "skipped": 0
      }
    }
  ]
}
```

### GET /api/agents/health

Детальный health check (panel Health).

**Источники**: watchdog.check_health(), in-memory CB statuses, state_store heartbeat.

```json
{
  "overall": "healthy",
  "checks": [
    {"component": "state_store", "status": "ok", "detail": "SQLite accessible"},
    {"component": "llm_client", "status": "ok", "detail": "OpenRouter responding, 120ms"},
    {"component": "wb_data", "status": "ok", "detail": "Fresh data for 2026-03-30"},
    {"component": "ozon_data", "status": "ok", "detail": "Fresh data for 2026-03-30"},
    {"component": "notion", "status": "ok", "detail": "API accessible"},
    {"component": "telegram", "status": "ok", "detail": "Bot active"}
  ],
  "circuit_breakers": [
    {"name": "reporter", "state": "closed", "failure_count": 0},
    {"name": "validator", "state": "open", "failure_count": 3, "last_failure": 1711875600.0}
  ],
  "last_heartbeat": "2026-03-31T06:15:00Z",
  "uptime_hours": 72.3
}
```

### GET /api/agents/costs

Разбивка затрат по агентам (Cost panel).

**Query params**: `days` (default 7).

**Источники**: `state_store.report_log` (cost_usd), `state_store.recommendation_log` (advisor_cost_usd, validator_cost_usd).

```json
{
  "period_days": 7,
  "total_usd": 2.84,
  "by_agent": [
    {"agent": "reporter", "cost_usd": 1.26, "pct": 44.4, "runs": 28},
    {"agent": "marketer", "cost_usd": 0.72, "pct": 25.4, "runs": 6},
    {"agent": "funnel", "cost_usd": 0.32, "pct": 11.3, "runs": 2},
    {"agent": "researcher", "cost_usd": 0.24, "pct": 8.5, "runs": 4},
    {"agent": "advisor", "cost_usd": 0.18, "pct": 6.3, "runs": 8},
    {"agent": "validator", "cost_usd": 0.12, "pct": 4.2, "runs": 5}
  ],
  "daily_series": [
    {"date": "2026-03-25", "cost_usd": 0.31},
    {"date": "2026-03-26", "cost_usd": 0.38}
  ]
}
```

### POST /api/agents/{name}/circuit-breaker/reset

Ручной сброс circuit breaker (кнопка "Reset" в UI).

**Источник**: in-memory CB instance.

```json
// Request: empty body
// Response:
{
  "name": "validator",
  "previous_state": "open",
  "new_state": "closed",
  "reset_at": "2026-03-31T09:20:00+03:00"
}
```

---

## TypeScript Types

```typescript
// ─── Overview ─────────────────────────────────────────────
interface AgentOverview {
  active_agents: number;
  total_agents: number;
  blocked_agents: BlockedAgent[];
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

interface BlockedAgent {
  name: string;
  reason: string;
}

// ─── Agent List / Fleet ───────────────────────────────────
interface AgentListResponse {
  agents: AgentSummary[];
}

interface AgentSummary {
  name: string;
  display_name: string;
  role: string;
  model_tier: "LIGHT" | "MAIN" | "HEAVY" | "FREE";
  model: string;
  status: AgentStatus;
  circuit_breaker: CircuitBreakerState;
  last_run_at: string | null;
  runs_today: number;
  errors_today: number;
  avg_duration_ms: number;
  cost_today_usd: number;
  tools_count: number;
}

type AgentStatus = "running" | "idle" | "error" | "cb_open" | "disabled";

interface CircuitBreakerState {
  state: "closed" | "open" | "half_open";
  failure_count: number;
  failure_threshold: number;
  cooldown_sec: number;
  last_failure: number | null;
}

// ─── Agent Detail ─────────────────────────────────────────
interface AgentDetail extends AgentSummary {
  description: string;
  max_iterations: number;
  tool_timeout_sec: number;
  total_timeout_sec: number;
  tools: ToolDefinition[];
  system_prompt_preview: string;
  report_types: string[];
  stats_7d: AgentStats;
  recent_runs: ReportRun[];
}

interface ToolDefinition {
  name: string;
  description: string;
}

interface AgentStats {
  total_runs: number;
  successful: number;
  failed: number;
  avg_duration_ms: number;
  total_cost_usd: number;
  avg_chain_steps: number;
}

interface ReportRun {
  id: number;
  report_type: string;
  status: "success" | "error" | "skipped";
  created_at: string;
  duration_ms: number;
  cost_usd: number;
  chain_steps: number;
  error: string | null;
}

// ─── Activity Feed ────────────────────────────────────────
interface ActivityFeedResponse {
  events: ActivityEvent[];
  has_more: boolean;
}

interface ActivityEvent {
  id: number;
  timestamp: string;
  event_type: EventType;
  agent: string;
  summary: string;
  status: "success" | "error" | "warning" | "info";
  duration_ms?: number;
  cost_usd?: number;
  metadata: Record<string, unknown>;
}

type EventType =
  | "report_complete"
  | "report_failed"
  | "report_skipped"
  | "anomaly_alert"
  | "gate_check"
  | "circuit_breaker_trip"
  | "circuit_breaker_reset"
  | "watchdog_heartbeat"
  | "recommendation_generated";

// ─── Pipeline Timeline ────────────────────────────────────
interface PipelineTimelineResponse {
  days: TimelineDay[];
}

interface TimelineDay {
  date: string;
  weekday: string;
  reports: TimelineReport[];
  stats: {
    success: number;
    failed: number;
    degraded: number;
    skipped: number;
  };
}

interface TimelineReport {
  report_type: string;
  display_name: string;
  status: "success" | "failed" | "degraded" | "skipped";
  duration_ms: number;
  cost_usd?: number;
  agent: string;
  notion_url?: string;
  warnings?: string[];
  error?: string;
}

// ─── Health ───────────────────────────────────────────────
interface HealthResponse {
  overall: "healthy" | "degraded" | "unhealthy";
  checks: HealthCheck[];
  circuit_breakers: CircuitBreakerState[];
  last_heartbeat: string;
  uptime_hours: number;
}

interface HealthCheck {
  component: string;
  status: "ok" | "warning" | "error";
  detail: string;
}

// ─── Costs ────────────────────────────────────────────────
interface CostsResponse {
  period_days: number;
  total_usd: number;
  by_agent: AgentCost[];
  daily_series: { date: string; cost_usd: number }[];
}

interface AgentCost {
  agent: string;
  cost_usd: number;
  pct: number;
  runs: number;
}
```

---

## Data Layer Changes

### 1. Новая таблица: `event_log`

Unified event log для activity feed. Сейчас события разбросаны: report_log хранит отчёты, anomaly alerts уходят в Telegram и теряются, gate_history хранит гейты без контекста, CB transitions только в логах.

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,       -- 'report_complete', 'anomaly_alert', 'gate_check', 'cb_trip', etc.
    agent TEXT,                      -- 'reporter', 'anomaly_monitor', 'gate_checker', etc.
    summary TEXT NOT NULL,           -- Human-readable одна строка
    status TEXT NOT NULL,            -- 'success', 'error', 'warning', 'info'
    duration_ms INTEGER,
    cost_usd REAL,
    metadata TEXT                    -- JSON blob с деталями
);

CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_agent ON event_log(agent);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type);
```

### 2. Новая таблица: `circuit_breaker_log`

Персистентная история CB transitions (сейчас only in-memory, теряется при рестарте).

```sql
CREATE TABLE IF NOT EXISTS circuit_breaker_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    breaker_name TEXT NOT NULL,
    previous_state TEXT NOT NULL,    -- 'closed', 'open', 'half_open'
    new_state TEXT NOT NULL,
    failure_count INTEGER,
    trigger TEXT                     -- 'failure_threshold', 'cooldown_elapsed', 'manual_reset', 'test_success'
);
```

### 3. Новая таблица: `anomaly_log`

Персистентные anomaly alerts (сейчас fire-and-forget в Telegram).

```sql
CREATE TABLE IF NOT EXISTS anomaly_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metric TEXT NOT NULL,
    channel TEXT NOT NULL,
    current_value REAL,
    avg_value REAL,
    deviation_pct REAL,
    direction TEXT,                  -- 'up', 'down'
    severity TEXT,                   -- 'warning', 'critical'
    commentary TEXT                  -- LLM commentary if generated
);
```

### 4. Расширение `report_log`

Добавить поле `notion_url` для прямой ссылки из timeline.

```sql
ALTER TABLE report_log ADD COLUMN notion_url TEXT;
```

### 5. Точки интеграции (записи в event_log)

Минимальные изменения в существующем коде:

| Компонент | Файл | Изменение |
|-----------|------|-----------|
| report_pipeline | `pipeline/report_pipeline.py` | После шага 6/7 — `state_store.log_event(...)` |
| anomaly_monitor | `anomaly/anomaly_monitor.py` | В `check_and_alert()` — `state_store.log_event(...)` + `log_anomaly(...)` |
| gate_checker | `pipeline/gate_checker.py` | В `check_all()` — `state_store.log_event(...)` |
| circuit_breaker | `executor/circuit_breaker.py` | В `record_failure()/record_success()` — callback в state_store |
| watchdog | `watchdog/watchdog.py` | В `heartbeat()` / `on_report_failure()` — `state_store.log_event(...)` |

### 6. Agent Registry (статический)

Файл `agents/oleg/api/registry.py` — декларативный реестр с метаданными, дополненный runtime introspection:

```python
AGENT_REGISTRY = {
    "reporter": {
        "display_name": "Reporter",
        "role": "Аналитик",
        "description": "Основной агент финансовой аналитики. Ежедневные, еженедельные, месячные отчёты.",
        "model_tier": "MAIN",
        "report_types": ["daily", "weekly", "monthly"],
    },
    "marketer": {
        "display_name": "Marketer",
        "role": "Маркетинг",
        "description": "Маркетинговая аналитика: реклама, продвижение, ДРР.",
        "model_tier": "MAIN",
        "report_types": ["marketing_weekly", "marketing_monthly"],
    },
    "funnel": {
        "display_name": "Funnel (Макар)",
        "role": "Воронка",
        "description": "Анализ воронки продаж WB: показы -> клики -> корзина -> заказы -> выкупы.",
        "model_tier": "MAIN",
        "report_types": ["funnel_weekly"],
    },
    "researcher": {
        "display_name": "Researcher",
        "role": "Исследователь",
        "description": "Глубокий исследовательский анализ при обнаружении аномалий.",
        "model_tier": "HEAVY",
        "report_types": [],
    },
    "advisor": {
        "display_name": "Advisor",
        "role": "Рекомендации",
        "description": "Генерация бизнес-рекомендаций на основе сигналов из отчётов.",
        "model_tier": "LIGHT",
        "report_types": [],
    },
    "validator": {
        "display_name": "Validator",
        "role": "Качество",
        "description": "Валидация рекомендаций advisor-а, проверка фактической корректности.",
        "model_tier": "MAIN",
        "report_types": [],
    },
}
```

Динамические данные (tools, system_prompt_preview, model) берутся из живых agent instances через `orchestrator.agents` dict. Registry предоставляет только статические метаданные, которые не зависят от runtime.

---

## Frontend Architecture

### Component Tree

```
/system/agents                    AgentOpsLayout (sub-navigation sidebar)
  /system/agents/overview         AgentOverviewPage (дефолт)
    SummaryCards                     4 карточки метрик
      SummaryCard                     отдельная карточка + sparkline
    MainGrid                        2-колоночный grid
      FleetTable                      таблица агентов
        FleetRow                        строка агента + status badge
      ActivityFeed                    live activity feed
        ActivityItem                    отдельное событие
    PipelineTimeline                7-дневный timeline блоков
      TimelineRow                     1 день
        TimelineBlock                   1 отчёт (success/failed/degraded/skipped)
    BottomBar                       2-колоночный grid
      CircuitBreakerPanel             CB statuses grid
        CircuitBreakerItem              отдельный breaker
      CostPanel                       cost breakdown bars
        CostRow                         агент + bar + value
  /system/agents/fleet            AgentFleetPage (расширенная таблица)
  /system/agents/fleet/:name      AgentDetailPage
    AgentHeader                     name, status, CB, model
    AgentTools                      список инструментов
    AgentRunHistory                 таблица последних запусков
    AgentPromptPreview              system prompt (collapsed)
  /system/agents/pipelines        PipelinesPage (расширенный timeline)
  /system/agents/logs             LogsPage (полный event_log)
  /system/agents/costs            CostsPage (расширенная аналитика затрат)
  /system/agents/health           HealthPage (detailed health checks)
```

### Routing

Замена stub-а `/system/agents` на layout с nested routes (аналогично `/system/matrix-admin`):

```tsx
// router.tsx — replace stub with nested layout
import { AgentOpsLayout } from "@/pages/agent-ops/agent-ops-layout"
import { AgentOverviewPage } from "@/pages/agent-ops/overview"
import { AgentFleetPage } from "@/pages/agent-ops/fleet"
import { AgentDetailPage } from "@/pages/agent-ops/agent-detail"
import { AgentPipelinesPage } from "@/pages/agent-ops/pipelines"
import { AgentLogsPage } from "@/pages/agent-ops/logs"
import { AgentCostsPage } from "@/pages/agent-ops/costs"
import { AgentHealthPage } from "@/pages/agent-ops/health"

// Replace:  { path: "/system/agents", element: <AgentsPage /> }
// With:
{
  path: "/system/agents",
  element: <AgentOpsLayout />,
  children: [
    { index: true, element: <Navigate to="/system/agents/overview" replace /> },
    { path: "overview", element: <AgentOverviewPage /> },
    { path: "fleet", element: <AgentFleetPage /> },
    { path: "fleet/:name", element: <AgentDetailPage /> },
    { path: "pipelines", element: <AgentPipelinesPage /> },
    { path: "logs", element: <AgentLogsPage /> },
    { path: "costs", element: <AgentCostsPage /> },
    { path: "health", element: <AgentHealthPage /> },
  ],
}
```

### Zustand Store

```typescript
// stores/agent-ops.ts
import { create } from "zustand"

interface AgentOpsState {
  // Overview data
  overview: AgentOverview | null;
  agents: AgentSummary[];
  activity: ActivityEvent[];
  timeline: TimelineDay[];
  health: HealthResponse | null;
  costs: CostsResponse | null;

  // Loading states
  loading: {
    overview: boolean;
    agents: boolean;
    activity: boolean;
    timeline: boolean;
    health: boolean;
    costs: boolean;
  };

  // Polling control
  pollingEnabled: boolean;
  lastFetchedAt: Record<string, number>;

  // Actions
  setOverview: (data: AgentOverview) => void;
  setAgents: (data: AgentSummary[]) => void;
  appendActivity: (events: ActivityEvent[]) => void;
  setTimeline: (data: TimelineDay[]) => void;
  setHealth: (data: HealthResponse) => void;
  setCosts: (data: CostsResponse) => void;
  setLoading: (key: string, value: boolean) => void;
  togglePolling: () => void;

  // Derived selectors
  getAgentByName: (name: string) => AgentSummary | undefined;
  getBlockedAgents: () => AgentSummary[];
}
```

Store не делает fetch сам — fetching управляется через `useApiQuery` или кастомный `usePollingQuery` хук. Store является единым кэшем.

### Data Fetching Strategy

**Polling** с переменным интервалом:

| Endpoint | Интервал | Обоснование |
|----------|----------|-------------|
| `/overview` | 30 сек | Summary карточки — основной экран |
| `/agents` (fleet) | 30 сек | Status может измениться (CB trip) |
| `/activity` | 15 сек | "Live" feed — самая частая |
| `/pipeline/timeline` | 5 мин | Исторические данные, обновляются редко |
| `/health` | 60 сек | Health checks не меняются часто |
| `/costs` | 5 мин | Агрегированные данные |
| `/agents/{name}` | 30 сек | Только когда страница открыта |

**Кастомный хук `usePollingQuery`**:

```typescript
function usePollingQuery<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: unknown[],
  options?: { enabled?: boolean; staleTime?: number }
): { data: T | null; loading: boolean; error: string | null; refetch: () => void }
```

- Polling останавливается когда вкладка неактивна (`document.hidden`)
- Stale-while-revalidate: показывает предыдущие данные пока идёт новый fetch
- При ошибке — exponential backoff (30s -> 60s -> 120s), автовосстановление при успехе

---

## Real-time Strategy

**Решение: Polling (не SSE, не WebSocket)**

Обоснование:
1. **Частота обновлений**: агенты запускаются раз в несколько часов (daily/weekly reports). Нет потока событий раз в секунду — polling каждые 15-30с более чем достаточно.
2. **Простота инфраструктуры**: единственный сервер (Timeweb Cloud), нет load balancer. SSE/WS добавляют сложность с keepalive, reconnection, nginx proxy buffering.
3. **Совместимость с архитектурой Hub**: существующий `useApiQuery` паттерн — polling. Не нужно вводить новую инфраструктуру.
4. **Деградация**: если API временно недоступен, UI продолжает показывать последние данные (stale-while-revalidate).

**Будущая оптимизация** (Phase 3+): если появится потребность в sub-second updates (например, наблюдение за live chain execution), добавить SSE endpoint `/api/agents/stream` для activity feed. Это аддитивное изменение, не требующее переписки.

---

## Implementation Phases

### Phase 1: Backend Foundation (3-4 часа)

**Зависимости**: нет.

1. Создать `agents/oleg/api/` — FastAPI app, schemas, deps
2. Добавить таблицы `event_log`, `circuit_breaker_log`, `anomaly_log` в `state_store.py`
3. Создать `agents/oleg/api/registry.py` — статический реестр агентов
4. Реализовать read-only endpoints:
   - `GET /api/agents/overview` — агрегация из report_log + CB statuses
   - `GET /api/agents` — registry + report_log stats + CB state
   - `GET /api/agents/{name}` — detail с tools introspection
   - `GET /api/agents/health` — прокси к watchdog.check_health()
5. Mount API в процесс Oleg (порт 8091)
6. Тест: curl вручную, проверить JSON responses

### Phase 2: Event Integration (2-3 часа)

**Зависимости**: Phase 1.

1. Добавить `log_event()` метод в StateStore
2. Инструментировать `report_pipeline.py` — запись в event_log при complete/fail/skip
3. Инструментировать `anomaly_monitor.py` — запись в anomaly_log + event_log
4. Добавить callback в `circuit_breaker.py` — запись в circuit_breaker_log + event_log
5. Инструментировать `gate_checker.py` — запись в event_log
6. Реализовать endpoints:
   - `GET /api/agents/activity` — query event_log
   - `GET /api/agents/pipeline/timeline` — агрегация report_log по дням
   - `GET /api/agents/costs` — агрегация cost из report_log + recommendation_log
7. Реализовать `POST /api/agents/{name}/circuit-breaker/reset`

### Phase 3: Frontend Overview Page (4-5 часов)

**Зависимости**: Phase 1 (минимально), Phase 2 (для activity feed).

1. Создать `usePollingQuery` хук
2. Создать Zustand store `agent-ops.ts`
3. Определить TypeScript типы в `types/agent-ops.ts`
4. Создать `AgentOpsLayout` с sub-navigation sidebar (аналогично `MatrixAdminLayout`)
5. Реализовать `AgentOverviewPage`:
   - SummaryCards (4 карточки)
   - FleetTable (таблица агентов)
   - ActivityFeed (live events)
   - PipelineTimeline (7-дневный grid)
   - CircuitBreakerPanel + CostPanel (bottom bar)
6. Обновить router.tsx — заменить stub на nested routes
7. Проверить responsive layout

### Phase 4: Detail Pages (2-3 часа)

**Зависимости**: Phase 3.

1. `AgentDetailPage` — fleet/:name с полной информацией по агенту
2. `AgentLogsPage` — полный event_log с фильтрацией и пагинацией
3. `AgentCostsPage` — расширенная аналитика затрат с графиками
4. `AgentHealthPage` — детальные health checks

### Итого: ~12-15 часов разработки

Приоритет: Phase 1 + Phase 3 дают MVP с работающим overview дашбордом. Phase 2 и 4 — обогащение данными и детальные страницы.
