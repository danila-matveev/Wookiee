-- search_queries_unified v2 — additive update of v1 (2026-05-09)
-- New columns: entity_type, channel_label, sku_label
-- Improved: model_hint via modeli_osnova JOIN
-- Preserved: source_id, source_table, group_kind, query_text, artikul_id,
--   nomenklatura_wb, ww_code, campaign_name, purpose, creator_ref, status,
--   created_at, updated_at, security_invoker, GRANTs

CREATE OR REPLACE VIEW marketing.search_queries_unified
WITH (security_invoker = true)
AS
SELECT
  ('B' || bq.id::text)::text                AS unified_id,
  bq.id                                     AS source_id,
  'branded_queries'::text                   AS source_table,
  'brand'::text                             AS entity_type,
  'brand'::text                             AS group_kind,
  bq.query                                  AS query_text,
  NULL::int                                 AS artikul_id,
  NULL::text                                AS nomenklatura_wb,
  NULL::text                                AS ww_code,
  NULL::text                                AS campaign_name,
  NULL::text                                AS purpose,
  COALESCE(
    (SELECT m.kod FROM public.modeli_osnova m WHERE m.id = bq.model_osnova_id),
    bq.canonical_brand
  )                                         AS model_hint,
  NULL::text                                AS sku_label,
  NULL::text                                AS creator_ref,
  (SELECT ch.label FROM marketing.channels ch WHERE ch.slug = 'brand') AS channel_label,
  bq.status                                 AS status,
  bq.created_at                             AS created_at,
  NULL::timestamptz                         AS updated_at
FROM crm.branded_queries bq
UNION ALL
SELECT
  ('S' || sa.id::text)::text                AS unified_id,
  sa.id                                     AS source_id,
  'substitute_articles'::text               AS source_table,
  CASE
    WHEN sa.code LIKE 'WW%'      THEN 'ww_code'
    WHEN sa.code ~ '^[0-9]+$'    THEN 'nomenclature'
    ELSE                              'other'
  END                                       AS entity_type,
  CASE
    WHEN sa.purpose = 'creators' AND sa.campaign_name ~* '^креатор[_ ]' THEN 'cr_personal'
    WHEN sa.purpose = 'creators'                                        THEN 'cr_general'
    ELSE                                                                     'external'
  END                                       AS group_kind,
  sa.code                                   AS query_text,
  sa.artikul_id                             AS artikul_id,
  sa.nomenklatura_wb                        AS nomenklatura_wb,
  CASE WHEN sa.code LIKE 'WW%' THEN sa.code ELSE NULL END AS ww_code,
  sa.campaign_name                          AS campaign_name,
  sa.purpose                                AS purpose,
  (SELECT m.kod FROM public.modeli_osnova m WHERE m.id =
    (SELECT a.model_id FROM public.artikuly a WHERE a.id = sa.artikul_id)) AS model_hint,
  (SELECT a.artikul FROM public.artikuly a WHERE a.id = sa.artikul_id) AS sku_label,
  sa.creator_ref                            AS creator_ref,
  (SELECT ch.label FROM marketing.channels ch WHERE ch.slug = sa.purpose) AS channel_label,
  sa.status                                 AS status,
  sa.created_at                             AS created_at,
  sa.updated_at                             AS updated_at
FROM crm.substitute_articles sa;

GRANT SELECT ON marketing.search_queries_unified TO authenticated, service_role;

COMMENT ON VIEW marketing.search_queries_unified IS
  'v2 (2026-05-13): adds entity_type/channel_label/sku_label, improves model_hint via modeli_osnova JOIN. Backward-compatible additive update of v1.';
