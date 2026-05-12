-- W3.1: brendy reference table + modeli_osnova.brand_id FK
-- Architectural decision: бренд ≠ фабрика. Фабрика = производитель (Singwear / Angelina / B&G),
-- бренд = маркетинговое имя (WOOKIEE / TELOWAY).
-- Backfill через категории: 1,2,3,11 → WOOKIEE (бельё); 4,5,6,7,8,10 → TELOWAY (спорт).

CREATE TABLE IF NOT EXISTS public.brendy (
  id          SERIAL PRIMARY KEY,
  kod         TEXT NOT NULL UNIQUE,
  nazvanie    TEXT NOT NULL,
  opisanie    TEXT,
  logo_url    TEXT,
  status_id   INT REFERENCES public.statusy(id),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.brendy ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated read" ON public.brendy;
CREATE POLICY "authenticated read" ON public.brendy
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "authenticated write" ON public.brendy;
CREATE POLICY "authenticated write" ON public.brendy
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.brendy TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.brendy_id_seq TO authenticated;

-- Fixture rows
INSERT INTO public.brendy (kod, nazvanie, opisanie) VALUES
  ('wookiee', 'WOOKIEE', 'Бельё'),
  ('teloway', 'TELOWAY', 'Спортивная одежда — wellness-бренд, запуск 2026')
ON CONFLICT (kod) DO NOTHING;

-- Add brand_id (nullable for now → backfill → NOT NULL)
ALTER TABLE public.modeli_osnova
  ADD COLUMN IF NOT EXISTS brand_id INT
  REFERENCES public.brendy(id);

CREATE INDEX IF NOT EXISTS idx_modeli_osnova_brand_id
  ON public.modeli_osnova(brand_id);

-- Backfill: WOOKIEE → бельё-категории (1, 2, 3, 11)
UPDATE public.modeli_osnova
SET brand_id = (SELECT id FROM public.brendy WHERE kod = 'wookiee')
WHERE kategoriya_id IN (1, 2, 3, 11) AND brand_id IS NULL;

-- Backfill: TELOWAY → спорт-категории (4, 5, 6, 7, 8, 10)
UPDATE public.modeli_osnova
SET brand_id = (SELECT id FROM public.brendy WHERE kod = 'teloway')
WHERE kategoriya_id IN (4, 5, 6, 7, 8, 10) AND brand_id IS NULL;

-- Enforce NOT NULL (will fail if any model has uncovered kategoriya_id)
ALTER TABLE public.modeli_osnova ALTER COLUMN brand_id SET NOT NULL;

COMMENT ON TABLE public.brendy IS
  'W3.1 reference: маркетинговые бренды (WOOKIEE / TELOWAY). Не путать с fabriki (производитель). Каждая модель в modeli_osnova обязана быть привязана к одному бренду через brand_id.';
COMMENT ON COLUMN public.modeli_osnova.brand_id IS
  'W3.1: FK на brendy. NOT NULL. Backfill из категорий: 1/2/3/11 → wookiee, 4/5/6/7/8/10 → teloway.';
