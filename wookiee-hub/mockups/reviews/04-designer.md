# Agent 4: Frontend Designer -- Design Recommendations

Документ описывает стратегию перевода HTML-мокапа Agent Operations Dashboard в React-компоненты Wookiee Hub с учётом существующей дизайн-системы, shadcn/ui, и замечаний UX Critic (Agent 1).

---

## Design System Alignment

### Цветовые токены

Мокап использует собственные hex-переменные (`--bg-deep: #0a0a0f`, `--purple: #a78bfa`, и т.д.), которые нужно заменить на существующие oklch-токены Hub.

| Мокап | Hub-токен (dark) | Примечание |
|-------|------------------|------------|
| `--bg-deep: #0a0a0f` | `--background` (oklch 0.094) | Основной фон |
| `--bg-base: #0f0f17` | `--bg-soft` (oklch 0.131) | Sidebar / card bg |
| `--bg-surface: #16161f` | `--card` (oklch 0.150) | Панели, карточки |
| `--bg-elevated: #1c1c28` | `--secondary` (oklch 0.183) | Вложенные элементы |
| `--bg-hover: #22222f` | `--bg-hover` (oklch 0.183) | Прямое соответствие |
| `--border-subtle` | `--border` (oklch 0.186) | Использовать напрямую |
| `--purple: #a78bfa` | `--primary` (oklch 0.541 0.232 292) | Основной акцент |
| `--green: #4ade80` | `--wk-green` (oklch 0.696 0.150 163) | Успех |
| `--red: #f87171` | `--wk-red` (oklch 0.637 0.237 25) | Ошибки |
| `--yellow: #fbbf24` | `--wk-yellow` (oklch 0.795 0.160 80) | Предупреждения |
| `--blue: #60a5fa` | `--wk-blue` (oklch 0.623 0.214 260) | Running/info |
| `--cyan: #67e8f9` | Нет прямого аналога | Нужен новый токен |
| `--text-primary` | `--foreground` | Основной текст |
| `--text-secondary: #8888a0` | `--muted-foreground` | Вторичный текст |
| `--text-dim: #55556a` | `--text-dim` | Приглушённый текст |

**Новые токены для добавления в `index.css`:**

```css
/* Agent status surfaces — dark */
--wk-green-surface: oklch(0.696 0.150 163 / 12%);
--wk-red-surface: oklch(0.637 0.237 25 / 12%);
--wk-yellow-surface: oklch(0.795 0.160 80 / 12%);
--wk-blue-surface: oklch(0.623 0.214 260 / 15%);
--wk-cyan: oklch(0.720 0.150 195);
--wk-cyan-surface: oklch(0.720 0.150 195 / 12%);
```

Также понадобятся light-варианты этих поверхностей. Рекомендация -- добавить `*-surface` суффикс в обе темы для status badges и agent avatars.

**Что НЕ переносить из мокапа:**
- `--purple-glow`, `--cyan-glow` -- декоративные тени, в Hub не нужны
- `--purple-dim`, `--cyan-dim` как отдельные переменные -- заменяются на `bg-primary/15`, `bg-wk-blue/15` через Tailwind opacity modifier
- Градиентные `::after` полоски на карточках -- слишком декоративные для операционного дашборда

### Типографика

| Мокап | Hub |
|-------|-----|
| `font-family: 'Inter'` | `--font-sans: 'Inter Variable'` -- совпадает |
| `html { font-size: 14px }` | Hub использует rem-систему через Tailwind, базовый размер 16px. Мокапные `13px` = `text-[13px]`, `12px` = `text-xs` |
| `JetBrains Mono` для чисел | В Hub не подключён. **Решение:** использовать `tabular-nums` класс Tailwind вместо отдельного моношрифта. Для feed timestamps и cost values -- `font-mono` (подключить `JetBrains Mono` как `--font-mono` в `@theme`) |
| `font-size: 10px` (sidebar labels) | **Ниже минимума.** Заменить на `text-[11px]` минимум, лучше `text-xs` (12px). UX Critic P2 подтверждает |
| `font-size: 9px` (timeline blocks) | **Недопустимо.** Заменить на `text-[11px]` |

**Рекомендация по font-mono:**

