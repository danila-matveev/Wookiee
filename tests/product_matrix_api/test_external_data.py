"""Tests for external data integration (stock + finance endpoints)."""
from datetime import timedelta
import pytest
from services.product_matrix_api.models.schemas import (
    StockChannel, MoySkladStock, StockResponse,
    ExpenseItem, DRR, FinanceChannel, FinanceDelta, FinanceResponse,
)


def test_stock_response_with_null_channels():
    """StockResponse accepts null wb/ozon/moysklad."""
    resp = StockResponse(
        entity_type="models_osnova", entity_id=1, entity_name="Vuki",
        period_days=30, wb=None, ozon=None, moysklad=None,
        total_stock=0, total_turnover_days=None,
    )
    assert resp.wb is None
    assert resp.total_stock == 0


def test_stock_response_with_data():
    """StockResponse with all channels populated."""
    wb = StockChannel(stock_mp=142, daily_sales=34.2, turnover_days=4.2, sales_count=1045, days_in_stock=28)
    ozon = StockChannel(stock_mp=38, daily_sales=5.1, turnover_days=7.5, sales_count=152, days_in_stock=28)
    ms = MoySkladStock(stock_main=230, stock_transit=85, total=315, snapshot_date="2026-03-20", is_stale=False)
    resp = StockResponse(
        entity_type="models_osnova", entity_id=1, entity_name="Vuki",
        period_days=30, wb=wb, ozon=ozon, moysklad=ms,
        total_stock=495, total_turnover_days=12.6,
    )
    assert resp.wb.stock_mp == 142
    assert resp.moysklad.total == 315


def test_finance_response_with_expenses():
    """FinanceChannel with expenses dict and DRR."""
    expenses = {
        "commission": ExpenseItem(value=511900, pct=37.8, delta_value=452, delta_pct=-0.2),
        "logistics": ExpenseItem(value=126300, pct=9.3, delta_value=-2800, delta_pct=-0.3),
        "cost_price": ExpenseItem(value=262400, pct=19.4, delta_value=104, delta_pct=-0.1),
        "advertising": ExpenseItem(value=32900, pct=2.4, delta_value=-7400, delta_pct=-0.6),
        "storage": ExpenseItem(value=31700, pct=2.3, delta_value=-542, delta_pct=-0.1),
        "nds": ExpenseItem(value=42800, pct=3.2, delta_value=1200, delta_pct=0.1),
        "other": ExpenseItem(value=10700, pct=0.8, delta_value=-5100, delta_pct=-0.4),
    }
    ch = FinanceChannel(
        revenue_before_spp=1370000, revenue_after_spp=898556,
        margin=332000, margin_pct=24.5,
        orders_count=1045, orders_sum=2000000,
        sales_count=745, sales_sum=1400000,
        avg_check_before_spp=1816, avg_check_after_spp=1206,
        spp_pct=33.2, buyout_pct=71.3, returns_count=9, returns_pct=1.2,
        expenses=expenses, drr=DRR(total=2.6, internal=2.1, external=0.5),
    )
    assert ch.expenses["commission"].value == 511900
    assert ch.drr.total == 2.6


from unittest.mock import MagicMock, patch, PropertyMock
from services.product_matrix_api.services.external_data import (
    resolve_marketplace_key, MarketplaceKey,
    ENTITIES_WITH_MP_DATA,
)


