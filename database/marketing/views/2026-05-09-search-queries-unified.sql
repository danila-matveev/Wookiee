CREATE OR REPLACE VIEW marketing.search_queries_unified
WITH (security_invoker = true)
AS
SELECT
  ('B' || bq.id::text)::text          AS unified_id,
  bq.id                                AS source_id,
  'branded_queries'::text              AS source_table,
  'brand'::text                        AS group_kind,
  bq.query                             AS query_text,
  NULL::int                            AS artikul_id,
  NULL::text                           AS nomenklatura_wb,
  NULL::text                           AS ww_code,
  NULL::text                           AS campaign_name,
  NULL::text                           AS purpose,
  bq.canonical_brand                   AS model_hint,
  NULL::text                           AS creator_ref,
  bq.status                            AS status,
  bq.created_at                        AS created_at,
  NULL::timestamptz                    AS updated_at
FROM crm.branded_queries bq
UNION ALL
SELECT
  ('S' || sa.id::text)::text           AS unified_id,
  sa.id                                AS source_id,
  'substitute_articles'::text          AS source_table,
  CASE
    WHEN sa.purpose = 'creators' AND sa.campaign_name ~* '^креатор[_ ]'   THEN 'cr_personal'
    WHEN sa.purpose = 'creators'                                          THEN 'cr_general'
    ELSE                                                                       'external'
  END                                  AS group_kind,
  sa.code                              AS query_text,
  sa.artikul_id                        AS artikul_id,
  sa.nomenklatura_wb                   AS nomenklatura_wb,
  CASE WHEN sa.code LIKE 'WW%' THEN sa.code ELSE NULL END AS ww_code,
  sa.campaign_name                     AS campaign_name,
  sa.purpose                           AS purpose,
  NULL::text                           AS model_hint,
  sa.creator_ref                       AS creator_ref,
  sa.status                            AS status,
  sa.created_at                        AS created_at,
  sa.updated_at                        AS updated_at
FROM crm.substitute_articles sa;

GRANT SELECT ON marketing.search_queries_unified TO authenticated, service_role;

COMMENT ON VIEW marketing.search_queries_unified IS
  'Unified read-layer for marketing search queries. UNION of brand_queries + substitute_articles. group_kind computed: brand|cr_personal|cr_general|external. Returns source_table + source_id directly (no client-side composite-id parse).';