Добавить в `index.css`:
```css
@import "@fontsource-variable/jetbrains-mono";

@theme inline {
  --font-mono: 'JetBrains Mono Variable', monospace;
}
```

### Spacing & Layout

Мокап использует абсолютные px-значения. Hub использует Tailwind spacing scale.

| Мокап | Hub Tailwind | Где используется |
|-------|-------------|-----------------|
| `padding: 24px 28px` | `p-6` (24px) | Main content area |
| `gap: 24px` | `gap-6` | Section spacing |
| `gap: 16px` | `gap-4` | Summary cards grid |
| `gap: 20px` | `gap-5` | Main grid |
| `gap: 10px` | `gap-2.5` | CB grid |
| `padding: 18px 20px` | `p-4` (16px) или `p-5` (20px) | Card padding |
| `border-radius: 14px` | `rounded-xl` (12px) или `rounded-2xl` (16px) | Панели |

Hub уже использует `rounded-[10px]` для карточек (MetricCard), `rounded-xl` для Card. Для консистентности -- все панели дашборда используют `Card` компонент (`rounded-xl`).

Главный layout-контейнер уже задан в `app-shell.tsx`:
```
<div className="flex-1 overflow-y-auto p-4 sm:p-6 pb-16 sm:pb-6">
  <div className="max-w-screen-2xl mx-auto">
```

Страница агентов должна использовать `space-y-4` (или `space-y-3` как DashboardPage) для вертикального ритма между секциями.

---

## Component Mapping

### Summary Cards --> MetricCard (extended)

**Существующий компонент:** `@/components/shared/metric-card.tsx`

MetricCard уже покрывает: label, value, change indicator, progress bar. Для agent dashboard нужно расширение:

- Добавить слот `sparkline` (SVG вместо div-бар из мокапа, как советует UX Critic)
- Добавить слот `subtitle` (текст "Validator -- circuit breaker open")
- Добавить `threshold` визуализацию (SLO-линия на sparkline, UX Critic P1)

**Реализация:** Создать `AgentMetricCard` как обёртку над `MetricCard` с дополнительным sparkline. Не модифицировать базовый MetricCard.

**Skeleton:** `MetricCardSkeleton` уже есть, расширить на sparkline (добавить `<Skeleton className="h-6 w-full mt-2" />`).

### Agent Fleet --> Card + Table

**Существующие компоненты:**
- `Card` + `CardHeader` + `CardTitle` + `CardAction` + `CardContent`
- Таблица -- raw HTML table (паттерн из `AuditLogPage`)
- `Badge` для статусов
- `StatusPill` для Running/Idle/CB Open

**Маппинг:**
```
<Card>
  <CardHeader>
    <CardTitle>Агенты <Badge variant="secondary">6</Badge></CardTitle>
    <CardAction><Button variant="ghost" size="sm">Управление</Button></CardAction>
  </CardHeader>
  <CardContent className="p-0"> <!-- p-0 для edge-to-edge таблицы -->
    <table> ... </table>
  </CardContent>
</Card>
```

Строки таблицы -- кликабельные (`cursor-pointer`, `hover:bg-bg-hover`). Аватары агентов -- `div` с `bg-wk-blue/15 text-wk-blue rounded-md w-8 h-8 flex items-center justify-center font-semibold text-sm`.

Status badges:
- Running: `<Badge variant="secondary" className="bg-wk-blue-surface text-wk-blue">`
- Idle: `<Badge variant="secondary" className="bg-wk-green-surface text-wk-green">`
- CB Open: `<Badge variant="destructive">`

### Activity Feed --> Card + custom FeedItem

**Существующие компоненты:**
- `Card` для контейнера
- Нет готового feed-компонента

**Новый компонент:** `AgentActivityFeed` + `FeedItem`

Контейнер:
```
<Card>
  <CardHeader>
    <CardTitle>Активность</CardTitle>
    <CardAction><!-- LiveIndicator --></CardAction>
  </CardHeader>
  <CardContent className="p-0">
    <div className="max-h-[420px] overflow-y-auto">
      {items.map(item => <FeedItem key={item.id} {...item} />)}
    </div>
  </CardContent>
</Card>
```

### Pipeline Timeline --> Card + custom TimelineGrid

**Существующие компоненты:**
- `Card` для контейнера
- Нет timeline-компонента

