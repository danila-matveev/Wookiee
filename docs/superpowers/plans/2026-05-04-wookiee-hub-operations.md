# Wookiee Hub — Operations Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить раздел Operations в существующий wookiee-hub: авторизация (Supabase Auth), каталог всех 47 тулзов с детальными панелями, просмотр документации скиллов.

**Architecture:** Supabase Auth (email+password, persistSession) + ProtectedRoute на весь хаб. Каталог читает из таблицы `tools` напрямую через Supabase JS-клиент. Детальная панель — slide-in компонент, для скиллов fetch-ит `/skills/<slug>.md` из public/. Существующий Community раздел не трогаем.

**Tech Stack:** React 19, TypeScript, Tailwind v4, Radix UI, Zustand 5, Supabase JS v2, Vitest + @testing-library/react, React Router v7.

---

## Файловая карта

### Новые файлы
```
wookiee-hub/src/
├── types/tool.ts                              ← расширенный тип OperationsTool
├── lib/tools-service.ts                       ← Supabase queries + display_name→name маппинг
├── stores/operations.ts                       ← Zustand: tools, фильтр, выбранный тулз
├── pages/auth/login.tsx                       ← страница /login
├── components/auth/protected-route.tsx        ← guard redirect → /login
├── pages/operations/tools.tsx                 ← каталог (главная страница)
├── pages/operations/activity.tsx              ← заглушка Activity Feed
├── components/operations/tool-card.tsx        ← карточка тулза
├── components/operations/tool-filters.tsx     ← фильтры категорий + поиск
├── components/operations/tool-skill-viewer.tsx ← markdown viewer для .md файлов
└── components/operations/tool-detail-panel.tsx ← правая панель при клике
wookiee-hub/public/skills/                     ← копии docs/skills/*.md
database/migrations/014_operations_hub.sql     ← 4 новых поля + tool_runs + RLS
scripts/populate_tools_name_ru.py              ← заполнение name_ru в Supabase
```

### Изменяемые файлы
```
wookiee-hub/src/lib/supabase.ts               ← persistSession: true, autoRefreshToken: true
wookiee-hub/src/config/navigation.ts          ← agents → operations (3 пункта)
wookiee-hub/src/router.tsx                    ← /login + /operations/*, убрать /agents/*
wookiee-hub/src/components/layout/user-menu.tsx ← wire logout supabase.auth.signOut()
```

---

## Task 1: DB Migration

**Files:**
- Create: `database/migrations/014_operations_hub.sql`

- [ ] **Написать SQL миграцию**

```sql
-- database/migrations/014_operations_hub.sql
-- Добавляем поля к таблице tools
alter table public.tools
  add column if not exists name_ru             text,
  add column if not exists health_check        text,
  add column if not exists output_description  text,
  add column if not exists skill_md_path       text,
  add column if not exists required_env_vars   text[] default '{}';

-- Таблица истории запусков (Phase 2 — создаём сейчас, заполним позже)
create table if not exists public.tool_runs (
  id            uuid primary key default gen_random_uuid(),
  tool_slug     text not null references public.tools(slug) on delete cascade,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  status        text not null check (status in ('running', 'success', 'error')),
  triggered_by  text,
  output_summary text,
  error_message  text,
  duration_ms   int
);

create index if not exists tool_runs_slug_started
  on public.tool_runs(tool_slug, started_at desc);

-- RLS для tool_runs
alter table public.tool_runs enable row level security;

create policy if not exists "authenticated read tool_runs"
  on public.tool_runs for select
  using (auth.role() = 'authenticated');

-- RLS для tools (таблица уже существует с политиками — добавляем если нет)
do $$
begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'tools' and policyname = 'authenticated read tools'
  ) then
    execute 'create policy "authenticated read tools" on public.tools for select using (auth.role() = ''authenticated'')';
  end if;
end $$;
```

- [ ] **Применить миграцию через Supabase Dashboard**

Открыть: Supabase Dashboard → SQL Editor → вставить содержимое файла → Run.

Проверить успех:
```sql
select column_name from information_schema.columns
where table_name = 'tools' and column_name in ('name_ru', 'health_check', 'skill_md_path');
-- должно вернуть 3 строки
```

- [ ] **Commit**

```bash
git add database/migrations/014_operations_hub.sql
git commit -m "feat(db): add operations hub migration - tool fields + tool_runs table"
```

---

## Task 2: Populate name_ru

**Files:**
- Create: `scripts/populate_tools_name_ru.py`

- [ ] **Написать скрипт**

