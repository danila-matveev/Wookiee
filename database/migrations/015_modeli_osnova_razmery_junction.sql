-- database/migrations/015_modeli_osnova_razmery_junction.sql
-- W2.1 — Wookiee Hub Catalog Overhaul, Wave 2
--
-- Заменяет хардкод `SIZES_LINEUP = ["XS","S","M","L","XL","XXL"]` в
-- `wookiee-hub/src/pages/catalog/model-card.tsx` на справочную junction-таблицу
-- `modeli_osnova_razmery (model_osnova_id, razmer_id, poryadok)`, которая
-- ссылается на существующий справочник `razmery`.
--
-- Backfill: для каждой строки `modeli_osnova` вставляем 6 записей XS..XXL
-- с `poryadok = 1..6`. Дальнейшее уточнение размерной линейки по модели —
-- вне скоупа W2.1 (см. PLAN).
--
-- razmery.id маппинг (verified pre-migration):
--   XS=6, S=1, M=2, L=3, XL=4, XXL=5
-- razmery.nazvanie хранит код размера (XS/S/M/L/XL/XXL); отдельной колонки
-- `kod` нет — используем `nazvanie`.

create table if not exists public.modeli_osnova_razmery (
  id                serial primary key,
  model_osnova_id   int not null references public.modeli_osnova(id) on delete cascade,
  razmer_id         int not null references public.razmery(id) on delete restrict,
  poryadok          int not null default 0,
  unique (model_osnova_id, razmer_id)
);

create index if not exists modeli_osnova_razmery_model_idx
  on public.modeli_osnova_razmery(model_osnova_id, poryadok);

alter table public.modeli_osnova_razmery enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'modeli_osnova_razmery'
      and policyname = 'authenticated read modeli_osnova_razmery'
  ) then
    execute 'create policy "authenticated read modeli_osnova_razmery" on public.modeli_osnova_razmery for select to authenticated using (true)';
  end if;
  if not exists (
    select 1 from pg_policies
    where tablename = 'modeli_osnova_razmery'
      and policyname = 'authenticated write modeli_osnova_razmery'
  ) then
    execute 'create policy "authenticated write modeli_osnova_razmery" on public.modeli_osnova_razmery for all to authenticated using (true) with check (true)';
  end if;
end $$;

grant select, insert, update, delete on public.modeli_osnova_razmery to authenticated;
grant usage, select on sequence public.modeli_osnova_razmery_id_seq to authenticated;

-- Backfill: XS..XXL для каждой модели; razmery.nazvanie играет роль кода.
insert into public.modeli_osnova_razmery (model_osnova_id, razmer_id, poryadok)
select
  mo.id,
  r.id,
  array_position(array['XS','S','M','L','XL','XXL'], r.nazvanie) as poryadok
from public.modeli_osnova mo
cross join public.razmery r
where r.nazvanie in ('XS','S','M','L','XL','XXL')
on conflict (model_osnova_id, razmer_id) do nothing;