UX Critic рекомендует heatmap grid (P2), но для MVP текущий формат приемлем с доработками: tooltip при hover, кликабельность блоков.

**Новый компонент:** `PipelineTimeline` + `TimelineRow` + `TimelineBlock`

### Circuit Breakers --> Card + custom CBGrid

**Существующие компоненты:**
- `Card` для контейнера
- `ProgressBar` для визуализации failures (заменяет `cb-bar`)

**Новый компонент:** `CircuitBreakerCard` с подкомпонентом `CBItem`. Каждый CB-item -- вложенная карточка (`bg-secondary rounded-lg p-3`).

### Cost Breakdown --> Card + custom CostBar

**Существующие компоненты:**
- `Card` для контейнера
- `ProgressBar` -- можно адаптировать для cost bars

**Новый компонент:** `CostBreakdown` + `CostRow`

---

## Новые компоненты для создания

### 1. `AgentMetricCard`

```typescript
// @/components/agents/agent-metric-card.tsx
interface AgentMetricCardProps {
  label: string
  value: string
  unit?: string
  change?: string          // "+1", "-4.2%"
  changeType: "positive" | "negative" | "neutral"
  subtitle?: string        // "Validator — circuit breaker open"
  sparklineData?: number[] // 7-30 точек для SVG sparkline
  threshold?: number       // SLO-линия (0-100)
  onClick?: () => void
}
```

### 2. `AgentFleetTable`

```typescript
// @/components/agents/agent-fleet-table.tsx
interface AgentFleetTableProps {
  agents: AgentRow[]
  onAgentClick: (agentName: string) => void
  sortField?: string
  sortDir?: "asc" | "desc"
  onSort?: (field: string) => void
}

interface AgentRow {
  name: string
  role: string
  avatarColor: string // wk-blue | wk-green | ...
  status: "running" | "idle" | "cb-open" | "error"
  lastRun: string
  runsToday: number
  errorsToday: number
  avgDuration: string
  nextRun?: string
}
```

### 3. `ActivityFeed` + `FeedItem`

```typescript
// @/components/agents/activity-feed.tsx
interface ActivityFeedProps {
  items: FeedItemData[]
  isLive: boolean
  lastUpdated?: Date        // UX Critic P0: показать актуальность
  filter?: "all" | "errors" | "warnings" // UX Critic P1
  onItemClick?: (id: string) => void
}

interface FeedItemData {
  id: string
  timestamp: Date
  icon: "success" | "error" | "warning" | "retry" | "critical" | "heartbeat"
  agent: string
  task: string
  result: string
  resultType: "success" | "error" | "warning"
  duration?: string
  cost?: string
  isCritical?: boolean      // UX Critic P0: выделение critical
}
```

### 4. `PipelineTimeline`

```typescript
// @/components/agents/pipeline-timeline.tsx
interface PipelineTimelineProps {
  days: PipelineDay[]
  onBlockClick?: (day: string, pipeline: string) => void
}

interface PipelineDay {
  date: string
  weekday: string
  runs: PipelineRun[]
}

interface PipelineRun {
  pipeline: string
  status: "success" | "failed" | "degraded" | "skipped"
  duration?: string       // UX Critic P1: длительность
}
```

### 5. `CircuitBreakerGrid`

```typescript
// @/components/agents/circuit-breaker-grid.tsx
interface CircuitBreakerGridProps {
  breakers: CBState[]
  onReset?: (name: string) => void  // UX Critic P1: кнопка reset
}

interface CBState {
  name: string
  state: "closed" | "open" | "half-open"
  failures: number
  maxFailures: number
  cooldownRemaining?: number // секунды, для countdown
  lastError?: string
}
```

### 6. `CostBreakdown`

```typescript
// @/components/agents/cost-breakdown.tsx
interface CostBreakdownProps {
  total: number
  rows: CostRow[]
  period: string         // "24ч", "7д", "30д"
  onPeriodChange?: (period: string) => void
}

interface CostRow {
  agent: string
  amount: number
  percentage: number
  trend?: "up" | "down" | "flat"
  calls?: number         // UX Critic: количество LLM-вызовов
}
```

### 7. `LiveIndicator`

