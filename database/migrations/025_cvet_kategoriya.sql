-- Migration 025: cvet_kategoriya
-- Catalog Management Overhaul Wave 9 (W9.12): filter color palette by category.
--
-- m2m link table between cveta (color reference) and kategorii (category).
-- A colour can apply to many categories; a category can have many colours.
--
-- Backward compat: if a colour has NO rows in this table, it is treated as
-- applicable to ALL categories (legacy fallback). Once a colour gets at least
-- one explicit category mapping, only those categories include it.

CREATE TABLE IF NOT EXISTS public.cvet_kategoriya (
  cvet_id INT NOT NULL REFERENCES public.cveta(id) ON DELETE CASCADE,
  kategoriya_id INT NOT NULL REFERENCES public.kategorii(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (cvet_id, kategoriya_id)
);

CREATE INDEX IF NOT EXISTS idx_cvet_kategoriya_cvet
  ON public.cvet_kategoriya(cvet_id);

CREATE INDEX IF NOT EXISTS idx_cvet_kategoriya_kategoriya
  ON public.cvet_kategoriya(kategoriya_id);

COMMENT ON TABLE public.cvet_kategoriya IS
  'M2M: which colours are applicable to which categories. Empty rowset for a colour = applies to ALL categories (legacy fallback).';

ALTER TABLE public.cvet_kategoriya ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated read" ON public.cvet_kategoriya
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "authenticated write" ON public.cvet_kategoriya
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.cvet_kategoriya TO authenticated;
