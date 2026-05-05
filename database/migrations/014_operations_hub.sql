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