```typescript
// @/components/agents/live-indicator.tsx
interface LiveIndicatorProps {
  isConnected: boolean
  lastUpdated?: Date      // UX Critic P0
  refreshInterval?: number
}
```

### 8. `AlertBanner`

```typescript
// @/components/agents/alert-banner.tsx
interface AlertBannerProps {
  alerts: CriticalAlert[]
  onDismiss?: (id: string) => void
  onInvestigate?: (id: string) => void
}

interface CriticalAlert {
  id: string
  message: string
  severity: "critical" | "warning"
  timestamp: Date
  agentName?: string
}
```

### 9. `TimeRangePicker`

```typescript
// @/components/agents/time-range-picker.tsx
// Можно переиспользовать DateRangePicker из @/components/shared/date-range-picker.tsx
// и добавить пресеты: "1ч", "6ч", "24ч", "7д", "30д"
interface TimeRangePickerProps {
  value: string           // preset или custom range
  onChange: (range: string) => void
  presets?: string[]
}
```

---

## States Design

### Loading (Skeleton)

Каждая секция показывает собственный skeleton, не блокируя соседние секции (независимая загрузка через отдельные `useApiQuery`).

**Summary Cards:** 4 экземпляра `MetricCardSkeleton` в grid `grid-cols-2 lg:grid-cols-4`.

**Agent Fleet Table:**
```tsx
<Card>
  <CardHeader>
    <Skeleton className="h-5 w-32" />
  </CardHeader>
  <CardContent className="p-0">
    {/* TableSkeleton уже есть, расширить на 6 строк с аватаром */}
    {Array.from({ length: 6 }).map((_, i) => (
      <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-border/50">
        <Skeleton className="w-8 h-8 rounded-md" />
        <div className="flex-1 space-y-1">
          <Skeleton className="h-3.5 w-24" />
          <Skeleton className="h-2.5 w-16" />
        </div>
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-8" />
        <Skeleton className="h-3 w-8" />
        <Skeleton className="h-3 w-10" />
      </div>
    ))}
  </CardContent>
</Card>
```

**Activity Feed:** 5 строк с иконкой-скелетоном и 2 строками текста.

**Pipeline Timeline:** 7 строк (по дням), каждая с 3-4 прямоугольными скелетонами.

**Circuit Breakers:** 6 карточек-скелетонов в grid 3x2.

**Cost Breakdown:** 6 строк с progress-bar скелетонами.

### Empty

**Нет агентов:**
```
[Bot icon]
Нет зарегистрированных агентов
Агенты появятся автоматически при первом запуске пайплайна.
```
Использовать паттерн `ModuleStub` из `@/components/shared/module-stub.tsx`.

**Нет активности сегодня:**
```
Тишина в эфире
Сегодня пока не было запусков агентов.
Следующий запуск: daily_report в 09:00
```

**Нет ошибок:**
В Activity Feed при фильтре "Errors only" -- пустое состояние:
```
Ошибок не обнаружено
За выбранный период все запуски завершились успешно.
```

**Все CB closed:**
Не пустое состояние, но визуально приглушить healthy breakers (opacity-60) и подсветить проблемные (UX Critic P1).

### Error

**API недоступен (весь дашборд):**
```tsx
<div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
  <AlertTriangle className="w-10 h-10 mb-3 text-wk-yellow" />
  <p className="font-medium">Не удалось загрузить данные</p>
  <p className="text-sm mt-1">Сервер агентов недоступен</p>
  <Button variant="outline" size="sm" className="mt-4" onClick={retry}>
    Повторить
  </Button>
</div>
```

**Частичные данные:** Секция, которая не загрузилась, показывает inline-ошибку внутри Card:
```tsx
<CardContent className="py-8 text-center text-muted-foreground">
  <p className="text-sm">Не удалось загрузить Activity Feed</p>
  <Button variant="ghost" size="xs" className="mt-2">Повторить</Button>
</CardContent>
```

**WebSocket отключён (UX Critic P0):** LiveIndicator меняет цвет с green на yellow, текст "LIVE" меняется на "OFFLINE (X сек назад)" с пульсирующей анимацией.

### Transitions & Animations

Использовать существующие токены из `index.css`:
- `--duration-fast: 150ms` -- для hover-эффектов
- `--duration-normal: 200ms` -- для появления данных
- `--duration-slow: 300ms` -- для slide-in панелей
- `--ease-out` -- для всех enter-анимаций

