CREATE OR REPLACE FUNCTION marketing.search_query_stats_aggregated(
  p_from date,
  p_to   date
) RETURNS TABLE (
  unified_id  text,
  frequency   bigint,
  transitions bigint,
  cart_adds   bigint,
  orders      bigint
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, crm
AS $$
  -- substitute_articles aggregations
  SELECT
    ('S' || sa.id::text) AS unified_id,
    COALESCE(SUM(m.frequency),  0) AS frequency,
    COALESCE(SUM(m.transitions),0) AS transitions,
    COALESCE(SUM(m.additions),  0) AS cart_adds,
    COALESCE(SUM(m.orders),     0) AS orders
  FROM crm.substitute_articles sa
  LEFT JOIN crm.substitute_article_metrics_weekly m
         ON m.substitute_article_id = sa.id
        AND m.week_start BETWEEN p_from AND p_to
  GROUP BY sa.id

  UNION ALL

  -- branded_queries — нет stats, заполняем нулями для consistent join
  SELECT
    ('B' || bq.id::text) AS unified_id,
    0::bigint AS frequency,
    0::bigint AS transitions,
    0::bigint AS cart_adds,
    0::bigint AS orders
  FROM crm.branded_queries bq;
$$;

GRANT EXECUTE ON FUNCTION marketing.search_query_stats_aggregated(date, date) TO authenticated, service_role;

COMMENT ON FUNCTION marketing.search_query_stats_aggregated IS
  'Aggregated weekly stats per unified search query for [p_from, p_to]. Branded queries return zero rows (no stats source). SECURITY INVOKER — relies on caller RLS on crm.* tables.';
