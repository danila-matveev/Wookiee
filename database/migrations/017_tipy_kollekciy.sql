-- W2.3: tip_kollekcii reference table + FK on modeli_osnova
-- Keeps existing modeli_osnova.tip_kollekcii TEXT column for backward-compat;
-- adds tip_kollekcii_id INT FK as the authoritative source going forward.

CREATE TABLE IF NOT EXISTS public.tipy_kollekciy (
  id SERIAL PRIMARY KEY,
  nazvanie TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.tipy_kollekciy ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated read" ON public.tipy_kollekciy;
CREATE POLICY "authenticated read" ON public.tipy_kollekciy
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "authenticated write" ON public.tipy_kollekciy;
CREATE POLICY "authenticated write" ON public.tipy_kollekciy
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.tipy_kollekciy TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.tipy_kollekciy_id_seq TO authenticated;

ALTER TABLE public.modeli_osnova
  ADD COLUMN IF NOT EXISTS tip_kollekcii_id INT
  REFERENCES public.tipy_kollekciy(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_modeli_osnova_tip_kollekcii_id
  ON public.modeli_osnova(tip_kollekcii_id);

-- Backfill: extract DISTINCT non-empty values from modeli_osnova.tip_kollekcii
INSERT INTO public.tipy_kollekciy (nazvanie)
SELECT DISTINCT TRIM(tip_kollekcii)
FROM public.modeli_osnova
WHERE tip_kollekcii IS NOT NULL AND TRIM(tip_kollekcii) <> ''
ON CONFLICT (nazvanie) DO NOTHING;

-- Wire up FK on existing rows by matching trimmed text
UPDATE public.modeli_osnova mo
SET tip_kollekcii_id = tk.id
FROM public.tipy_kollekciy tk
WHERE mo.tip_kollekcii IS NOT NULL
  AND TRIM(mo.tip_kollekcii) = tk.nazvanie;

COMMENT ON TABLE public.tipy_kollekciy IS
  'W2.3 reference: tip коллекции. Authoritative source is modeli_osnova.tip_kollekcii_id (FK). The legacy modeli_osnova.tip_kollekcii TEXT column is kept temporarily for backward-compat and is written in parallel.';
