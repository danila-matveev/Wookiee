-- W5.1: Storage bucket for catalog assets (model images, color samples, certificate PDFs)
--
-- private, max 10MB, allowed: image/* + application/pdf
-- Paths convention:
--   models/{modeli_osnova_id}/header.{ext}        — model header image
--   colors/{cvet_id}/sample.{ext}                  — color sample image
--   sertifikaty/{sertifikat_id}/{filename}.pdf    — certificate PDF
--
-- RLS:
--   SELECT — authenticated users (signed URLs are used for actual access)
--   INSERT — authenticated users
--   UPDATE — authenticated (owner upserts metadata)
--   DELETE — authenticated users
--
-- Note: object access is gated through signed URLs (TTL=3600) generated server-side;
-- the SELECT policy below allows authenticated session to read row metadata.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'catalog-assets',
  'catalog-assets',
  false,
  10485760,
  ARRAY[
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
    'image/gif',
    'application/pdf'
  ]
)
ON CONFLICT (id) DO UPDATE
  SET public = EXCLUDED.public,
      file_size_limit = EXCLUDED.file_size_limit,
      allowed_mime_types = EXCLUDED.allowed_mime_types;

-- RLS policies for storage.objects (scoped to catalog-assets bucket)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='storage' AND tablename='objects' AND policyname='catalog_assets_select'
  ) THEN
    CREATE POLICY catalog_assets_select ON storage.objects
      FOR SELECT TO authenticated
      USING (bucket_id = 'catalog-assets');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='storage' AND tablename='objects' AND policyname='catalog_assets_insert'
  ) THEN
    CREATE POLICY catalog_assets_insert ON storage.objects
      FOR INSERT TO authenticated
      WITH CHECK (bucket_id = 'catalog-assets');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='storage' AND tablename='objects' AND policyname='catalog_assets_update'
  ) THEN
    CREATE POLICY catalog_assets_update ON storage.objects
      FOR UPDATE TO authenticated
      USING (bucket_id = 'catalog-assets')
      WITH CHECK (bucket_id = 'catalog-assets');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='storage' AND tablename='objects' AND policyname='catalog_assets_delete'
  ) THEN
    CREATE POLICY catalog_assets_delete ON storage.objects
      FOR DELETE TO authenticated
      USING (bucket_id = 'catalog-assets');
  END IF;
END$$;