**Обновление данных в реальном времени:**
- Новые элементы feed -- slide-in сверху с `animate-in slide-in-from-top duration-200`
- Изменение числовых значений в summary cards -- `transition-all duration-300` (число плавно обновляется)
- Изменение статуса агента -- badge кратко подсвечивается (`ring-2 ring-wk-blue/50` на 1 сек через CSS animation)
- **Не использовать:** декоративные glow/ambient эффекты из мокапа (UX Critic P2: "каждый пиксель должен нести информацию")

**Stagger-анимация при первой загрузке:**
Карточки появляются последовательно с `--duration-stagger: 50ms` задержкой. Использовать `animate-in fade-in slide-in-from-bottom-2` с `style={{ animationDelay: `${i * 50}ms` }}`.

**`prefers-reduced-motion`:** Уже поддерживается в `index.css` -- все анимации сводятся к 0.01ms.

---

## Responsive Breakpoints

Используем существующие breakpoints из Hub: `sm: 768px`, `md: 1024px`, `lg: 1280px`.

### >= 1280px (lg) -- Desktop

Полный layout как в мокапе:
```
[Summary Cards: 4 колонки]
[Fleet Table (1.5fr) | Activity Feed (1fr)]
[Pipeline Timeline: full-width]
[Circuit Breakers (1fr) | Cost Breakdown (1fr)]
```

### 1024px -- 1279px (md)

Summary cards: 4 колонки (уже/компактнее).
Main grid: `grid-cols-1` -- Fleet Table и Activity Feed стекаются вертикально.
Bottom bar: `grid-cols-1` -- CB и Costs стекаются.
Pipeline Timeline: horizontal scroll если блоки не помещаются.

### 768px -- 1023px (sm)

Summary cards: `grid-cols-2` (2x2 сетка).
Fleet Table: скрыть колонки "Avg" и "Runs", оставить Agent/Status/Errors/Last Run.
Activity Feed: полная ширина, max-height увеличить до 300px.
CB Grid: `grid-cols-2` вместо 3.
Pipeline Timeline: скрыть текстовые лейблы блоков, только цветные точки. Или horizontal scroll.

### < 768px (mobile)

Summary cards: `grid-cols-2`, значения уменьшить шрифт.
Fleet Table: превратить в карточный список (каждый агент -- карточка с основными метриками).
Activity Feed: упрощённый вид без feed-meta.
Pipeline Timeline: **скрыть** (слишком компактный для mobile), показать summary "5 из 7 дней без ошибок".
CB Grid: `grid-cols-1`, вертикальный список.
Cost Breakdown: убрать bar, показать только agent + value + percentage.

**Приоритет отображения на mobile (что показывать первым):**
1. Alert Banner (если есть critical alerts)
2. Summary Cards
3. Agent Fleet (card view)
4. Activity Feed
5. Rest -- за скроллом

---

## Решение P0 проблем (из UX review)

### Drill-down: Sheet panel approach

**Решение:** Использовать существующий `Sheet` компонент (`@/components/ui/sheet.tsx`) для drill-down. Это консистентно с `ModelDetailDrawer` на DashboardPage.

**Клик на строку агента --> Sheet справа (480px):**
```
[Sheet: Agent Detail]
  Header: Avatar + Name + Status badge + "Открыть страницу" link
  Section 1: Key metrics (runs, errors, avg time, cost today)
  Section 2: Last 10 activity events (mini-feed)
  Section 3: Circuit Breaker state
  Section 4: Configuration (tier, retry policy, schedule)
  Footer: "Force Run" button, "Reset CB" button (if open)
```

**Клик на pipeline block --> Sheet справа:**
```
[Sheet: Pipeline Run Detail]
  Header: Pipeline name + date + status badge
  Section 1: Duration, cost, model tier used
  Section 2: Step-by-step log (input -> gate check -> generation -> validation -> publish)
  Section 3: Error details (if failed) + stack trace
  Section 4: Output preview (link to Notion/Telegram)
```

**Клик на feed item --> Sheet справа:**
```
[Sheet: Event Detail]
  Full log output, input/output payloads, timing breakdown
```

