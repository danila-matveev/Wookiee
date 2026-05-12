-- W6.1: registry of attribute definitions (label, type, options)
-- Replaces hardcoded `ALL_ATTRIBUTES` map in src/types/catalog.ts.
-- W6.2: type='url' allows custom user-defined link fields (e.g. "Я.Диск-сертификат").

CREATE TABLE IF NOT EXISTS public.atributy (
  id            SERIAL PRIMARY KEY,
  key           TEXT NOT NULL UNIQUE,
  label         TEXT NOT NULL,
  type          TEXT NOT NULL CHECK (type IN (
                  'text','number','textarea','select','multiselect',
                  'file_url','url','date','checkbox','pills'
                )),
  options       JSONB NOT NULL DEFAULT '[]'::jsonb,
  default_value TEXT,
  helper_text   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.atributy ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS atributy_authenticated ON public.atributy;
CREATE POLICY atributy_authenticated ON public.atributy
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.atributy TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.atributy_id_seq TO authenticated;
COMMENT ON TABLE public.atributy IS 'Registry of attribute definitions used by model-card Атрибуты block.';

-- Backfill 10 rows from existing ALL_ATTRIBUTES map.
INSERT INTO public.atributy (key, label, type, options) VALUES
  ('stepen_podderzhki','Степень поддержки','select',
    '["Низкая","Средняя","Высокая"]'::jsonb),
  ('forma_chashki','Форма чашки','select',
    '["Без формованной чашки","Pull-on","Формованная","Push-up"]'::jsonb),
  ('regulirovka','Регулировка','select',
    '["Без регулировки","Регулируемые бретели","Регулируемая застёжка"]'::jsonb),
  ('zastezhka','Застёжка','select',
    '["Без застёжки","Крючки","Застёжка спереди","Магнитная"]'::jsonb),
  ('dlya_kakoy_grudi','Для какой груди','select',
    '["Для любой","Малая/средняя","Средняя/большая","Большая"]'::jsonb),
  ('posadka_trusov','Посадка трусов','select',
    '["Низкая","Средняя","Высокая"]'::jsonb),
  ('vid_trusov','Вид трусов','select',
    '["Слипы","Бразилианы","Хипстеры","Стринги","Танга","Шортики"]'::jsonb),
  ('naznachenie','Назначение','select',
    '["Повседневное","Спорт","Премиум","Сон"]'::jsonb),
  ('stil','Стиль','text','[]'::jsonb),
  ('po_nastroeniyu','По настроению','text','[]'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- Extend kategoriya_atributy with FK to atributy (keep atribut_key for now).
ALTER TABLE public.kategoriya_atributy
  ADD COLUMN IF NOT EXISTS atribut_id INT REFERENCES public.atributy(id) ON DELETE CASCADE;

UPDATE public.kategoriya_atributy ka
SET atribut_id = a.id
FROM public.atributy a
WHERE ka.atribut_id IS NULL AND ka.atribut_key = a.key;

CREATE INDEX IF NOT EXISTS kategoriya_atributy_atribut_id_idx
  ON public.kategoriya_atributy(atribut_id);
