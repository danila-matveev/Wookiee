-- Task 2.2 — `creator_ref` column + auto-sync trigger on `crm.substitute_articles`.
-- Eliminates ETL drift: креатор имена парсятся из `campaign_name` непосредственно в БД,
-- VIEW `marketing.search_queries_unified` начинает возвращать `sa.creator_ref` вместо NULL.
-- Pattern: case-insensitive `^креатор[_ ]` (CTO Blocker #2 + Backend Important #4 + Minor #12).

ALTER TABLE crm.substitute_articles
  ADD COLUMN IF NOT EXISTS creator_ref text;

-- 87 строк сейчас — обычный CREATE INDEX мгновенный, CONCURRENTLY не нужен (и не запускается в транзакции apply_migration).
CREATE INDEX IF NOT EXISTS idx_substitute_articles_creator_ref
  ON crm.substitute_articles(creator_ref);

-- Backfill существующих строк до создания триггера (идемпотентно, повторные запуски ничего не меняют).
UPDATE crm.substitute_articles
SET creator_ref = trim(regexp_replace(campaign_name, '^креатор[_ ]', '', 'i'))
WHERE creator_ref IS NULL
  AND campaign_name ~* '^креатор[_ ]';

-- Trigger: BEFORE INSERT OR UPDATE OF campaign_name. ETL может писать campaign_name —
-- триггер сам обновит creator_ref (или сбросит в NULL, если паттерн не совпал).
CREATE OR REPLACE FUNCTION crm.tg_substitute_articles_creator_ref()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, crm
AS $$
BEGIN
  IF NEW.campaign_name IS NOT NULL AND NEW.campaign_name ~* '^креатор[_ ]' THEN
    NEW.creator_ref := trim(regexp_replace(NEW.campaign_name, '^креатор[_ ]', '', 'i'));
  ELSE
    NEW.creator_ref := NULL;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS substitute_articles_creator_ref ON crm.substitute_articles;
CREATE TRIGGER substitute_articles_creator_ref
  BEFORE INSERT OR UPDATE OF campaign_name ON crm.substitute_articles
  FOR EACH ROW EXECUTE FUNCTION crm.tg_substitute_articles_creator_ref();

COMMENT ON COLUMN crm.substitute_articles.creator_ref IS
  'Имя криэйтора, авто-парсится из campaign_name по паттерну `^креатор[_ ]` (case-insensitive). Обновляется триггером substitute_articles_creator_ref.';