URL не меняется при открытии Sheet (state через `useState`, не через router). Это позволяет быстро закрыть и вернуться.

Для полной страницы агента -- отдельный route `/system/agents/:name` (см. Page Hierarchy).

### Time range picker

**Расположение:** В правой части header-а страницы (рядом с LiveIndicator).

**Реализация:** Расширить существующий `DateRangePicker` из `@/components/shared/date-range-picker.tsx` или создать компактный `TimeRangePicker`:

```
[1ч] [6ч] [24ч] [7д] [30д] [Custom...]
```

- Визуально: `TabsList variant="line"` с 5-6 пресетами
- Custom: открывает popover с DatePicker
- Выбранный диапазон применяется ко ВСЕМ секциям дашборда (единый state)
- URL-параметр: `?range=24h` для sharable links

### Alert banner

**Расположение:** Над summary cards, sticky при скролле (но ниже TopBar).

```tsx
<div className="bg-wk-red/10 border border-wk-red/20 rounded-lg px-4 py-3 flex items-center gap-3">
  <AlertTriangle className="w-5 h-5 text-wk-red shrink-0" />
  <div className="flex-1 min-w-0">
    <p className="text-sm font-medium">Revenue WB -22% vs avg</p>
    <p className="text-xs text-muted-foreground">Обнаружено в 09:10 -- требуется расследование</p>
  </div>
  <Button variant="destructive" size="sm" onClick={investigate}>
    Расследовать
  </Button>
  <Button variant="ghost" size="icon-sm" onClick={dismiss}>
    <X className="w-4 h-4" />
  </Button>
</div>
```

- Множественные алерты: стекать вертикально, max 3 видимых + "ещё N"
- Звуковой сигнал: не реализовывать в MVP (может раздражать)
- Toast для real-time: использовать `sonner` (уже стандартная практика в shadcn)

### Auto-refresh indicator

**Расположение:** Рядом с заголовком страницы или в правом углу TopBar.

**Компонент `LiveIndicator`:**

Два состояния:
1. **Connected:** Зелёная пульсирующая точка + "LIVE" + "обновлено Xs назад"
2. **Disconnected:** Жёлтая точка (не пульсирует) + "OFFLINE" + "данные от HH:MM"

```tsx
<div className="flex items-center gap-2 text-xs">
  <span className={cn(
    "w-1.5 h-1.5 rounded-full",
    isConnected ? "bg-wk-green animate-pulse" : "bg-wk-yellow"
  )} />
  <span className={cn(
    "font-medium uppercase tracking-wider",
    isConnected ? "text-wk-green" : "text-wk-yellow"
  )}>
    {isConnected ? "Live" : "Offline"}
  </span>
  <span className="text-muted-foreground">
    {isConnected ? `${secondsAgo}с назад` : `данные от ${lastUpdate}`}
  </span>
</div>
```

**Refresh strategy:**
- Polling каждые 30 сек (не WebSocket для MVP -- проще и надёжнее)
- Если 3 consecutive failures -- переключить на "Offline"
- Manual refresh button (RefreshCw icon) всегда доступен

---

## Page Hierarchy

### `/system/agents` -- Overview (текущий мокап)

Основная страница. Заменяет stub `AgentsPage`.

**Layout:**
```tsx
export function AgentsOverviewPage() {
  return (
    <div className="space-y-4">
      <AgentsHeader />        {/* Title + TimeRangePicker + LiveIndicator */}
      <AlertBanner />          {/* P0: critical alerts, если есть */}
      <SummaryCards />         {/* 4 metric cards */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4">
        <AgentFleetTable />
        <ActivityFeed />
      </div>
      <PipelineTimeline />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CircuitBreakerGrid />
        <CostBreakdown />
      </div>
      {/* Sheet panels (conditional) */}
      <AgentDetailSheet />
      <PipelineDetailSheet />
    </div>
  )
}
```

**Route:** `/system/agents` (заменить stub).

### `/system/agents/:name` -- Agent Detail Page

Полноценная страница для одного агента. Переход: клик "Открыть страницу" из Sheet или прямой URL.

