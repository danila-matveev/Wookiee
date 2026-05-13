-- search_query_stats_aggregated v3 — extended JOIN-key
-- v2 (B.0.2) joined only on query_text = search_word.
-- On production:
--   * crm.branded_queries is empty (0 brand-rows in unified)
--   * crm.substitute_articles.code stores human labels ("Wendy/white",
--     "163 152 029" with spaces) while marketing.search_queries_weekly.search_word
--     stores clean numeric nm_id strings ("163151603", ...).
--   * Result: query_text = search_word matches 0 rows on real data.
--
-- v3 adds a second JOIN key via nomenklatura_wb, which is clean numeric
-- nm_id and matches search_word directly. This recovers metrics for
-- substitute_articles entries that have nomenklatura_wb populated (~10 today).
-- Brand rows and WW-style codes remain at zero — separate Phase 3 follow-up
-- (data ops: backfill branded_queries, add WW→nm mapping).

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
    ON (
         w.search_word = u.query_text
         OR (u.nomenklatura_wb IS NOT NULL AND w.search_word = u.nomenklatura_wb)
       )
   AND w.week_start BETWEEN p_from AND p_to
  GROUP BY u.unified_id;
$$;

GRANT EXECUTE ON FUNCTION marketing.search_query_stats_aggregated(DATE, DATE) TO authenticated, service_role;

COMMENT ON FUNCTION marketing.search_query_stats_aggregated(DATE, DATE) IS
  'v3 (2026-05-13-rework): JOIN by query_text OR nomenklatura_wb. Recovers metrics for substitute_articles whose code is a label (e.g. "Wendy/white") via their nm_id. Brand rows and WW-codes still need Phase 3 data-ops follow-up.';
