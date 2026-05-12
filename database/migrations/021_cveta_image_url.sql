-- W5.3: image path for цвета (catalog-assets bucket)
ALTER TABLE public.cveta
  ADD COLUMN IF NOT EXISTS image_url TEXT;
COMMENT ON COLUMN public.cveta.image_url IS
  'Storage path inside catalog-assets bucket (e.g. colors/45/sample.jpg). Resolve via getCatalogAssetSignedUrl().';