class TestResolveMarketplaceKey:
    def _mock_db(self):
        return MagicMock()

    def test_models_osnova_uses_kod(self):
        db = self._mock_db()
        record = MagicMock()
        record.kod = "Vuki"
        db.get.return_value = record

        key = resolve_marketplace_key("models_osnova", 1, db)
        assert key.level == "model"
        assert key.key == "vuki"

    def test_models_uses_kod(self):
        db = self._mock_db()
        record = MagicMock()
        record.kod = "VukiN"
        db.get.return_value = record

        key = resolve_marketplace_key("models", 1, db)
        assert key.level == "model"
        assert key.key == "vukin"

    def test_articles_uses_artikul(self):
        db = self._mock_db()
        record = MagicMock()
        record.artikul = "\u043a\u043e\u043c\u043f\u0431\u0435\u043b-\u0436-\u0431\u0435\u0441\u0448\u043e\u0432/\u0447\u0435\u0440"
        db.get.return_value = record

        key = resolve_marketplace_key("articles", 1, db)
        assert key.level == "article"
        assert key.key == "\u043a\u043e\u043c\u043f\u0431\u0435\u043b-\u0436-\u0431\u0435\u0441\u0448\u043e\u0432/\u0447\u0435\u0440"

    def test_products_uses_barkod(self):
        db = self._mock_db()
        record = MagicMock()
        record.barkod = "2000989949060"
        db.get.return_value = record

        key = resolve_marketplace_key("products", 1, db)
        assert key.level == "barcode"
        assert key.key == "2000989949060"

    def test_cards_wb_traverses_m2m(self):
        db = self._mock_db()
        record = MagicMock()
        t1, t2 = MagicMock(), MagicMock()
        t1.barkod = "2000989949060"
        t2.barkod = "2010165489006"
        record.tovary = [t1, t2]
        db.get.return_value = record

        key = resolve_marketplace_key("cards_wb", 1, db)
        assert key.level == "barcode_list"
        assert key.keys == ["2000989949060", "2010165489006"]
        assert key.channel == "wb"

    def test_unsupported_entity_raises(self):
        db = self._mock_db()
        with pytest.raises(ValueError, match="no marketplace mapping"):
            resolve_marketplace_key("colors", 1, db)

    def test_entities_with_mp_data_constant(self):
        assert "models_osnova" in ENTITIES_WITH_MP_DATA
        assert "colors" not in ENTITIES_WITH_MP_DATA
        assert "factories" not in ENTITIES_WITH_MP_DATA


from fastapi.testclient import TestClient
from services.product_matrix_api.app import app

client = TestClient(app)


