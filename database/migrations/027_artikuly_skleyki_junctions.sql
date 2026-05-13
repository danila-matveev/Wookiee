-- W10.43: Junction tables artikuly ↔ skleyki (WB + OZON)
-- Контекст: до W10 склейки связывались только с tovary (через
-- tovary_skleyki_wb / tovary_skleyki_ozon). Это мешает (a) показывать
-- склейки в карточке артикула, (b) группировать SKU по артикулу в карточке
-- склейки (W10.23), (c) бэйдж "склейка" в реестре /artikuly (W10.26).
--
-- Решение: завести две параллельные junction-таблицы и сделать backfill
-- из текущей связи tovary↔skleyki через tovary.artikul_id.
--
-- Скейл: skleyki_wb ~ <50 строк, skleyki_ozon ~ <50, tovary ~ 11k.
-- Backfill — однократная операция, DISTINCT artikul_id, занимает <1с.
--
-- Audit: composite-PK таблицы НЕ покрываются audit_trigger_fn
-- (он ожидает поле id). Изменения связки видны через диффы skleyka.
-- Если в будущем потребуется явный аудит — добавить отдельный trigger.

-- ── WB junction ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.artikuly_skleyki_wb (
  artikul_id  INTEGER NOT NULL REFERENCES public.artikuly(id)    ON DELETE CASCADE,
  skleyka_id  INTEGER NOT NULL REFERENCES public.skleyki_wb(id)  ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (artikul_id, skleyka_id)
);
CREATE INDEX IF NOT EXISTS artikuly_skleyki_wb_skleyka_idx
  ON public.artikuly_skleyki_wb(skleyka_id);

-- ── OZON junction ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.artikuly_skleyki_ozon (
  artikul_id  INTEGER NOT NULL REFERENCES public.artikuly(id)      ON DELETE CASCADE,
  skleyka_id  INTEGER NOT NULL REFERENCES public.skleyki_ozon(id)  ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (artikul_id, skleyka_id)
);
CREATE INDEX IF NOT EXISTS artikuly_skleyki_ozon_skleyka_idx
  ON public.artikuly_skleyki_ozon(skleyka_id);

-- ── RLS ─────────────────────────────────────────────────────────────
ALTER TABLE public.artikuly_skleyki_wb   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artikuly_skleyki_ozon ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS authenticated_read  ON public.artikuly_skleyki_wb;
DROP POLICY IF EXISTS authenticated_write ON public.artikuly_skleyki_wb;
CREATE POLICY authenticated_read  ON public.artikuly_skleyki_wb FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_write ON public.artikuly_skleyki_wb FOR ALL    TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS authenticated_read  ON public.artikuly_skleyki_ozon;
DROP POLICY IF EXISTS authenticated_write ON public.artikuly_skleyki_ozon;
CREATE POLICY authenticated_read  ON public.artikuly_skleyki_ozon FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_write ON public.artikuly_skleyki_ozon FOR ALL    TO authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.artikuly_skleyki_wb   TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.artikuly_skleyki_ozon TO authenticated, service_role;

-- ── Backfill из tovary_skleyki_* ────────────────────────────────────
INSERT INTO public.artikuly_skleyki_wb (artikul_id, skleyka_id)
SELECT DISTINCT t.artikul_id, ts.skleyka_id
FROM public.tovary_skleyki_wb ts
JOIN public.tovary t ON t.id = ts.tovar_id
WHERE t.artikul_id IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO public.artikuly_skleyki_ozon (artikul_id, skleyka_id)
SELECT DISTINCT t.artikul_id, ts.skleyka_id
FROM public.tovary_skleyki_ozon ts
JOIN public.tovary t ON t.id = ts.tovar_id
WHERE t.artikul_id IS NOT NULL
ON CONFLICT DO NOTHING;