```python
# scripts/populate_tools_name_ru.py
"""Заполняет поле name_ru в таблице tools на основе TOOLS_CATALOG.md.

Запуск: python scripts/populate_tools_name_ru.py
"""
from __future__ import annotations

import re
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv('database/sku/.env')

CATALOG_PATH = Path(__file__).parent.parent / 'docs' / 'TOOLS_CATALOG.md'

# Маппинг slug → русское название
# Берём из заголовков каталога: ### ✅ `slug` — Русское название
def parse_catalog(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    pattern = re.compile(r'###\s+\S+\s+`([^`]+)`\s+[—–]\s+(.+)')
    for match in pattern.finditer(text):
        slug, name_ru = match.group(1).strip(), match.group(2).strip()
        # Убираем суффикс версии типа ` v2` или ` 2.0.0`
        name_ru = re.sub(r'\s+`[\d.]+`$', '', name_ru)
        mapping[slug] = name_ru
    return mapping


def main() -> None:
    catalog_text = CATALOG_PATH.read_text(encoding='utf-8')
    mapping = parse_catalog(catalog_text)
    print(f'Найдено {len(mapping)} тулзов в каталоге')

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'postgres'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
    )
    try:
        cur = conn.cursor()
        updated = 0
        for slug, name_ru in mapping.items():
            cur.execute(
                'update tools set name_ru = %s where slug = %s and name_ru is null',
                (name_ru, slug)
            )
            updated += cur.rowcount
        conn.commit()
        print(f'Обновлено: {updated} строк')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
```

- [ ] **Запустить скрипт**

```bash
cd /Users/danilamatveev/Projects/Wookiee
python scripts/populate_tools_name_ru.py
# Ожидаем: Найдено N тулзов в каталоге / Обновлено: N строк
```

- [ ] **Проверить в Supabase**

```sql
select slug, name_ru from tools where name_ru is not null limit 5;
-- должно вернуть строки с русскими названиями
select count(*) from tools where name_ru is null;
-- желательно 0
```

- [ ] **Commit**

```bash
git add scripts/populate_tools_name_ru.py
git commit -m "feat(scripts): add populate_tools_name_ru from TOOLS_CATALOG.md"
```

---

## Task 3: Скопировать .md файлы скиллов в public/

**Files:**
- Create: `wookiee-hub/public/skills/` (папка + файлы)

- [ ] **Скопировать файлы**

```bash
mkdir -p wookiee-hub/public/skills
cp docs/skills/*.md wookiee-hub/public/skills/
ls wookiee-hub/public/skills/
# должно быть ~19 файлов: finance-report.md, marketing-report.md, ...
```

- [ ] **Проверить доступность через dev-сервер**

```bash
cd wookiee-hub && npm run dev &
# Открыть http://localhost:5173/skills/finance-report.md
# Должен вернуть markdown текст, не 404
kill %1
```

- [ ] **Commit**

```bash
git add wookiee-hub/public/skills/
git commit -m "feat(hub): add skill .md docs to public/skills for in-app viewer"
```

---

## Task 4: Расширенный тип OperationsTool

**Files:**
- Create: `wookiee-hub/src/types/tool.ts`

- [ ] **Написать тип**

```typescript
// wookiee-hub/src/types/tool.ts
// Расширенный тип тулза из таблицы Supabase `tools`.
// display_name маппится на name в tools-service.ts для совместимости.

export type ToolType = 'skill' | 'service' | 'script' | 'cron'
export type ToolStatus = 'active' | 'deprecated' | 'draft' | 'archived'
export type ToolCategory =
  | 'analytics'
  | 'content'
  | 'publishing'
  | 'infra'
  | 'planning'
  | 'team'

export interface OperationsTool {
  slug: string
  name: string           // mapped from display_name
  nameRu: string | null  // mapped from name_ru
  type: ToolType
  category: ToolCategory
  status: ToolStatus
  version: string | null
  description: string | null
  howItWorks: string | null     // mapped from how_it_works
  runCommand: string | null     // mapped from run_command
  dataSources: string[]         // mapped from data_sources
  dependsOn: string[]           // mapped from depends_on
  outputTargets: string[]       // mapped from output_targets
  outputDescription: string | null // mapped from output_description
  healthCheck: string | null    // mapped from health_check
  skillMdPath: string | null    // mapped from skill_md_path
  requiredEnvVars: string[]     // mapped from required_env_vars (API keys this tool needs)
  totalRuns: number
  lastRunAt: string | null      // mapped from last_run_at (ISO string)
  lastStatus: string | null     // mapped from last_status
}

export type ToolCategoryFilter = ToolCategory | 'all'
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/types/tool.ts
git commit -m "feat(hub): add OperationsTool type with full Supabase field mapping"
```

---

## Task 5: Fix supabase.ts + Tools Service

**Files:**
- Modify: `wookiee-hub/src/lib/supabase.ts`
- Create: `wookiee-hub/src/lib/tools-service.ts`
- Test: `wookiee-hub/src/lib/tools-service.test.ts`

- [ ] **Написать тест для tools-service**

```typescript
// wookiee-hub/src/lib/tools-service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock supabase BEFORE importing tools-service
vi.mock('@/lib/supabase', () => ({
  supabase: {
    from: vi.fn(),
  },
}))

import { fetchTools } from '@/lib/tools-service'
import { supabase } from '@/lib/supabase'

const mockRow = {
  slug: 'finance-report',
  display_name: 'finance-report',
  name_ru: 'Финансовый отчёт P&L',
  type: 'skill',
  category: 'analytics',
  status: 'active',
  version: 'v4',
  description: 'Недельный P&L отчёт',
  how_it_works: 'Шаг 1. Загрузка данных',
  run_command: '/finance-report',
  data_sources: ['supabase'],
  depends_on: ['notion'],
  output_targets: ['notion', 'telegram'],
  output_description: 'Notion страница',
  health_check: null,
  skill_md_path: 'finance-report.md',
  required_env_vars: ['OPENROUTER_API_KEY', 'SUPABASE_URL'],
  total_runs: 42,
  last_run_at: '2026-05-04T09:15:00Z',
  last_status: 'success',
}

describe('fetchTools', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('maps display_name to name', async () => {
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        neq: vi.fn().mockResolvedValue({ data: [mockRow], error: null }),
      }),
    } as any)

    const tools = await fetchTools()
    expect(tools[0].name).toBe('finance-report')
    expect(tools[0].nameRu).toBe('Финансовый отчёт P&L')
  })

  it('returns empty array on null data', async () => {
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        neq: vi.fn().mockResolvedValue({ data: null, error: { message: 'fail' } }),
      }),
    } as any)

    const tools = await fetchTools()
    expect(tools).toEqual([])
  })

  it('maps null arrays to empty arrays', async () => {
    const rowWithNulls = { ...mockRow, data_sources: null, depends_on: null, output_targets: null }
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        neq: vi.fn().mockResolvedValue({ data: [rowWithNulls], error: null }),
      }),
    } as any)

    const tools = await fetchTools()
    expect(tools[0].dataSources).toEqual([])
    expect(tools[0].dependsOn).toEqual([])
  })
})
```

- [ ] **Запустить тест — убедиться что падает**

```bash
cd wookiee-hub && npx vitest run src/lib/tools-service.test.ts
# Expected: FAIL — fetchTools not found
```

- [ ] **Исправить supabase.ts**

```typescript
// wookiee-hub/src/lib/supabase.ts
import { createClient } from "@supabase/supabase-js"

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? ""
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ""

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
})
```

- [ ] **Написать tools-service.ts**

```typescript
// wookiee-hub/src/lib/tools-service.ts
import { supabase } from '@/lib/supabase'
import type { OperationsTool } from '@/types/tool'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapRow(row: any): OperationsTool {
  return {
    slug: row.slug,
    name: row.display_name,
    nameRu: row.name_ru ?? null,
    type: row.type,
    category: row.category,
    status: row.status,
    version: row.version ?? null,
    description: row.description ?? null,
    howItWorks: row.how_it_works ?? null,
    runCommand: row.run_command ?? null,
    dataSources: row.data_sources ?? [],
    dependsOn: row.depends_on ?? [],
    outputTargets: row.output_targets ?? [],
    outputDescription: row.output_description ?? null,
    healthCheck: row.health_check ?? null,
    skillMdPath: row.skill_md_path ?? null,
    requiredEnvVars: row.required_env_vars ?? [],
    totalRuns: row.total_runs ?? 0,
    lastRunAt: row.last_run_at ?? null,
    lastStatus: row.last_status ?? null,
  }
}

export async function fetchTools(): Promise<OperationsTool[]> {
  const { data, error } = await supabase
    .from('tools')
    .select(
      'slug, display_name, name_ru, type, category, status, version, ' +
      'description, how_it_works, run_command, data_sources, depends_on, ' +
      'output_targets, output_description, health_check, skill_md_path, ' +
      'required_env_vars, total_runs, last_run_at, last_status'
    )
    .neq('status', 'archived')

  if (error || !data) {
    console.error('[tools-service] fetchTools error:', error?.message)
    return []
  }

  return data.map(mapRow)
}
```

- [ ] **Запустить тест — убедиться что проходит**

```bash
cd wookiee-hub && npx vitest run src/lib/tools-service.test.ts
# Expected: PASS (3 tests)
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/lib/supabase.ts wookiee-hub/src/lib/tools-service.ts wookiee-hub/src/lib/tools-service.test.ts
git commit -m "feat(hub): fix supabase auth config + add tools-service with field mapping"
```

---

## Task 6: Operations Zustand Store

**Files:**
- Create: `wookiee-hub/src/stores/operations.ts`
- Test: `wookiee-hub/src/stores/operations.test.ts`

- [ ] **Написать тест**

```typescript
// wookiee-hub/src/stores/operations.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useOperationsStore, filterTools } from '@/stores/operations'
import type { OperationsTool } from '@/types/tool'

const makeTool = (overrides: Partial<OperationsTool>): OperationsTool => ({
  slug: 'test-tool',
  name: 'test-tool',
  nameRu: 'Тестовый тулз',
  type: 'skill',
  category: 'analytics',
  status: 'active',
  version: 'v1',
  description: 'Описание',
  howItWorks: null,
  runCommand: null,
  dataSources: [],
  dependsOn: [],
  outputTargets: [],
  outputDescription: null,
  healthCheck: null,
  skillMdPath: null,
  requiredEnvVars: [],
  totalRuns: 0,
  lastRunAt: null,
  lastStatus: null,
  ...overrides,
})

const tools = [
  makeTool({ slug: 'finance', category: 'analytics', name: 'finance-report' }),
  makeTool({ slug: 'sheets', category: 'infra', name: 'sheets-sync' }),
  makeTool({ slug: 'hygiene', category: 'infra', name: 'hygiene', status: 'active' }),
]

describe('filterTools', () => {
  it('returns all tools when category is "all" and query empty', () => {
    expect(filterTools(tools, 'all', '')).toHaveLength(3)
  })

  it('filters by category', () => {
    const result = filterTools(tools, 'infra', '')
    expect(result).toHaveLength(2)
    expect(result.every(t => t.category === 'infra')).toBe(true)
  })

  it('filters by search query on name', () => {
    const result = filterTools(tools, 'all', 'finance')
    expect(result).toHaveLength(1)
    expect(result[0].slug).toBe('finance')
  })

  it('search is case-insensitive', () => {
    const result = filterTools(tools, 'all', 'HYGIENE')
    expect(result).toHaveLength(1)
  })
})
```

- [ ] **Запустить тест — убедиться что падает**

```bash
cd wookiee-hub && npx vitest run src/stores/operations.test.ts
# Expected: FAIL
```

- [ ] **Написать store**

```typescript
// wookiee-hub/src/stores/operations.ts
import { create } from 'zustand'
import type { OperationsTool, ToolCategoryFilter } from '@/types/tool'

interface OperationsState {
  tools: OperationsTool[]
  loading: boolean
  categoryFilter: ToolCategoryFilter
  searchQuery: string
  selectedTool: OperationsTool | null
  setTools: (tools: OperationsTool[]) => void
  setLoading: (loading: boolean) => void
  setCategoryFilter: (category: ToolCategoryFilter) => void
  setSearchQuery: (query: string) => void
  setSelectedTool: (tool: OperationsTool | null) => void
}

export const useOperationsStore = create<OperationsState>((set) => ({
  tools: [],
  loading: false,
  categoryFilter: 'all',
  searchQuery: '',
  selectedTool: null,
  setTools: (tools) => set({ tools }),
  setLoading: (loading) => set({ loading }),
  setCategoryFilter: (categoryFilter) => set({ categoryFilter }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSelectedTool: (selectedTool) => set({ selectedTool }),
}))

export function filterTools(
  tools: OperationsTool[],
  category: ToolCategoryFilter,
  query: string
): OperationsTool[] {
  const q = query.toLowerCase().trim()
  return tools.filter((tool) => {
    const matchesCategory = category === 'all' || tool.category === category
    const matchesQuery =
      q === '' ||
      tool.name.toLowerCase().includes(q) ||
      (tool.nameRu ?? '').toLowerCase().includes(q) ||
      (tool.description ?? '').toLowerCase().includes(q)
    return matchesCategory && matchesQuery
  })
}
```

- [ ] **Запустить тест — убедиться что проходит**

```bash
cd wookiee-hub && npx vitest run src/stores/operations.test.ts
# Expected: PASS (4 tests)
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/stores/operations.ts wookiee-hub/src/stores/operations.test.ts
git commit -m "feat(hub): add operations Zustand store with filterTools logic"
```

---

## Task 7: Login Page + ProtectedRoute

**Files:**
- Create: `wookiee-hub/src/pages/auth/login.tsx`
- Create: `wookiee-hub/src/components/auth/protected-route.tsx`
- Test: `wookiee-hub/src/pages/auth/login.test.tsx`

- [ ] **Написать тест**

```typescript
// wookiee-hub/src/pages/auth/login.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
    },
  },
}))

// react-router-dom navigate mock
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

import { LoginPage } from '@/pages/auth/login'
import { supabase } from '@/lib/supabase'

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders email and password inputs', () => {
    renderLogin()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/пароль/i)).toBeInTheDocument()
  })

  it('does not render a signup link', () => {
    renderLogin()
    expect(screen.queryByText(/зарегистрироваться/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument()
  })

  it('calls signInWithPassword on submit', async () => {
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      data: { user: { id: '1' }, session: {} },
      error: null,
    } as any)

    renderLogin()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText(/пароль/i), { target: { value: 'pass' } })
    fireEvent.click(screen.getByRole('button', { name: /войти/i }))

    await waitFor(() => {
      expect(supabase.auth.signInWithPassword).toHaveBeenCalledWith({
        email: 'a@b.com',
        password: 'pass',
      })
    })
  })

  it('shows error message on failed login', async () => {
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      data: { user: null, session: null },
      error: { message: 'Invalid credentials' },
    } as any)

    renderLogin()
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'bad@b.com' } })
    fireEvent.change(screen.getByLabelText(/пароль/i), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: /войти/i }))

    await waitFor(() => {
      expect(screen.getByText(/неверный логин или пароль/i)).toBeInTheDocument()
    })
  })
})
```

- [ ] **Запустить тест — убедиться что падает**

```bash
cd wookiee-hub && npx vitest run src/pages/auth/login.test.tsx
# Expected: FAIL — LoginPage not found
```

- [ ] **Написать LoginPage**

```typescript
// wookiee-hub/src/pages/auth/login.tsx
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const { error: authError } = await supabase.auth.signInWithPassword({ email, password })

    setLoading(false)
    if (authError) {
      setError('Неверный логин или пароль')
      return
    }
    navigate('/operations/tools')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-foreground">Wookiee Hub</h1>
          <p className="text-sm text-muted-foreground mt-1">Войдите в рабочее пространство</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-card border border-border rounded-xl p-6 space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium text-foreground">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="you@wookiee.shop"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium text-foreground">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'Вхожу...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Написать ProtectedRoute**

```typescript
// wookiee-hub/src/components/auth/protected-route.tsx
import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const [status, setStatus] = useState<'loading' | 'auth' | 'unauth'>('loading')

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setStatus(data.session ? 'auth' : 'unauth')
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setStatus(session ? 'auth' : 'unauth')
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  if (status === 'loading') return null
  if (status === 'unauth') return <Navigate to="/login" replace />
  return <>{children}</>
}
```

- [ ] **Запустить тест — убедиться что проходит**

```bash
cd wookiee-hub && npx vitest run src/pages/auth/login.test.tsx
# Expected: PASS (4 tests)
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/pages/auth/ wookiee-hub/src/components/auth/ wookiee-hub/src/pages/auth/login.test.tsx
git commit -m "feat(hub): add LoginPage + ProtectedRoute with Supabase Auth"
```

---

## Task 8: Logout в UserMenu

**Files:**
- Modify: `wookiee-hub/src/components/layout/user-menu.tsx`

- [ ] **Добавить logout в UserMenu**

```typescript
// wookiee-hub/src/components/layout/user-menu.tsx
import { useNavigate } from 'react-router-dom'
import { User, Settings, LogOut } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'

function UserMenu() {
  const navigate = useNavigate()

  async function handleLogout() {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        data-slot="user-menu-trigger"
        className="flex items-center justify-center w-8 h-8 rounded-full bg-accent-soft text-accent text-[11px] font-semibold shrink-0 cursor-pointer select-none hover:opacity-80 transition-opacity"
      >
        ДМ
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" sideOffset={8} align="end">
        <DropdownMenuItem>
          <User size={14} />
          Профиль
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Settings size={14} />
          Настройки
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onSelect={handleLogout}>
          <LogOut size={14} />
          Выход
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { UserMenu }
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/components/layout/user-menu.tsx
git commit -m "feat(hub): wire logout in UserMenu via supabase.auth.signOut"
```

---

## Task 9: ToolCard Component

**Files:**
- Create: `wookiee-hub/src/components/operations/tool-card.tsx`
- Test: `wookiee-hub/src/components/operations/tool-card.test.tsx`

- [ ] **Написать тест**

```typescript
// wookiee-hub/src/components/operations/tool-card.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ToolCard } from '@/components/operations/tool-card'
import type { OperationsTool } from '@/types/tool'

const tool: OperationsTool = {
  slug: 'finance-report',
  name: 'finance-report',
  nameRu: 'Финансовый отчёт',
  type: 'skill',
  category: 'analytics',
  status: 'active',
  version: 'v4',
  description: 'Формирует P&L отчёт',
  howItWorks: null,
  runCommand: '/finance-report',
  dataSources: [],
  dependsOn: [],
  outputTargets: [],
  outputDescription: null,
  healthCheck: null,
  skillMdPath: 'finance-report.md',
  requiredEnvVars: ['OPENROUTER_API_KEY'],
  totalRuns: 5,
  lastRunAt: '2026-05-04T09:00:00Z',
  lastStatus: 'success',
}

describe('ToolCard', () => {
  it('renders tool name', () => {
    render(<ToolCard tool={tool} onSelect={vi.fn()} />)
    expect(screen.getByText('finance-report')).toBeInTheDocument()
  })

  it('renders Russian name when present', () => {
    render(<ToolCard tool={tool} onSelect={vi.fn()} />)
    expect(screen.getByText('Финансовый отчёт')).toBeInTheDocument()
  })

  it('does not render Russian name when null', () => {
    render(<ToolCard tool={{ ...tool, nameRu: null }} onSelect={vi.fn()} />)
    expect(screen.queryByText('Финансовый отчёт')).not.toBeInTheDocument()
  })

  it('calls onSelect with tool when clicked', () => {
    const onSelect = vi.fn()
    render(<ToolCard tool={tool} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('article'))
    expect(onSelect).toHaveBeenCalledWith(tool)
  })

  it('shows green dot for active tool with success last status', () => {
    render(<ToolCard tool={tool} onSelect={vi.fn()} />)
    const indicator = document.querySelector('[data-status="active"]')
    expect(indicator).toBeInTheDocument()
    expect(indicator).toHaveClass('bg-green-500')
  })

  it('shows red dot and error border when lastStatus is error', () => {
    render(<ToolCard tool={{ ...tool, lastStatus: 'error' }} onSelect={vi.fn()} />)
    const indicator = document.querySelector('[data-last-status="error"]')
    expect(indicator).toBeInTheDocument()
    expect(indicator).toHaveClass('bg-red-500')
    expect(screen.getByRole('article')).toHaveClass('border-red-300')
  })
})
```

- [ ] **Запустить тест — убедиться что падает**

```bash
cd wookiee-hub && npx vitest run src/components/operations/tool-card.test.tsx
# Expected: FAIL
```

- [ ] **Написать ToolCard**

```typescript
// wookiee-hub/src/components/operations/tool-card.tsx
import { cn } from '@/lib/utils'
import type { OperationsTool } from '@/types/tool'

const TYPE_LABELS: Record<string, string> = {
  skill: 'Скилл',
  service: 'Сервис',
  cron: 'Cron',
  script: 'Скрипт',
}

const TYPE_CLASSES: Record<string, string> = {
  skill:   'bg-green-100 text-green-700',
  service: 'bg-blue-100 text-blue-700',
  cron:    'bg-purple-100 text-purple-700',
  script:  'bg-amber-100 text-amber-700',
}

// Status dot priority: run error > catalog status.
// A tool that is `active` in catalog but had a failed run should show red — not green.
function getStatusDot(tool: OperationsTool): string {
  if (tool.lastStatus === 'error') return 'bg-red-500'
  if (tool.status === 'deprecated') return 'bg-amber-500'
  if (tool.status === 'draft') return 'bg-gray-400'
  if (tool.status === 'archived') return 'bg-gray-300'
  return 'bg-green-500'
}

function formatLastRun(iso: string | null): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'только что'
  if (h < 24) return `${h}ч назад`
  const d = Math.floor(h / 24)
  return `${d}д назад`
}

interface ToolCardProps {
  tool: OperationsTool
  onSelect: (tool: OperationsTool) => void
}

export function ToolCard({ tool, onSelect }: ToolCardProps) {
  return (
    <article
      role="article"
      onClick={() => onSelect(tool)}
      className={cn(
        'bg-card rounded-xl p-4 cursor-pointer hover:shadow-sm transition-all border',
        tool.lastStatus === 'error'
          ? 'border-red-300 bg-red-50/30 hover:border-red-400'
          : 'border-border hover:border-primary/40'
      )}
    >
      <div className="flex items-start justify-between mb-1.5">
        <div className="min-w-0 flex-1 mr-2">
          <p className="font-mono text-[13px] font-semibold text-foreground truncate">
            {tool.name}
          </p>
          {tool.nameRu && (
            <p className="text-[12px] text-muted-foreground mt-0.5 truncate">{tool.nameRu}</p>
          )}
        </div>
        <span
          data-status={tool.status}
          data-last-status={tool.lastStatus ?? 'none'}
          className={cn('w-2 h-2 rounded-full shrink-0 mt-1.5', getStatusDot(tool))}
        />
      </div>

      {tool.description && (
        <p className="text-[12px] text-muted-foreground line-clamp-2 mb-3 leading-relaxed">
          {tool.description}
        </p>
      )}

      <div className="flex items-center gap-2">
        <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', TYPE_CLASSES[tool.type] ?? 'bg-muted text-muted-foreground')}>
          {TYPE_LABELS[tool.type] ?? tool.type}
        </span>
        <span className="text-[11px] text-muted-foreground ml-auto">
          {formatLastRun(tool.lastRunAt)}
        </span>
      </div>
    </article>
  )
}
```

- [ ] **Запустить тест — убедиться что проходит**

```bash
cd wookiee-hub && npx vitest run src/components/operations/tool-card.test.tsx
# Expected: PASS (5 tests)
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/components/operations/tool-card.tsx wookiee-hub/src/components/operations/tool-card.test.tsx
git commit -m "feat(hub): add ToolCard component with status, type badge, last-run"
```

---

## Task 10: ToolFilters Component

**Files:**
- Create: `wookiee-hub/src/components/operations/tool-filters.tsx`

- [ ] **Написать компонент**

```typescript
// wookiee-hub/src/components/operations/tool-filters.tsx
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolCategoryFilter } from '@/types/tool'

const CATEGORIES: { value: ToolCategoryFilter; label: string }[] = [
  { value: 'all',       label: 'Все' },
  { value: 'analytics', label: 'Аналитика' },
  { value: 'infra',     label: 'Инфраструктура' },
  { value: 'content',   label: 'Контент' },
  { value: 'publishing',label: 'Публикация' },
  { value: 'team',      label: 'Команда' },
  { value: 'planning',  label: 'Планирование' },
]

interface ToolFiltersProps {
  activeCategory: ToolCategoryFilter
  searchQuery: string
  counts: Partial<Record<ToolCategoryFilter, number>>
  onCategoryChange: (category: ToolCategoryFilter) => void
  onSearchChange: (query: string) => void
}

export function ToolFilters({
  activeCategory,
  searchQuery,
  counts,
  onCategoryChange,
  onSearchChange,
}: ToolFiltersProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {CATEGORIES.map(({ value, label }) => {
        const count = counts[value] ?? 0
        if (value !== 'all' && count === 0) return null
        return (
          <button
            key={value}
            onClick={() => onCategoryChange(value)}
            className={cn(
              'px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-colors',
              activeCategory === value
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border hover:border-primary/40 hover:text-foreground'
            )}
          >
            {label}
            {value !== 'all' && (
              <span className="ml-1 opacity-60">{count}</span>
            )}
          </button>
        )
      })}

      <div className="ml-auto flex items-center gap-2 border border-border rounded-lg px-3 py-1.5 bg-card min-w-[180px]">
        <Search size={13} className="text-muted-foreground shrink-0" />
        <input
          type="text"
          placeholder="Поиск тулзов..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="text-[12px] bg-transparent outline-none text-foreground placeholder:text-muted-foreground w-full"
        />
      </div>
    </div>
  )
}
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/components/operations/tool-filters.tsx
git commit -m "feat(hub): add ToolFilters component with category pills and search"
```

---

## Task 11: Skill .md Viewer

**Files:**
- Create: `wookiee-hub/src/components/operations/tool-skill-viewer.tsx`

- [ ] **Написать компонент**

```typescript
// wookiee-hub/src/components/operations/tool-skill-viewer.tsx
import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'

interface ToolSkillViewerProps {
  mdPath: string  // e.g. "finance-report.md"
}

export function ToolSkillViewer({ mdPath }: ToolSkillViewerProps) {
  const [content, setContent] = useState<string | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'not-found'>('loading')

  useEffect(() => {
    setStatus('loading')
    setContent(null)
    fetch(`/skills/${mdPath}`)
      .then((res) => {
        if (!res.ok) { setStatus('not-found'); return null }
        return res.text()
      })
      .then((text) => {
        if (text !== null) { setContent(text); setStatus('ok') }
      })
      .catch(() => setStatus('not-found'))
  }, [mdPath])

  if (status === 'loading') {
    return <div className="text-[12px] text-muted-foreground">Загружаю документацию...</div>
  }

  if (status === 'not-found') return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
        <FileText size={11} />
        Инструкция скилла
      </div>
      <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-muted/40 border border-border rounded-lg p-3 text-foreground font-mono overflow-auto max-h-64">
        {content}
      </pre>
    </div>
  )
}
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/components/operations/tool-skill-viewer.tsx
git commit -m "feat(hub): add ToolSkillViewer fetches /skills/*.md for skill tools"
```

---

## Task 12: Tool Detail Panel

**Files:**
- Create: `wookiee-hub/src/components/operations/tool-detail-panel.tsx`

- [ ] **Написать компонент**

```typescript
// wookiee-hub/src/components/operations/tool-detail-panel.tsx
import { X, Terminal, Link2, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { OperationsTool } from '@/types/tool'
import { ToolSkillViewer } from './tool-skill-viewer'

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен',
  deprecated: 'Устарел',
  draft: 'Черновик',
  archived: 'Архив',
}
const STATUS_CLASS: Record<string, string> = {
  active:     'bg-green-100 text-green-700',
  deprecated: 'bg-amber-100 text-amber-700',
  draft:      'bg-gray-100 text-gray-600',
  archived:   'bg-red-100 text-red-700',
}
const CATEGORY_LABEL: Record<string, string> = {
  analytics: 'Аналитика',
  infra: 'Инфраструктура',
  content: 'Контент',
  publishing: 'Публикация',
  team: 'Команда',
  planning: 'Планирование',
}

function formatLastRunPanel(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'только что'
  if (h < 24) return `${h}ч назад`
  return `${Math.floor(h / 24)}д назад`
}

interface SectionProps { label: string; children: React.ReactNode }
function Section({ label, children }: SectionProps) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
      {children}
      <div className="border-t border-border/50 mt-4 pt-0" />
    </div>
  )
}

interface ToolDetailPanelProps {
  tool: OperationsTool
  onClose: () => void
}

export function ToolDetailPanel({ tool, onClose }: ToolDetailPanelProps) {
  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40" onClick={onClose} />

      {/* Panel */}
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-[480px] max-w-full bg-card border-l border-border shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-card border-b border-border px-5 py-4 flex items-start justify-between">
          <div>
            <p className="font-mono text-[15px] font-bold text-foreground">{tool.name}</p>
            {tool.nameRu && (
              <p className="text-[13px] text-muted-foreground mt-0.5">{tool.nameRu}</p>
            )}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded', STATUS_CLASS[tool.status])}>
                {STATUS_LABEL[tool.status] ?? tool.status}
              </span>
              <span className="text-[10px] bg-muted text-muted-foreground px-2 py-0.5 rounded">
                {CATEGORY_LABEL[tool.category] ?? tool.category}
              </span>
              {tool.version && (
                <span className="text-[10px] text-muted-foreground font-mono">{tool.version}</span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-5 space-y-5">

          {/* Description */}
          {tool.description && (
            <Section label="Что делает">
              <p className="text-[13px] text-foreground leading-relaxed">{tool.description}</p>
            </Section>
          )}

          {/* How it works */}
          {tool.howItWorks && (
            <Section label="Как работает">
              <pre className="text-[12px] text-foreground leading-relaxed whitespace-pre-wrap font-sans">
                {tool.howItWorks}
              </pre>
            </Section>
          )}

          {/* Skill .md doc viewer (only for skills) */}
          {tool.type === 'skill' && tool.skillMdPath && (
            <Section label="">
              <ToolSkillViewer mdPath={tool.skillMdPath} />
            </Section>
          )}

          {/* Cron schedule placeholder */}
          {tool.type === 'cron' && tool.runCommand && (
            <Section label="Расписание">
              <p className="font-mono text-[12px] bg-muted px-3 py-2 rounded-lg text-foreground">
                {tool.runCommand}
              </p>
            </Section>
          )}

          {/* Run command */}
          {tool.runCommand && (
            <Section label="Команда запуска">
              <div className="flex items-center gap-2 bg-muted/50 border border-border rounded-lg px-3 py-2">
                <Terminal size={13} className="text-muted-foreground shrink-0" />
                <code className="text-[12px] font-mono text-foreground flex-1">{tool.runCommand}</code>
              </div>
            </Section>
          )}

          {/* Health check (services) */}
          {tool.healthCheck && (
            <Section label="Как проверить">
              <div className="bg-muted/50 border border-border rounded-lg px-3 py-2">
                <code className="text-[12px] font-mono text-foreground">{tool.healthCheck}</code>
              </div>
            </Section>
          )}

          {/* Dependencies */}
          {(tool.dependsOn.length > 0 || tool.dataSources.length > 0) && (
            <Section label="Зависимости">
              <div className="flex flex-wrap gap-2">
                {[...tool.dataSources, ...tool.dependsOn].map((dep) => (
                  <span key={dep} className="text-[11px] bg-muted border border-border rounded px-2 py-0.5 text-muted-foreground">
                    {dep}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {/* Output */}
          {(tool.outputTargets.length > 0 || tool.outputDescription) && (
            <Section label="Результат">
              {tool.outputDescription && (
                <p className="text-[12px] text-foreground mb-2">{tool.outputDescription}</p>
              )}
              {tool.outputTargets.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <ArrowRight size={12} className="text-muted-foreground" />
                  {tool.outputTargets.map((t) => (
                    <span key={t} className="text-[11px] bg-green-50 border border-green-200 text-green-700 rounded px-2 py-0.5">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </Section>
          )}

          {/* Required env vars (skills only) */}
          {tool.type === 'skill' && tool.requiredEnvVars.length > 0 && (
            <Section label="Переменные окружения">
              <div className="flex flex-wrap gap-2">
                {tool.requiredEnvVars.map((v) => (
                  <code key={v} className="text-[11px] bg-amber-50 border border-amber-200 text-amber-700 rounded px-2 py-0.5 font-mono">
                    {v}
                  </code>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Задать в .env файле проекта</p>
            </Section>
          )}

          {/* Run stats from tools table — available in Phase 1 */}
          <Section label="Статистика запусков">
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-muted/40 border border-border rounded-lg p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Всего</p>
                <p className="text-xl font-bold text-foreground">{tool.totalRuns}</p>
              </div>
              <div className="bg-muted/40 border border-border rounded-lg p-3">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Последний</p>
                <p className="text-[12px] text-foreground">{tool.lastRunAt ? formatLastRunPanel(tool.lastRunAt) : '—'}</p>
              </div>
              <div className={cn(
                'border rounded-lg p-3',
                tool.lastStatus === 'error' ? 'bg-red-50 border-red-200' : 'bg-muted/40 border-border'
              )}>
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Статус</p>
                <p className={cn(
                  'text-[12px] font-medium',
                  tool.lastStatus === 'error' ? 'text-red-600' :
                  tool.lastStatus === 'success' ? 'text-green-600' : 'text-muted-foreground'
                )}>
                  {tool.lastStatus ?? '—'}
                </p>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">Детальная история запусков — Phase 2</p>
          </Section>

        </div>
      </aside>
    </>
  )
}
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/components/operations/tool-detail-panel.tsx
git commit -m "feat(hub): add ToolDetailPanel with all sections for skill/service/cron types"
```

---

## Task 13: Tools Catalog Page + Activity Stub

**Files:**
- Create: `wookiee-hub/src/pages/operations/tools.tsx`
- Create: `wookiee-hub/src/pages/operations/activity.tsx`

- [ ] **Написать Tools Catalog Page**

```typescript
// wookiee-hub/src/pages/operations/tools.tsx
import { useEffect, useMemo } from 'react'
import { useOperationsStore, filterTools } from '@/stores/operations'
import { fetchTools } from '@/lib/tools-service'
import { ToolCard } from '@/components/operations/tool-card'
import { ToolFilters } from '@/components/operations/tool-filters'
import { ToolDetailPanel } from '@/components/operations/tool-detail-panel'
import type { OperationsTool, ToolCategory, ToolCategoryFilter } from '@/types/tool'

const CATEGORY_LABELS: Record<ToolCategory, string> = {
  analytics:  'Аналитика',
  infra:      'Инфраструктура',
  content:    'Контент',
  publishing: 'Публикация',
  team:       'Команда',
  planning:   'Планирование',
}
const CATEGORY_ORDER: ToolCategory[] = ['analytics', 'infra', 'content', 'publishing', 'team', 'planning']

export function ToolsPage() {
  const {
    tools, loading, categoryFilter, searchQuery, selectedTool,
    setTools, setLoading, setCategoryFilter, setSearchQuery, setSelectedTool,
  } = useOperationsStore()

  useEffect(() => {
    setLoading(true)
    fetchTools().then((data) => { setTools(data); setLoading(false) })
  }, [])

  const filtered = useMemo(
    () => filterTools(tools, categoryFilter, searchQuery),
    [tools, categoryFilter, searchQuery]
  )

  const counts = useMemo(() => {
    const result: Partial<Record<ToolCategoryFilter, number>> = { all: tools.length }
    for (const tool of tools) {
      result[tool.category] = (result[tool.category] ?? 0) + 1
    }
    return result
  }, [tools])

  const grouped = useMemo(() => {
    const map = new Map<ToolCategory, OperationsTool[]>()
    for (const tool of filtered) {
      const list = map.get(tool.category) ?? []
      list.push(tool)
      map.set(tool.category, list)
    }
    return CATEGORY_ORDER
      .filter((cat) => map.has(cat))
      .map((cat) => ({ category: cat, tools: map.get(cat)! }))
  }, [filtered])

  const activeCount = tools.filter(t => t.status === 'active').length
  const errorCount = tools.filter(t => t.lastStatus === 'error').length

  const lastRunDisplay = useMemo(() => {
    const dates = tools.filter(t => t.lastRunAt).map(t => t.lastRunAt!)
    if (dates.length === 0) return '—'
    const latest = dates.reduce((a, b) => a > b ? a : b)
    const diff = Date.now() - new Date(latest).getTime()
    const h = Math.floor(diff / 3_600_000)
    if (h < 1) return 'только что'
    if (h < 24) return `${h}ч назад`
    return `${Math.floor(h / 24)}д назад`
  }, [tools])

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Tools Catalog</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Все инструменты системы Wookiee — агенты, сервисы, скиллы, cron-задачи
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Всего тулзов',     value: tools.length,   sub: 'в каталоге',         cls: 'text-foreground' },
          { label: 'Активных',         value: activeCount,     sub: `из ${tools.length}`,  cls: 'text-green-600' },
          { label: 'С ошибкой',        value: errorCount,      sub: 'last_status = error', cls: errorCount > 0 ? 'text-red-600' : 'text-foreground' },
          { label: 'Последний запуск', value: lastRunDisplay,  sub: 'по данным каталога',  cls: 'text-foreground' },
        ].map(({ label, value, sub, cls }) => (
          <div key={label} className="bg-card border border-border rounded-xl p-4">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
            <p className={`text-2xl font-bold ${cls}`}>{value}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <ToolFilters
        activeCategory={categoryFilter}
        searchQuery={searchQuery}
        counts={counts}
        onCategoryChange={setCategoryFilter}
        onSearchChange={setSearchQuery}
      />

      {/* Loading */}
      {loading && (
        <p className="text-sm text-muted-foreground py-8 text-center">Загружаю тулзы...</p>
      )}

      {/* Grouped grid */}
      {!loading && grouped.map(({ category, tools: catTools }) => (
        <div key={category}>
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              {CATEGORY_LABELS[category]}
            </h2>
            <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
              {catTools.length}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {catTools.map((tool) => (
              <ToolCard key={tool.slug} tool={tool} onSelect={setSelectedTool} />
            ))}
          </div>
        </div>
      ))}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-sm text-muted-foreground">Тулзы не найдены</p>
        </div>
      )}

      {/* Add new tool instruction */}
      {!loading && (
        <div className="border border-dashed border-border rounded-xl p-4 text-center">
          <p className="text-[13px] font-medium text-foreground">Добавить новый инструмент в каталог</p>
          <p className="text-[12px] text-muted-foreground mt-1">
            Запустите{' '}
            <code className="font-mono bg-muted text-foreground px-1 py-0.5 rounded">/tool-register</code>
            {' '}в Claude Code — скилл заведёт запись в Supabase и обновит каталог
          </p>
        </div>
      )}

      {/* Detail Panel */}
      {selectedTool && (
        <ToolDetailPanel tool={selectedTool} onClose={() => setSelectedTool(null)} />
      )}
    </div>
  )
}
```

- [ ] **Написать Activity Stub**

```typescript
// wookiee-hub/src/pages/operations/activity.tsx
export function ActivityPage() {
  return (
    <div className="py-12 text-center">
      <p className="text-lg font-medium text-foreground">Activity Feed</p>
      <p className="text-sm text-muted-foreground mt-1">
        Появится в Phase 2 после подключения телеметрии инструментов
      </p>
    </div>
  )
}
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/pages/operations/
git commit -m "feat(hub): add ToolsPage (catalog + detail panel) and ActivityPage stub"
```

---

## Task 14: Router + Navigation

**Files:**
- Modify: `wookiee-hub/src/router.tsx`
- Modify: `wookiee-hub/src/config/navigation.ts`

- [ ] **Обновить navigation.ts**

```typescript
// wookiee-hub/src/config/navigation.ts
import {
  MessageSquare,
  LayoutGrid,
  Star,
  HelpCircle,
  CheckCircle2,
  BarChart3,
  Clock,
  Activity,
} from 'lucide-react'
import type { NavGroup } from '@/types/navigation'

export const navigationGroups: NavGroup[] = [
  {
    id: 'operations',
    icon: LayoutGrid,
    label: 'Operations',
    items: [
      { id: 'tools',    label: 'Tools Catalog',  icon: LayoutGrid, path: '/operations/tools',    badge: '47' },
      { id: 'activity', label: 'Activity Feed',   icon: Activity,   path: '/operations/activity', badge: 'Phase 2' },
      { id: 'health',   label: 'System Health',   icon: Clock,      path: '/operations/health',   badge: 'Phase 2' },
    ],
  },
  {
    id: 'community',
    icon: MessageSquare,
    label: 'Комьюнити',
    items: [
      { id: 'reviews',   label: 'Отзывы',    icon: Star,         path: '/community/reviews' },
      { id: 'questions', label: 'Вопросы',   icon: HelpCircle,   path: '/community/questions' },
      { id: 'answers',   label: 'Ответы',    icon: CheckCircle2, path: '/community/answers' },
      { id: 'analytics', label: 'Аналитика', icon: BarChart3,    path: '/community/analytics' },
    ],
  },
]
```

- [ ] **Обновить router.tsx**

```typescript
// wookiee-hub/src/router.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'
import { ProtectedRoute } from '@/components/auth/protected-route'
import { LoginPage } from '@/pages/auth/login'
import { ToolsPage } from '@/pages/operations/tools'
import { ActivityPage } from '@/pages/operations/activity'
import { ReviewsPage } from '@/pages/community/reviews'
import { QuestionsPage } from '@/pages/community/questions'
import { AnswersPage } from '@/pages/community/answers'
import { AnalyticsPage } from '@/pages/community/analytics'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { path: '/',                    element: <Navigate to="/operations/tools" replace /> },
      { path: '/operations',          element: <Navigate to="/operations/tools" replace /> },
      { path: '/operations/tools',    element: <ToolsPage /> },
      { path: '/operations/activity', element: <ActivityPage /> },
      { path: '/community',           element: <Navigate to="/community/reviews" replace /> },
      { path: '/community/reviews',   element: <ReviewsPage /> },
      { path: '/community/questions', element: <QuestionsPage /> },
      { path: '/community/answers',   element: <AnswersPage /> },
      { path: '/community/analytics', element: <AnalyticsPage /> },
    ],
  },
])
```

- [ ] **Commit**

```bash
git add wookiee-hub/src/router.tsx wookiee-hub/src/config/navigation.ts
git commit -m "feat(hub): update router + navigation for Operations section, add /login, remove /agents"
```

---

## Task 15: Smoke Test + Build

- [ ] **Запустить все тесты**

```bash
cd wookiee-hub && npx vitest run
# Expected: все тесты PASS
```

- [ ] **Запустить dev-сервер и проверить вручную**

```bash
cd wookiee-hub && npm run dev
# Открыть http://localhost:5173
# Ожидаем: redirect → /login
# Ввести email/password (создать пользователя заранее в Supabase Dashboard)
# После логина: redirect → /operations/tools
# Проверить: каталог загружается, карточки отображаются, клик открывает панель
# Для скиллов: документация отображается в панели
# Проверить: logout через UserMenu → redirect /login
# Проверить: Community раздел работает (Reviews, Questions и т.д.)
```

- [ ] **Собрать продакшн-билд**

```bash
cd wookiee-hub && npm run build
# Expected: 0 errors
```

- [ ] **Деплой на hub.wookiee.shop**

```bash
ssh timeweb "cd /path/to/wookiee && git pull && cd wookiee-hub && npm run build"
# Или через существующий деплой-пайплайн (проверить deploy/)
```

- [ ] **Финальный commit**

```bash
git add -A
git commit -m "feat(hub): wookiee hub operations section - phase 1 complete"
```

---

## Переменные окружения

Убедиться что в `wookiee-hub/.env` есть:
```
VITE_SUPABASE_URL=https://gjvwcdtfglupewcwzfhw.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key из Supabase Dashboard>
```

Создать тестового пользователя: Supabase Dashboard → Authentication → Users → Add user → ввести email + пароль.
