-- =============================================================================
-- marketing.channels — канал для промокодов и search queries
-- =============================================================================
-- Phase 2 / Task 2.1: Marketing Hub Implementation v2
--
-- Назначение: централизованный реестр каналов трафика (Бренд, Яндекс, ВК, etc.)
-- для рендеринга в SelectMenu allowAdd при создании новых промокодов и поисковых
-- запросов. Slug генерируется триггером server-side (Backend Blocker #3); INSERT
-- разрешён только service_role и admin role — UI пишет через защищённый API
-- endpoint (Task 2.8).
--
-- Применить через: supabase apply_migration (имя marketing_channels_registry).
-- =============================================================================

CREATE TABLE marketing.channels (
  id          bigserial PRIMARY KEY,
  slug        text NOT NULL UNIQUE,
  label       text NOT NULL,
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Server-side slug generation: lowercase latin + digits + underscores; fallback
-- к 'channel'; коллизии разрешаются автоинкрементным суффиксом '_N'.
CREATE OR REPLACE FUNCTION marketing.tg_channels_slug() RETURNS trigger AS $$
DECLARE
  base text;
  candidate text;
  n int := 0;
BEGIN
  IF NEW.slug IS NULL OR NEW.slug = '' THEN
    base := lower(regexp_replace(NEW.label, '[^a-zA-Z0-9]+', '_', 'g'));
    base := regexp_replace(base, '^_+|_+$', '', 'g');
    IF base = '' THEN base := 'channel'; END IF;
    candidate := base;
    WHILE EXISTS (SELECT 1 FROM marketing.channels WHERE slug = candidate) LOOP
      n := n + 1;
      candidate := base || '_' || n::text;
    END LOOP;
    NEW.slug := candidate;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = pg_catalog, marketing;

CREATE TRIGGER channels_slug_before_insert
  BEFORE INSERT ON marketing.channels
  FOR EACH ROW EXECUTE FUNCTION marketing.tg_channels_slug();

-- RLS: read для всех authenticated, write только service_role
ALTER TABLE marketing.channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY channels_read ON marketing.channels
  FOR SELECT TO authenticated
  USING (true);

GRANT SELECT ON marketing.channels TO authenticated;
GRANT ALL ON marketing.channels TO service_role;
GRANT USAGE ON SEQUENCE marketing.channels_id_seq TO service_role;

-- Seed: 12 каналов из v4 JSX prototype + текущей бизнес-практики Wookiee
INSERT INTO marketing.channels (slug, label) VALUES
  ('brand',     'Бренд'),
  ('yandex',    'Яндекс'),
  ('vk_target', 'Таргет ВК'),
  ('adblogger', 'Adblogger'),
  ('creators',  'Креаторы'),
  ('smm',       'SMM'),
  ('other',     'Прочее'),
  ('social',    'Соцсети'),
  ('blogger',   'Блогер'),
  ('corp',      'Корп'),
  ('yps',       'ЯПС'),
  ('mvp',       'МВП');
