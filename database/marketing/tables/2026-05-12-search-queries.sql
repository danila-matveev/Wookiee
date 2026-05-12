-- WB Search Queries Sync 2.0.0 — двухуровневое хранение аналитики поисковых запросов.
--
-- Источник: WB seller-analytics-api /api/v2/search-report/product/search-texts.
-- API отдаёт по каждому (слово × nmId) счётчики openCard / addToCart / orders;
-- frequency — keyword-level метрика (общая частота слова на WB).
--
-- (1) marketing.search_queries_weekly  — недельный агрегат по ключу.
-- (2) marketing.search_query_product_breakdown — поартикульная история
--     (1 строка на неделю × слово × nmId).

-- ───────────────────────────────────────────────────────────────────────────────
-- (1) Weekly aggregate
-- ───────────────────────────────────────────────────────────────────────────────
CREATE TABLE marketing.search_queries_weekly (
  id            bigserial PRIMARY KEY,
  week_start    date NOT NULL,
  search_word   text NOT NULL,
  frequency     integer NOT NULL DEFAULT 0,
  open_card     integer NOT NULL DEFAULT 0,
  add_to_cart   integer NOT NULL DEFAULT 0,
  orders        integer NOT NULL DEFAULT 0,
  captured_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (week_start, search_word)
);

CREATE INDEX idx_sqw_week ON marketing.search_queries_weekly(week_start);
CREATE INDEX idx_sqw_word ON marketing.search_queries_weekly(search_word);

ALTER TABLE marketing.search_queries_weekly ENABLE ROW LEVEL SECURITY;

CREATE POLICY sqw_read ON marketing.search_queries_weekly
  FOR SELECT TO authenticated
  USING (true);

GRANT SELECT ON marketing.search_queries_weekly TO authenticated;
GRANT ALL    ON marketing.search_queries_weekly TO service_role;
GRANT USAGE  ON SEQUENCE marketing.search_queries_weekly_id_seq TO service_role;

COMMENT ON TABLE marketing.search_queries_weekly IS
  'Понедельный агрегат метрик поисковых запросов WB. frequency — keyword-level (общая на WB); open_card/add_to_cart/orders — счётчики по нашим карточкам, суммарно по обоим кабинетам.';

-- ───────────────────────────────────────────────────────────────────────────────
-- (2) Per-article breakdown
-- ───────────────────────────────────────────────────────────────────────────────
CREATE TABLE marketing.search_query_product_breakdown (
  id            bigserial PRIMARY KEY,
  week_start    date    NOT NULL,
  search_word   text    NOT NULL,
  nm_id         bigint  NOT NULL,
  artikul_id    integer,           -- nullable: nm_id может ещё не быть в public.artikuly
  sku_label     text,              -- denormalized cache (Charlotte/black)
  model_code    text,              -- denormalized cache (charlotte)
  open_card     integer NOT NULL DEFAULT 0,
  add_to_cart   integer NOT NULL DEFAULT 0,
  orders        integer NOT NULL DEFAULT 0,
  captured_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (week_start, search_word, nm_id)
);

CREATE INDEX idx_sqpb_week_word ON marketing.search_query_product_breakdown(week_start, search_word);
CREATE INDEX idx_sqpb_artikul   ON marketing.search_query_product_breakdown(artikul_id);
CREATE INDEX idx_sqpb_nm        ON marketing.search_query_product_breakdown(nm_id);

ALTER TABLE marketing.search_query_product_breakdown ENABLE ROW LEVEL SECURITY;

CREATE POLICY sqpb_read ON marketing.search_query_product_breakdown
  FOR SELECT TO authenticated
  USING (true);

GRANT SELECT ON marketing.search_query_product_breakdown TO authenticated;
GRANT ALL    ON marketing.search_query_product_breakdown TO service_role;
GRANT USAGE  ON SEQUENCE marketing.search_query_product_breakdown_id_seq TO service_role;

COMMENT ON TABLE marketing.search_query_product_breakdown IS
  'Поартикульная история поисковых запросов: счётчики openCard/addToCart/orders на (неделю × слово × nm_id). artikul_id nullable — резолвится через public.artikuly.nomenklatura_wb.';
COMMENT ON COLUMN marketing.search_query_product_breakdown.artikul_id IS
  'FK на public.artikuly.id; nullable, чтобы не терять данные если nm_id ещё не в каталоге.';