class TestStockEndpoint:
    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_cached_bulk")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_stock_model_level(self, mock_resolve, mock_bulk, mock_db):
        """GET /api/matrix/models_osnova/1/stock returns stock data."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        mock_resolve.return_value = MarketplaceKey(level="model", key="vuki")
        mock_bulk.side_effect = lambda name, *args: {
            "wb_turnover": {"vuki": {"avg_stock": 142, "stock_mp": 142, "stock_moysklad": 0, "stock_transit": 0, "daily_sales": 34.2, "turnover_days": 4.2, "sales_count": 1045, "days_in_stock": 28, "revenue": 1370000, "margin": 332000, "low_sales": False}},
            "ozon_turnover": {"vuki": {"avg_stock": 38, "stock_mp": 38, "stock_moysklad": 0, "stock_transit": 0, "daily_sales": 5.1, "turnover_days": 7.5, "sales_count": 152, "days_in_stock": 28, "revenue": 200000, "margin": 40000, "low_sales": False}},
            "moysklad": {"vuki": {"stock_main": 230, "stock_transit": 85, "total": 315, "snapshot_date": "2026-03-20", "is_stale": False}},
        }[name]

        resp = client.get("/api/matrix/models_osnova/1/stock?period=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "models_osnova"
        assert data["wb"]["stock_mp"] == 142
        assert data["ozon"]["stock_mp"] == 38
        assert data["moysklad"]["stock_main"] == 230
        assert data["total_stock"] == 495  # 142 + 38 + 315

    @patch("services.product_matrix_api.routes.external_data.get_db")
    def test_stock_unsupported_entity_returns_404(self, mock_db):
        """GET /api/matrix/colors/1/stock returns 404."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        resp = client.get("/api/matrix/colors/1/stock")
        assert resp.status_code == 404

    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_cached_bulk")
    @patch("services.product_matrix_api.services.external_data._get_cached_ms_article")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_stock_article_level(self, mock_resolve, mock_ms, mock_bulk, mock_db):
        """GET /api/matrix/articles/1/stock returns article-level stock."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        mock_resolve.return_value = MarketplaceKey(level="article", key="vuki/black")

        def bulk_side_effect(name, *args):
            return {
                "wb_avg_stock": {"vuki/black": 50.0},
                "ozon_avg_stock": {"vuki/black": 20.0},
                "wb_by_article": [{"article": "vuki/black", "model": "vuki", "sales_count": 120, "revenue": 50000, "margin": 10000}],
                "ozon_by_article": [{"article": "vuki/black", "model": "vuki", "sales_count": 30, "revenue": 15000, "margin": 3000}],
            }[name]

        mock_bulk.side_effect = bulk_side_effect
        mock_ms.return_value = {
            "vuki/black": {"stock_main": 100, "stock_transit": 25, "total": 125,
                           "snapshot_date": "2026-03-20", "is_stale": False},
        }

        resp = client.get("/api/matrix/articles/1/stock?period=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"]["stock_mp"] == 50.0
        assert data["ozon"]["stock_mp"] == 20.0
        assert data["moysklad"]["stock_main"] == 100
        assert data["moysklad"]["total"] == 125
        assert data["total_stock"] == 195.0  # 50 + 20 + 125

    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_wb_barcode_stock")
    @patch("services.product_matrix_api.services.external_data._get_ozon_barcode_stock")
    @patch("services.product_matrix_api.services.external_data._get_wb_barcode_daily_sales")
    @patch("services.product_matrix_api.services.external_data._get_ozon_barcode_daily_sales")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_stock_barcode_level(self, mock_resolve, mock_ozon_sales, mock_wb_sales,
                                  mock_ozon_stock, mock_wb_stock, mock_db):
        """GET /api/matrix/products/1/stock returns barcode-level stock."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        mock_resolve.return_value = MarketplaceKey(level="barcode", key="2000989949060")
        mock_wb_stock.return_value = {"2000989949060": 15.0}
        mock_ozon_stock.return_value = {"2000989949060": 5.0}
        mock_wb_sales.return_value = {"2000989949060": 60.0}
        mock_ozon_sales.return_value = {"2000989949060": 10.0}

        resp = client.get("/api/matrix/products/1/stock?period=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"]["stock_mp"] == 15.0
        assert data["ozon"]["stock_mp"] == 5.0
        assert data["moysklad"] is None  # Not available at barcode level
        assert data["total_stock"] == 20.0

    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_wb_barcode_stock")
    @patch("services.product_matrix_api.services.external_data._get_ozon_barcode_stock")
    @patch("services.product_matrix_api.services.external_data._get_wb_barcode_daily_sales")
    @patch("services.product_matrix_api.services.external_data._get_ozon_barcode_daily_sales")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_stock_barcode_list_wb_only(self, mock_resolve, mock_ozon_sales, mock_wb_sales,
                                         mock_ozon_stock, mock_wb_stock, mock_db):
        """cards_wb should only fetch WB data."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        mock_resolve.return_value = MarketplaceKey(
            level="barcode_list", keys=["2000989949060", "2010165489006"], channel="wb")
        mock_wb_stock.return_value = {"2000989949060": 10.0, "2010165489006": 8.0}
        mock_wb_sales.return_value = {"2000989949060": 30.0, "2010165489006": 20.0}

        resp = client.get("/api/matrix/cards_wb/1/stock?period=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"]["stock_mp"] == 18.0
        assert data["ozon"] is None
        # Should not have called ozon functions
        mock_ozon_stock.assert_not_called()
        mock_ozon_sales.assert_not_called()


class TestFinanceEndpoint:
    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_full_wb_finance")
    @patch("services.product_matrix_api.services.external_data._get_full_ozon_finance")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_finance_model_level(self, mock_resolve, mock_ozon_fin, mock_wb_fin, mock_db):
        """GET /api/matrix/models_osnova/1/finance returns finance data."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_resolve.return_value = MarketplaceKey(level="model", key="vuki")

        # Mock WB finance: sales_data tuple + orders_data tuple
        mock_wb_fin.return_value = (
            [("current", 745, 1370000, 898556, 30000, 2900, 262400, 126300, 31700, 511900, 471444, 42800, 1000, 500, 200, 332000, 13589, 0)],
            [("current", 1045, 2000000)],
        )
        mock_ozon_fin.return_value = ([], [])

        resp = client.get("/api/matrix/models_osnova/1/finance?period=7&compare=none")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"] is not None
        assert data["wb"]["revenue_before_spp"] == 1370000
        assert data["wb"]["margin"] == 332000
        assert data["wb"]["orders_count"] == 1045
        assert "commission" in data["wb"]["expenses"]
        assert data["ozon"] is None

    @patch("services.product_matrix_api.routes.external_data.get_db")
    def test_finance_unsupported_entity_returns_404(self, mock_db):
        """GET /api/matrix/factories/1/finance returns 404."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        resp = client.get("/api/matrix/factories/1/finance")
        assert resp.status_code == 404

    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_article_wb_finance")
    @patch("services.product_matrix_api.services.external_data._get_article_ozon_finance")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_finance_article_level(self, mock_resolve, mock_ozon_fin, mock_wb_fin, mock_db):
        """GET /api/matrix/articles/1/finance returns article-level finance."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_resolve.return_value = MarketplaceKey(level="article", key="vuki/black")

        mock_wb_fin.return_value = (
            [("current", 200, 500000, 350000, 10000, 1000, 80000, 40000, 10000, 180000, 150000, 15000, 300, 100, 50, 120000, 5000, 0)],
            [("current", 300, 700000)],
        )
        mock_ozon_fin.return_value = ([], [])

        resp = client.get("/api/matrix/articles/1/finance?period=7&compare=none")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"] is not None
        assert data["wb"]["sales_count"] == 200
        assert data["wb"]["revenue_before_spp"] == 500000
        assert data["ozon"] is None

    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_cached_bulk")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_finance_barcode_level(self, mock_resolve, mock_bulk, mock_db):
        """GET /api/matrix/products/1/finance returns barcode-level finance."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_resolve.return_value = MarketplaceKey(level="barcode", key="2000989949060")

        def bulk_side_effect(name, *args):
            return {
                "wb_fin_barcode": [
                    {"barcode": "2000989949060", "sales_count": 50, "revenue_before_spp": 100000,
                     "revenue_after_spp": 70000, "margin": 25000, "commission": 35000,
                     "logistics": 12000, "cost_of_goods": 20000, "adv_internal": 5000,
                     "adv_external": 500, "storage": 3000, "nds": 4000,
                     "penalty": 100, "retention": 50, "deduction": 20,
                     "returns_revenue": 2000},
                ],
                "wb_orders_barcode": {
                    "2000989949060": {"orders_count": 70, "orders_rub": 150000},
                },
                "ozon_fin_barcode": [],
                "ozon_orders_barcode": {},
            }[name]

        mock_bulk.side_effect = bulk_side_effect

        resp = client.get("/api/matrix/products/1/finance?period=7&compare=none")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"] is not None
        assert data["wb"]["sales_count"] == 50
        assert data["wb"]["revenue_before_spp"] == 100000
        assert data["wb"]["orders_count"] == 70
        assert data["ozon"] is None

    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_cached_bulk")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_finance_barcode_list_wb_only(self, mock_resolve, mock_bulk, mock_db):
        """cards_wb finance should only fetch WB data."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_resolve.return_value = MarketplaceKey(
            level="barcode_list", keys=["BC1", "BC2"], channel="wb")

        call_names = []

        def bulk_side_effect(name, *args):
            call_names.append(name)
            return {
                "wb_fin_barcode": [
                    {"barcode": "BC1", "sales_count": 30, "revenue_before_spp": 60000,
                     "revenue_after_spp": 42000, "margin": 15000, "commission": 20000,
                     "logistics": 7000, "cost_of_goods": 12000, "adv_internal": 3000,
                     "adv_external": 300, "storage": 2000, "nds": 2500,
                     "penalty": 50, "retention": 25, "deduction": 10,
                     "returns_revenue": 1000},
                    {"barcode": "BC2", "sales_count": 20, "revenue_before_spp": 40000,
                     "revenue_after_spp": 28000, "margin": 10000, "commission": 14000,
                     "logistics": 5000, "cost_of_goods": 8000, "adv_internal": 2000,
                     "adv_external": 200, "storage": 1500, "nds": 1500,
                     "penalty": 30, "retention": 15, "deduction": 5,
                     "returns_revenue": 500},
                ],
                "wb_orders_barcode": {
                    "BC1": {"orders_count": 40, "orders_rub": 80000},
                    "BC2": {"orders_count": 25, "orders_rub": 50000},
                },
            }[name]

        mock_bulk.side_effect = bulk_side_effect

        resp = client.get("/api/matrix/cards_wb/1/finance?period=7&compare=none")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"] is not None
        # Aggregated: 30+20=50 sales
        assert data["wb"]["sales_count"] == 50
        assert data["wb"]["revenue_before_spp"] == 100000  # 60000+40000
        assert data["wb"]["orders_count"] == 65  # 40+25
        assert data["ozon"] is None
        # Should not have called ozon bulk funcs
        assert not any("ozon" in n for n in call_names)


