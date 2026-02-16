-- Wookiee Database Indexes
-- Optimized for common query patterns: date range, article/sku lookup, lk filtering

-- ============================================================
-- WB INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_wb_abc_date_date ON wb.abc_date(date);
CREATE INDEX IF NOT EXISTS idx_wb_abc_date_article ON wb.abc_date(article);
CREATE INDEX IF NOT EXISTS idx_wb_abc_date_date_article ON wb.abc_date(date, article);
CREATE INDEX IF NOT EXISTS idx_wb_abc_date_lk ON wb.abc_date(lk);
CREATE INDEX IF NOT EXISTS idx_wb_abc_date_nm_id ON wb.abc_date(nm_id);
CREATE INDEX IF NOT EXISTS idx_wb_abc_date_date_lk ON wb.abc_date(date, lk);

CREATE INDEX IF NOT EXISTS idx_wb_orders_date ON wb.orders(date);
CREATE INDEX IF NOT EXISTS idx_wb_orders_supplierarticle ON wb.orders(supplierarticle);
CREATE INDEX IF NOT EXISTS idx_wb_orders_nmid ON wb.orders(nmid);
CREATE INDEX IF NOT EXISTS idx_wb_orders_lk ON wb.orders(lk);

CREATE INDEX IF NOT EXISTS idx_wb_sales_date ON wb.sales(date);
CREATE INDEX IF NOT EXISTS idx_wb_sales_supplierarticle ON wb.sales(supplierarticle);
CREATE INDEX IF NOT EXISTS idx_wb_sales_nmid ON wb.sales(nmid);
CREATE INDEX IF NOT EXISTS idx_wb_sales_lk ON wb.sales(lk);

CREATE INDEX IF NOT EXISTS idx_wb_stocks_dateupdate ON wb.stocks(dateupdate);
CREATE INDEX IF NOT EXISTS idx_wb_stocks_barcode ON wb.stocks(barcode);
CREATE INDEX IF NOT EXISTS idx_wb_stocks_lk ON wb.stocks(lk);

CREATE INDEX IF NOT EXISTS idx_wb_nomenclature_vendorcode ON wb.nomenclature(vendorcode);
CREATE INDEX IF NOT EXISTS idx_wb_nomenclature_nmid ON wb.nomenclature(nmid);

CREATE INDEX IF NOT EXISTS idx_wb_content_analysis_date ON wb.content_analysis(date);
CREATE INDEX IF NOT EXISTS idx_wb_content_analysis_vendorcode ON wb.content_analysis(vendorcode);

CREATE INDEX IF NOT EXISTS idx_wb_wb_adv_date ON wb.wb_adv(date);
CREATE INDEX IF NOT EXISTS idx_wb_wb_adv_nmid ON wb.wb_adv(nmid);
CREATE INDEX IF NOT EXISTS idx_wb_wb_adv_advertid ON wb.wb_adv(advertid);

-- ============================================================
-- OZON INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_ozon_abc_date_date ON ozon.abc_date(date);
CREATE INDEX IF NOT EXISTS idx_ozon_abc_date_article ON ozon.abc_date(article);
CREATE INDEX IF NOT EXISTS idx_ozon_abc_date_date_article ON ozon.abc_date(date, article);
CREATE INDEX IF NOT EXISTS idx_ozon_abc_date_sku ON ozon.abc_date(sku);
CREATE INDEX IF NOT EXISTS idx_ozon_abc_date_lk ON ozon.abc_date(lk);
CREATE INDEX IF NOT EXISTS idx_ozon_abc_date_date_lk ON ozon.abc_date(date, lk);

CREATE INDEX IF NOT EXISTS idx_ozon_orders_in_process_at ON ozon.orders(in_process_at);
CREATE INDEX IF NOT EXISTS idx_ozon_orders_offer_id ON ozon.orders(offer_id);
CREATE INDEX IF NOT EXISTS idx_ozon_orders_sku ON ozon.orders(sku);
CREATE INDEX IF NOT EXISTS idx_ozon_orders_lk ON ozon.orders(lk);

CREATE INDEX IF NOT EXISTS idx_ozon_returns_operation_date ON ozon.returns(operation_date);
CREATE INDEX IF NOT EXISTS idx_ozon_returns_sku ON ozon.returns(sku);
CREATE INDEX IF NOT EXISTS idx_ozon_returns_lk ON ozon.returns(lk);

CREATE INDEX IF NOT EXISTS idx_ozon_stocks_dateupdate ON ozon.stocks(dateupdate);
CREATE INDEX IF NOT EXISTS idx_ozon_stocks_sku ON ozon.stocks(sku);
CREATE INDEX IF NOT EXISTS idx_ozon_stocks_lk ON ozon.stocks(lk);

CREATE INDEX IF NOT EXISTS idx_ozon_nomenclature_article ON ozon.nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_ozon_nomenclature_ozon_product_id ON ozon.nomenclature(ozon_product_id);

CREATE INDEX IF NOT EXISTS idx_ozon_adv_stats_daily_date ON ozon.adv_stats_daily(operation_date);
CREATE INDEX IF NOT EXISTS idx_ozon_adv_stats_daily_id_rk ON ozon.adv_stats_daily(id_rk);

CREATE INDEX IF NOT EXISTS idx_ozon_adv_api_date ON ozon.ozon_adv_api(operation_date);
CREATE INDEX IF NOT EXISTS idx_ozon_adv_api_sku ON ozon.ozon_adv_api(sku);