**Секции:**
1. **Header:** Breadcrumb (Агенты > Reporter) + status + действия (Force Run, Pause, Reset CB)
2. **Metrics row:** Runs today, Errors, Avg time, Cost, Success rate -- всё за выбранный период
3. **Activity log:** Полный лог этого агента (с фильтрами по типу и поиском)
4. **Pipeline history:** Все запуски этого агента в timeline
5. **Configuration:** Tier, retry policy, schedule, CB settings
6. **Cost history:** График расходов этого агента за 30 дней

**Route:** `/system/agents/:name`

### `/system/agents/pipelines` -- Pipeline History

Расширенная версия Pipeline Timeline с фильтрами.

**Отличия от Overview:**
- Полный heatmap (30 дней вместо 7)
- Фильтр по pipeline name
- Фильтр по статусу
- Клик на ячейку --> Sheet с деталями запуска
- Таблица всех запусков с пагинацией (паттерн как в `AuditLogPage`)

**Route:** `/system/agents/pipelines`

### `/system/agents/logs` -- Full Logs

Полная лента активности всех агентов с расширенными фильтрами.

**Фильтры:**
- По агенту (multi-select, использовать `MultiSelectFilter` из `@/components/shared/multi-select-filter.tsx`)
- По типу (success / error / warning / retry)
- По дате (DateRangePicker)
- Текстовый поиск

**Формат:** Таблица с колонками: Time | Agent | Task | Status | Duration | Cost | Details (expand).

**Route:** `/system/agents/logs`

### Навигация между страницами

Обновить `navigation.ts` -- навигация уже содержит `{ id: "agents", label: "Агенты", icon: Bot, path: "/system/agents" }`. Подстраницы доступны через:
- Breadcrumbs внутри страниц
- Tabs в header-е overview page: `[Обзор] [Пайплайны] [Логи]` (используя `TabsList variant="line"`)
- Прямые ссылки из других секций (клик "View All" в Activity Feed --> `/system/agents/logs`)

**Обновление router.tsx:**
```tsx
// System -- Agents
{ path: "/system/agents", element: <AgentsOverviewPage /> },
{ path: "/system/agents/pipelines", element: <AgentsPipelinesPage /> },
{ path: "/system/agents/logs", element: <AgentsLogsPage /> },
{ path: "/system/agents/:name", element: <AgentDetailPage /> },
```

---

## Дополнительные рекомендации

### Языковая консистентность (UX Critic P1)

Перевести все заголовки на русский:
- "Agent Fleet" --> "Агенты"
- "Live Activity" --> "Активность"
- "Pipeline Timeline" --> "Пайплайны"
- "Circuit Breakers" --> "Автоматы защиты"
- "Cost Breakdown" --> "Расходы"
- "Running" / "Idle" / "CB Open" -- оставить на английском (технические термины, понятные оператору)
- "Success" / "Failed" / "Degraded" / "Skipped" -- оставить на английском

### Accessibility (UX Critic P2)

Включить в первую итерацию (не откладывать):
- `aria-label` на все status badges
- `role="button"` + `tabIndex={0}` + `onKeyDown` для кликабельных строк таблицы
- Contrast fix: `--text-dim` в dark mode поднять lightness с 0.450 до 0.500 (для AA compliance)
- Focus-visible стили уже включены в shadcn компоненты -- убедиться что custom элементы их наследуют
- `aria-live="polite"` на Activity Feed container для screen reader обновлений

### CSS cleanup из мокапа

**Убрать полностью:**
- `body::before` (noise texture) -- GPU overhead, нулевая информационная ценность
- `body::after` (ambient glow) -- декоративный элемент
- `@keyframes pulse-green/pulse-blue` -- заменить на Tailwind `animate-pulse`
- Custom sidebar -- в Hub sidebar обрабатывается `IconBar` + `SubSidebar`

### Файловая структура

```
src/components/agents/
  agent-metric-card.tsx
  agent-fleet-table.tsx
  activity-feed.tsx
  pipeline-timeline.tsx
  circuit-breaker-grid.tsx
  cost-breakdown.tsx
  live-indicator.tsx
  alert-banner.tsx
  time-range-picker.tsx
  agent-detail-sheet.tsx
  pipeline-detail-sheet.tsx

src/pages/
  agents/
    agents-overview.tsx       # заменяет stubs/agents.tsx
    agents-pipelines.tsx
    agents-logs.tsx
    agent-detail.tsx
```