from datetime import date
from services.product_matrix_api.services.external_data import _calc_dates, _bulk_cache, _get_cached_bulk


class TestCalcDates:
    def test_week_comparison(self):
        """period=7, compare=week produces correct date ranges."""
        cs, ps, ce, cpe = _calc_dates(7, "week")
        today = date.today()
        assert cs == (today - timedelta(days=7)).isoformat()
        assert ce == today.isoformat()
        assert ps == (today - timedelta(days=14)).isoformat()
        assert cpe == cs

    def test_month_comparison(self):
        """period=7, compare=month produces 30-day lookback for prev."""
        cs, ps, ce, cpe = _calc_dates(7, "month")
        today = date.today()
        assert ps == (today - timedelta(days=37)).isoformat()
        assert cpe == cs

    def test_no_comparison(self):
        """compare=none means prev_start == current_start, no compare_end."""
        cs, ps, ce, cpe = _calc_dates(7, "none")
        assert ps == cs
        assert cpe is None


class TestBulkCaching:
    def setup_method(self):
        _bulk_cache.clear()

    @patch("services.product_matrix_api.services.external_data._BULK_FUNCS", {
        "test_func": MagicMock(return_value={"key1": {"val": 10}}),
    })
    def test_second_call_uses_cache(self):
        """Second call with same args doesn't invoke the underlying function."""
        from services.product_matrix_api.services.external_data import _BULK_FUNCS
        func = _BULK_FUNCS["test_func"]

        result1 = _get_cached_bulk("test_func", "2026-01-01", "2026-01-30")
        result2 = _get_cached_bulk("test_func", "2026-01-01", "2026-01-30")

        assert result1 == result2
        assert func.call_count == 1

    @patch("services.product_matrix_api.services.external_data._BULK_FUNCS", {
        "test_func": MagicMock(return_value={"key1": {"val": 10}}),
    })
    def test_different_args_calls_again(self):
        """Different args produce a separate cache entry."""
        from services.product_matrix_api.services.external_data import _BULK_FUNCS
        func = _BULK_FUNCS["test_func"]

        _get_cached_bulk("test_func", "2026-01-01", "2026-01-30")
        _get_cached_bulk("test_func", "2026-02-01", "2026-02-28")

        assert func.call_count == 2


