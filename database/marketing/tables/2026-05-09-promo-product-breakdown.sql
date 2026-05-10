-- Task 2.3 — `marketing.promo_product_breakdown`: понедельная разбивка использования промокода по артикулам.
-- Заменяет text-label подход на структурированный (artikul_id NOT NULL + denormalized sku_label cache).
-- FK на crm.promo_codes(id) с CASCADE — при удалении промокода схлопывается вся разбивка.
-- FK на artikuly не добавляется: плановый таргет catalog.skus/catalog.artikuly отсутствует, public.artikuly
-- — выходящий за scope маркетинга layer; оставляем artikul_id NOT NULL без FK (Backend Important #5).

CREATE TABLE marketing.promo_product_breakdown (
  id              bigserial PRIMARY KEY,
  promo_code_id   bigint  NOT NULL REFERENCES crm.promo_codes(id) ON DELETE CASCADE,
  week_start      date    NOT NULL,
  artikul_id      integer NOT NULL,
  sku_label       text    NOT NULL,
  model_code      text,
  qty             integer NOT NULL DEFAULT 0,
  amount_rub      numeric NOT NULL DEFAULT 0,
  captured_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (promo_code_id, week_start, artikul_id)
);

CREATE INDEX idx_ppb_promo_code ON marketing.promo_product_breakdown(promo_code_id);

ALTER TABLE marketing.promo_product_breakdown ENABLE ROW LEVEL SECURITY;

CREATE POLICY ppb_read ON marketing.promo_product_breakdown
  FOR SELECT TO authenticated
  USING (true);

GRANT SELECT ON marketing.promo_product_breakdown TO authenticated;
GRANT ALL    ON marketing.promo_product_breakdown TO service_role;
GRANT USAGE  ON SEQUENCE marketing.promo_product_breakdown_id_seq TO service_role;

COMMENT ON TABLE marketing.promo_product_breakdown IS
  'Понедельная разбивка использования промокода по артикулам. ETL пишет sku_label (denormalized cache), UI читает напрямую без JOIN.';
COMMENT ON COLUMN marketing.promo_product_breakdown.artikul_id IS
  'Ссылка на артикул (источник истины public.artikuly.id; FK не добавлен — public-схема выходит за маркетинговый scope).';
