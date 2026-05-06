# Wookiee Hub — Phase 2 (История запусков) + Phase 3 (Примеры)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Реализовать страницу "История запусков" с данными из `agent_runs` и добавить поля примеров использования в карточки инструментов.

**Spec:** `docs/superpowers/specs/2026-05-04-wookiee-hub-operations-design.md`
**Deployment:** `hub.os.wookiee.shop` (rsync dist/, Node.js нет на сервере)
**Supabase project:** `gjvwcdtfglupewcwzfhw`

---

## Контекст

### Что уже есть (Phase 1 — DONE)
- `wookiee-hub/src/pages/operations/activity.tsx` — STUB, нужно реализовать
- `wookiee-hub/src/components/operations/tool-detail-panel.tsx` — показывает детали инструмента, нужно добавить секцию запусков
- `wookiee-hub/src/lib/tools-service.ts` — fetchTools() фильтрует show_in_hub=true
- Таблица `public.tool_runs` — создана (014 миграция), пустая
- Таблица `public.agent_runs` — 650+ записей, реальные данные

### Схема agent_runs
```sql
id uuid, run_id uuid, parent_run_id uuid,
agent_name text,        -- "margin-analyst", "ad-efficiency", "report-compiler" и т.д.
agent_type text, agent_version text,
status text,            -- 'success' | 'error' | 'timeout'
started_at timestamptz, finished_at timestamptz, duration_ms int,
error_message text,
model text, prompt_tokens int, completion_tokens int, cost_usd numeric,
llm_calls int, tool_calls int, user_input text
```

### Маппинг agent_name → tool slug
Нужно построить маппинг. Известные соответствия:
- "margin-analyst", "ad-efficiency", "revenue-decomposer", "report-compiler" → `/analytics-report` (мета-оркестратор)
- "crm-sheets-etl" → `sheets-sync`
- Остальные — по совпадению agent_name с tools.slug или display_name

---

## Phase 2 — История запусков

### Task 1: RLS для agent_runs
**Цель:** Дать authenticated users право читать agent_runs.

```sql
-- Применить через Supabase MCP apply_migration
alter table public.agent_runs enable row level security;

do $$ begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'agent_runs' and policyname = 'authenticated read agent_runs'
  ) then
    execute 'create policy "authenticated read agent_runs" on public.agent_runs
      for select using (auth.role() = ''authenticated'')';
  end if;
end $$;
```

### Task 2: activity-service.ts
Новый файл `wookiee-hub/src/lib/activity-service.ts`:

```typescript
// Получить последние N запусков (для страницы)
fetchRuns(limit: number, offset: number, filters: RunFilters): Promise<AgentRun[]>

// Получить последние запуски по agent_name (для ToolDetailPanel)
fetchRunsByAgent(agentName: string, limit: number): Promise<AgentRun[]>
```

Тип `AgentRun`:
```typescript
interface AgentRun {
  id: string
  agentName: string
  status: 'success' | 'error' | 'timeout'
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  errorMessage: string | null
  costUsd: number | null
  model: string | null
}

interface RunFilters {
  status?: string
  agentName?: string
  dateFrom?: string
  dateTo?: string
}
```

### Task 3: ActivityPage
Файл `wookiee-hub/src/pages/operations/activity.tsx`:

**Структура:**
- Заголовок "История запусков" + subtitle
- Строка фильтров: статус (все / успех / ошибка / таймаут), инструмент (select), дата-пикер
- Таблица запусков:
  - Иконка статуса (зелёная ✓ / красная ✗ / жёлтая ⏱)
  - Название инструмента (из маппинга agent_name)
  - Время запуска (относительное: "3 мин назад", "2 дня назад")
  - Длительность (секунды)
  - Стоимость (если > 0)
- При клике на строку — раскрывающаяся панель с error_message, model, tokens
- Пагинация (по 50 записей)
- Пустое состояние: "Запусков пока нет"

**Маппинг для отображения имён:**
```typescript
const AGENT_NAME_MAP: Record<string, string> = {
  'margin-analyst': 'Финансовый P&L отчёт',
  'ad-efficiency': 'Маркетинговый отчёт',
  'revenue-decomposer': 'Сводный аналитический отчёт',
  'report-compiler': 'Сводный аналитический отчёт',
  'crm-sheets-etl': 'ETL: WB/OZON/МойСклад → Google Sheets',
  // остальные — agent_name как есть
}
```

### Task 4: Секция запусков в ToolDetailPanel
В `wookiee-hub/src/components/operations/tool-detail-panel.tsx`:

Добавить под секцией "Статистика запусков" новый блок "Последние запуски":
- Показывает 5 последних запусков из agent_runs где agent_name соответствует инструменту
- Каждая строка: статус + время + длительность
- Если error — показывать первые 100 символов error_message
- "Детальная история → История запусков" (ссылка на /operations/activity)
- Загружается лениво при открытии панели

---

## Phase 3 — Примеры использования

### Task 5: Миграция usage_examples + doc_url
```sql
alter table public.tools
  add column if not exists usage_examples text,
  add column if not exists doc_url        text;
```

### Task 6: Обогащение агентом
Запустить general-purpose агента:
- Читает docs/skills/*.md для каждого инструмента
- Заполняет `usage_examples`: 2-3 конкретных примера в формате
  "→ Запрос: [что написать] → Результат: [что получишь]"
- Заполняет `doc_url` если есть ссылка на Notion/Sheets в docs
- Обновляет через Supabase REST API

### Task 7: Отображение в ToolDetailPanel
В детальной панели добавить секцию "Примеры использования":
- Показывается только если `usage_examples` не пустое
- Отображение: нумерованный список примеров
- Если `doc_url` есть — кнопка "Смотреть пример отчёта →" (внешняя ссылка)

---

## Deploy checklist
- [ ] Применить RLS миграцию через Supabase MCP
- [ ] Применить миграцию usage_examples + doc_url
- [ ] npm run build в wookiee-hub/
- [ ] rsync dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/
- [ ] Проверить https://hub.os.wookiee.shop/operations/activity