class TestBuildFinanceFromBarcodeDicts:
    """Tests for _build_finance_channel_from_barcode_dicts helper."""

    def test_empty_rows_returns_none(self):
        from services.product_matrix_api.services.external_data import (
            _build_finance_channel_from_barcode_dicts,
        )
        result = _build_finance_channel_from_barcode_dicts([], {}, ["BC1"])
        assert result is None

    def test_single_barcode(self):
        from services.product_matrix_api.services.external_data import (
            _build_finance_channel_from_barcode_dicts,
        )
        fin_rows = [
            {"barcode": "BC1", "sales_count": 50, "revenue_before_spp": 100000,
             "revenue_after_spp": 70000, "margin": 25000, "commission": 35000,
             "logistics": 12000, "cost_of_goods": 20000, "adv_internal": 5000,
             "adv_external": 500, "storage": 3000, "nds": 4000,
             "penalty": 100, "retention": 50, "deduction": 20,
             "returns_revenue": 2000},
        ]
        orders_map = {"BC1": {"orders_count": 70, "orders_rub": 150000}}
        result = _build_finance_channel_from_barcode_dicts(fin_rows, orders_map, ["BC1"])
        assert result is not None
        assert result.sales_count == 50
        assert result.orders_count == 70
        assert result.revenue_before_spp == 100000

    def test_aggregates_multiple_barcodes(self):
        from services.product_matrix_api.services.external_data import (
            _build_finance_channel_from_barcode_dicts,
        )
        fin_rows = [
            {"barcode": "BC1", "sales_count": 30, "revenue_before_spp": 60000,
             "revenue_after_spp": 42000, "margin": 15000, "commission": 20000,
             "logistics": 7000, "cost_of_goods": 12000, "adv_internal": 3000,
             "adv_external": 300, "storage": 2000, "nds": 2500,
             "penalty": 50, "retention": 25, "deduction": 10,
             "returns_revenue": 1000},
            {"barcode": "BC2", "sales_count": 20, "revenue_before_spp": 40000,
             "revenue_after_spp": 28000, "margin": 10000, "commission": 14000,
             "logistics": 5000, "cost_of_goods": 8000, "adv_internal": 2000,
             "adv_external": 200, "storage": 1500, "nds": 1500,
             "penalty": 30, "retention": 15, "deduction": 5,
             "returns_revenue": 500},
            {"barcode": "OTHER", "sales_count": 100, "revenue_before_spp": 200000,
             "revenue_after_spp": 140000, "margin": 50000, "commission": 70000,
             "logistics": 25000, "cost_of_goods": 40000, "adv_internal": 10000,
             "adv_external": 1000, "storage": 6000, "nds": 5000,
             "penalty": 200, "retention": 100, "deduction": 40,
             "returns_revenue": 4000},
        ]
        orders_map = {
            "BC1": {"orders_count": 40, "orders_rub": 80000},
            "BC2": {"orders_count": 25, "orders_rub": 50000},
            "OTHER": {"orders_count": 130, "orders_rub": 300000},
        }
        result = _build_finance_channel_from_barcode_dicts(
            fin_rows, orders_map, ["BC1", "BC2"])
        assert result is not None
        assert result.sales_count == 50  # 30 + 20
        assert result.orders_count == 65  # 40 + 25
        assert result.revenue_before_spp == 100000  # 60k + 40k

    def test_ozon_uses_returns_count(self):
        from services.product_matrix_api.services.external_data import (
            _build_finance_channel_from_barcode_dicts,
        )
        fin_rows = [
            {"barcode": "BC1", "sales_count": 50, "revenue_before_spp": 100000,
             "revenue_after_spp": 70000, "margin": 25000, "commission": 35000,
             "logistics": 12000, "cost_of_goods": 20000, "adv_internal": 5000,
             "adv_external": 500, "storage": 3000, "nds": 4000,
             "returns_count": 7, "returns_revenue": 2000},
        ]
        orders_map = {"BC1": {"orders_count": 70, "orders_rub": 150000}}
        result = _build_finance_channel_from_barcode_dicts(
            fin_rows, orders_map, ["BC1"], is_ozon=True)
        assert result is not None
        assert result.returns_count == 7
