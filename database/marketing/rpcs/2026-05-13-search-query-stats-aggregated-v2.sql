-- search_query_stats_aggregated v2 — JOIN on marketing.search_queries_weekly by search_word
-- Closes the "brands with zeros" bug: brands now get real metrics from the unified
-- weekly table (1396 rows after bootstrap 2026-05-12).

CREATE OR REPLACE FUNCTION marketing.search_query_stats_aggregated(p_from DATE, p_to DATE)
RETURNS TABLE (
  unified_id   TEXT,
  frequency    BIGINT,
  transitions  BIGINT,
  additions    BIGINT,
  orders       BIGINT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    u.unified_id,
    COALESCE(SUM(w.frequency),   0)::bigint AS frequency,
    COALESCE(SUM(w.open_card),   0)::bigint AS transitions,
    COALESCE(SUM(w.add_to_cart), 0)::bigint AS additions,
    COALESCE(SUM(w.orders),      0)::bigint AS orders
  FROM marketing.search_queries_unified u
  LEFT JOIN marketing.search_queries_weekly w
    ON  w.search_word = u.query_text
    AND w.week_start BETWEEN p_from AND p_to
  GROUP BY u.unified_id;
$$;

GRANT EXECUTE ON FUNCTION marketing.search_query_stats_aggregated(DATE, DATE) TO authenticated, service_role;

COMMENT ON FUNCTION marketing.search_query_stats_aggregated(DATE, DATE) IS
  'v2 (2026-05-13): JOIN on marketing.search_queries_weekly by search_word. Returns metrics for ALL entity types including brands.';
