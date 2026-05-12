-- W5.2: header image path for модели (catalog-assets bucket)
ALTER TABLE public.modeli_osnova
  ADD COLUMN IF NOT EXISTS header_image_url TEXT;
COMMENT ON COLUMN public.modeli_osnova.header_image_url IS
  'Storage path inside catalog-assets bucket (e.g. models/123/header.jpg). Resolve via getCatalogAssetSignedUrl().';
