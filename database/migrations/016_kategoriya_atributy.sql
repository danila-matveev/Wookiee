-- Migration 016: kategoriya_atributy
-- Catalog Management Overhaul Wave 2 (W2.2): move category -> attribute_keys mapping
-- out of hardcoded ATTRIBUTES_BY_CATEGORY (wookiee-hub/src/types/catalog.ts:426)
-- into a normalized DB table.
--
-- Scope: just the (kategoriya_id, atribut_key, poryadok) link table.
-- AttributeFieldDef registry (label / type / options) stays in code for now;
-- a full attribute registry (`atributy` table) is W6.1.

CREATE TABLE IF NOT EXISTS public.kategoriya_atributy (
  id SERIAL PRIMARY KEY,
  kategoriya_id INT NOT NULL REFERENCES public.kategorii(id) ON DELETE CASCADE,
  atribut_key TEXT NOT NULL,
  poryadok INT NOT NULL DEFAULT 0,
  UNIQUE(kategoriya_id, atribut_key)
);

CREATE INDEX IF NOT EXISTS idx_kategoriya_atributy_kategoriya
  ON public.kategoriya_atributy(kategoriya_id);

ALTER TABLE public.kategoriya_atributy ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated read" ON public.kategoriya_atributy
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "authenticated write" ON public.kategoriya_atributy
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.kategoriya_atributy TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.kategoriya_atributy_id_seq TO authenticated;

-- Backfill: derived from ATTRIBUTES_BY_CATEGORY in wookiee-hub/src/types/catalog.ts:426-464
-- poryadok is 1-based, preserving the array order from the source.
INSERT INTO public.kategoriya_atributy (kategoriya_id, atribut_key, poryadok) VALUES
  -- 1 Комплект белья (10)
  (1, 'stepen_podderzhki', 1),
  (1, 'forma_chashki', 2),
  (1, 'regulirovka', 3),
  (1, 'zastezhka', 4),
  (1, 'dlya_kakoy_grudi', 5),
  (1, 'posadka_trusov', 6),
  (1, 'vid_trusov', 7),
  (1, 'naznachenie', 8),
  (1, 'stil', 9),
  (1, 'po_nastroeniyu', 10),
  -- 2 Трусы (5)
  (2, 'posadka_trusov', 1),
  (2, 'vid_trusov', 2),
  (2, 'naznachenie', 3),
  (2, 'stil', 4),
  (2, 'po_nastroeniyu', 5),
  -- 3 Боди женское (6)
  (3, 'stepen_podderzhki', 1),
  (3, 'forma_chashki', 2),
  (3, 'dlya_kakoy_grudi', 3),
  (3, 'naznachenie', 4),
  (3, 'stil', 5),
  (3, 'po_nastroeniyu', 6),
  -- 4 Леггинсы (3)
  (4, 'naznachenie', 1),
  (4, 'stil', 2),
  (4, 'po_nastroeniyu', 3),
  -- 5 Лонгслив (3)
  (5, 'naznachenie', 1),
  (5, 'stil', 2),
  (5, 'po_nastroeniyu', 3),
  -- 6 Рашгард (3)
  (6, 'naznachenie', 1),
  (6, 'stil', 2),
  (6, 'po_nastroeniyu', 3),
  -- 7 Топ (4)
  (7, 'stepen_podderzhki', 1),
  (7, 'naznachenie', 2),
  (7, 'stil', 3),
  (7, 'po_nastroeniyu', 4),
  -- 8 Футболка (3)
  (8, 'naznachenie', 1),
  (8, 'stil', 2),
  (8, 'po_nastroeniyu', 3),
  -- 10 Велосипедки (3)
  (10, 'naznachenie', 1),
  (10, 'stil', 2),
  (10, 'po_nastroeniyu', 3),
  -- 11 Бюстгалтер (8)
  (11, 'stepen_podderzhki', 1),
  (11, 'forma_chashki', 2),
  (11, 'regulirovka', 3),
  (11, 'zastezhka', 4),
  (11, 'dlya_kakoy_grudi', 5),
  (11, 'naznachenie', 6),
  (11, 'stil', 7),
  (11, 'po_nastroeniyu', 8)
ON CONFLICT (kategoriya_id, atribut_key) DO NOTHING;
