"""
Tests for ETL transform logic.

Focuses on transform methods (pure data mapping, no I/O).
Tests verify field mapping correctness and aggregation formulas.
"""

import unittest
from unittest.mock import MagicMock, patch

from services.marketplace_etl.etl.wb_etl import WildberriesETL
from services.marketplace_etl.etl.ozon_etl import OzonETL


def _make_wb_etl():
    """Create WB ETL with a mock client (no real API calls)."""
    etl = WildberriesETL.__new__(WildberriesETL)
    etl.client = MagicMock()
    etl.lk = 'Test LK'
    return etl


def _make_ozon_etl():
    """Create Ozon ETL with a mock client (no real API calls)."""
    etl = OzonETL.__new__(OzonETL)
    etl.client = MagicMock()
    etl.lk = 'Test LK'
    return etl


# ======================================================================
# WB Transform Tests
# ======================================================================

class TestWBTransformReportDetail(unittest.TestCase):
    """Test _transform_report_detail aggregation."""

    def test_empty_records(self):
        etl = _make_wb_etl()
        result = etl._transform_report_detail([])
        self.assertEqual(result, [])

    def test_single_record(self):
        etl = _make_wb_etl()
        records = [{
            'rr_dt': '2026-02-01T00:00:00',
            'sa_name': 'ART1',
            'barcode': '123456',
            'nm_id': 100,
            'ts_name': 'TestShirt',
            'doc_type_name': 'Продажа',
            'quantity': 1,
            'ppvz_for_pay': 1000,
            'retail_amount': 1500,
            'delivery_rub': 50,
            'ppvz_vw_nds': 200,
            'penalty': 0,
            'additional_payment': 0,
            'storage_fee': 10,
            'deduction': 0,
            'acceptance': 5,
            'retail_price': 2000,
            'rebill_logistic_cost': 0,
            'ppvz_spp_prc': 15,
            'rrd_id': 1,
        }]
        result = etl._transform_report_detail(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['date'], '2026-02-01')
        self.assertEqual(row['article'], 'ART1')
        self.assertEqual(row['barcode'], '123456')
        self.assertEqual(row['lk'], 'Test LK')
        self.assertEqual(row['mp'], 'wb')
        self.assertEqual(row['revenue_spp'], 1500)
        self.assertEqual(row['full_counts'], 1)
        self.assertEqual(row['count_return'], 0)
        self.assertEqual(row['comis_spp'], 200)
        self.assertEqual(row['logist'], 50)
        self.assertEqual(row['storage'], 10)
        self.assertEqual(row['penalty'], 0)
        self.assertEqual(row['retention'], 5)
        self.assertEqual(row['sebes'], 0)  # Not from API
        self.assertEqual(row['reclama'], 0)  # Not from API

    def test_aggregation_by_key(self):
        """Two records with same (date, article, barcode) should be aggregated."""
        etl = _make_wb_etl()
        records = [
            {
                'rr_dt': '2026-02-01', 'sa_name': 'ART1', 'barcode': '123',
                'nm_id': 1, 'ts_name': '', 'doc_type_name': 'Продажа',
                'quantity': 1, 'ppvz_for_pay': 500, 'retail_amount': 700,
                'delivery_rub': 30, 'ppvz_vw_nds': 100, 'penalty': 0,
                'additional_payment': 0, 'storage_fee': 5, 'deduction': 0,
                'acceptance': 0, 'retail_price': 1000, 'rebill_logistic_cost': 0,
                'ppvz_spp_prc': 0,
            },
            {
                'rr_dt': '2026-02-01', 'sa_name': 'ART1', 'barcode': '123',
                'nm_id': 1, 'ts_name': '', 'doc_type_name': 'Продажа',
                'quantity': 2, 'ppvz_for_pay': 1000, 'retail_amount': 1400,
                'delivery_rub': 60, 'ppvz_vw_nds': 200, 'penalty': 0,
                'additional_payment': 0, 'storage_fee': 10, 'deduction': 0,
                'acceptance': 0, 'retail_price': 1000, 'rebill_logistic_cost': 0,
                'ppvz_spp_prc': 0,
            },
        ]
        result = etl._transform_report_detail(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['revenue_spp'], 2100)  # 700 + 1400
        self.assertEqual(row['comis_spp'], 300)  # 100 + 200
        self.assertEqual(row['logist'], 90)  # 30 + 60
        self.assertEqual(row['storage'], 15)  # 5 + 10
        self.assertEqual(row['full_counts'], 3)  # 1 + 2

    def test_returns_counted_separately(self):
        """Return records should increment count_return, not full_counts."""
        etl = _make_wb_etl()
        records = [
            {
                'rr_dt': '2026-02-01', 'sa_name': 'ART1', 'barcode': '123',
                'nm_id': 1, 'ts_name': '', 'doc_type_name': 'Возврат',
                'quantity': 1, 'ppvz_for_pay': -500, 'retail_amount': 0,
                'delivery_rub': 0, 'ppvz_vw_nds': 0, 'penalty': 0,
                'additional_payment': 0, 'storage_fee': 0, 'deduction': 0,
                'acceptance': 0, 'retail_price': 0, 'rebill_logistic_cost': 0,
                'ppvz_spp_prc': 0,
            },
        ]
        result = etl._transform_report_detail(records)
        row = result[0]
        self.assertEqual(row['count_return'], 1)
        self.assertEqual(row['full_counts'], 0)


class TestWBTransformOrders(unittest.TestCase):
    """Test _transform_orders field mapping."""

    def test_basic_mapping(self):
        etl = _make_wb_etl()
        records = [{
            'date': '2026-02-01',
            'lastChangeDate': '2026-02-01T10:00:00',
            'supplierArticle': 'ART1',
            'techSize': 'M',
            'barcode': '123',
            'totalPrice': 1500,
            'discountPercent': 10,
            'spp': 5,
            'finishedPrice': 1350,
            'priceWithDisc': 1350,
            'warehouseName': 'WH1',
            'oblast': 'Moscow',
            'region': 'Central',
            'regionName': 'Moscow',
            'country': 'Russia',
            'nmId': 100,
            'subject': 'Shirts',
            'category': 'Clothing',
            'brand': 'TestBrand',
            'isCancel': False,
            'cancel_dt': None,
            'gNumber': 'G123',
            'sticker': '',
            'srid': 'SRID1',
            'orderType': 'Клиентский',
        }]
        result = etl._transform_orders(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['supplierarticle'], 'ART1')
        self.assertEqual(row['nmid'], 100)
        self.assertEqual(row['lk'], 'Test LK')
        self.assertEqual(row['srid'], 'SRID1')


class TestWBTransformSales(unittest.TestCase):
    """Test _transform_sales field mapping."""

    def test_basic_mapping(self):
        etl = _make_wb_etl()
        records = [{
            'date': '2026-02-01',
            'lastChangeDate': '2026-02-01',
            'supplierArticle': 'ART1',
            'techSize': 'L',
            'barcode': '456',
            'totalPrice': 2000,
            'discountPercent': 5,
            'spp': 3,
            'forPay': 1800,
            'finishedPrice': 1900,
            'priceWithDisc': 1900,
            'warehouseName': 'WH2',
            'countryName': 'Russia',
            'oblastOkrugName': 'Central',
            'regionName': 'SPb',
            'nmId': 200,
            'subject': 'Pants',
            'category': 'Clothing',
            'brand': 'Brand2',
            'IsStorno': 0,
            'gNumber': 'G456',
            'saleID': 'SALE1',
            'srid': 'SRID2',
            'paymentSaleAmount': 1800,
        }]
        result = etl._transform_sales(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['forpay'], 1800)
        self.assertEqual(row['saleid'], 'SALE1')
        self.assertEqual(row['lk'], 'Test LK')


class TestWBTransformStocks(unittest.TestCase):
    """Test _transform_stocks field mapping."""

    def test_basic_mapping(self):
        etl = _make_wb_etl()
        records = [{
            'lastChangeDate': '2026-02-01',
            'supplierArticle': 'ART1',
            'techSize': 'S',
            'barcode': '789',
            'quantity': 50,
            'isSupply': True,
            'isRealization': False,
            'quantityFull': 55,
            'warehouseName': 'WH3',
            'nmId': 300,
            'subject': 'Socks',
            'category': 'Accessories',
            'daysOnSite': 30,
            'brand': 'Brand3',
            'SCCode': 'SC1',
            'Price': 500,
            'Discount': 10,
        }]
        result = etl._transform_stocks(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['quantity'], 50)
        self.assertEqual(row['quantityfull'], 55)
        self.assertEqual(row['lk'], 'Test LK')


class TestWBTransformAdv(unittest.TestCase):
    """Test _transform_adv nested structure flattening."""

    def test_nested_structure(self):
        etl = _make_wb_etl()
        records = [{
            'advertId': 1001,
            'name': 'Campaign1',
            'days': [{
                'date': '2026-02-01T00:00:00',
                'apps': [{
                    'nm': [{
                        'nmId': 100,
                        'views': 500,
                        'clicks': 20,
                        'sum': 1000,
                        'atbs': 5,
                        'orders': 3,
                        'ctr': 4.0,
                        'cpc': 50.0,
                        'cr': 15.0,
                        'frq': 1.2,
                        'shks': 3,
                        'unique_users': 400,
                    }],
                }],
            }],
        }]
        result = etl._transform_adv(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['date'], '2026-02-01')
        self.assertEqual(row['nmid'], 100)
        self.assertEqual(row['views'], 500)
        self.assertEqual(row['clicks'], 20)
        self.assertEqual(row['advertid'], 1001)
        self.assertEqual(row['lk'], 'Test LK')

    def test_empty_days(self):
        etl = _make_wb_etl()
        records = [{'advertId': 1, 'name': 'C1', 'days': []}]
        result = etl._transform_adv(records)
        self.assertEqual(result, [])


# ======================================================================
# Ozon Transform Tests
# ======================================================================

class TestOzonTransformTransactions(unittest.TestCase):
    """Test _transform_transactions aggregation."""

    def test_empty_operations(self):
        etl = _make_ozon_etl()
        result = etl._transform_transactions([])
        self.assertEqual(result, [])

    def test_single_operation(self):
        etl = _make_ozon_etl()
        operations = [{
            'operation_date': '2026-02-01T10:00:00Z',
            'operation_type': 'OperationAgentDeliveredToCustomer',
            'amount': 1500,
            'accruals_for_sale': 1500,
            'sale_commission': -200,
            'items': [{
                'sku': 12345,
                'offer_id': 'ART1',
                'product_id': 99,
                'quantity': 1,
            }],
            'posting': {'posting_number': 'POST-1'},
            'services': [
                {'name': 'MarketplaceServiceItemDirectFlowLogistic', 'price': -50},
                {'name': 'MarketplaceServiceStorageFee', 'price': -10},
            ],
        }]
        result = etl._transform_transactions(operations)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['date'], '2026-02-01')
        self.assertEqual(row['article'], 'ART1')
        self.assertEqual(row['lk'], 'Test LK')
        self.assertEqual(row['mp'], 'ozon')
        self.assertEqual(row['price_end'], 1500)
        self.assertEqual(row['comission_end'], 200)
        self.assertEqual(row['logist_end'], 50)  # abs(-50)
        self.assertEqual(row['storage_end'], 10)  # abs(-10)
        self.assertEqual(row['count_end'], 1)
        self.assertEqual(row['sebes_end'], 0)
        self.assertEqual(row['reclama_end'], 0)

    def test_aggregation_by_date_article(self):
        """Two operations same day + article should aggregate."""
        etl = _make_ozon_etl()
        operations = [
            {
                'operation_date': '2026-02-01T10:00:00Z',
                'operation_type': 'Sale',
                'amount': 500,
                'accruals_for_sale': 500,
                'sale_commission': -50,
                'items': [{'sku': 1, 'offer_id': 'ART1', 'product_id': 1, 'quantity': 1}],
                'posting': {},
                'services': [],
            },
            {
                'operation_date': '2026-02-01T14:00:00Z',
                'operation_type': 'Sale',
                'amount': 700,
                'accruals_for_sale': 700,
                'sale_commission': -70,
                'items': [{'sku': 1, 'offer_id': 'ART1', 'product_id': 1, 'quantity': 2}],
                'posting': {},
                'services': [],
            },
        ]
        result = etl._transform_transactions(operations)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['price_end'], 1200)  # 500 + 700
        self.assertEqual(row['comission_end'], 120)  # abs(-50) + abs(-70)
        self.assertEqual(row['count_end'], 3)  # 1 + 2


class TestOzonTransformPostings(unittest.TestCase):
    """Test _transform_postings combining FBO + FBS."""

    def test_combined_postings(self):
        etl = _make_ozon_etl()
        fbo = [{
            'order_id': 1,
            'posting_number': 'FBO-1',
            'order_number': 'ON-1',
            'status': 'delivered',
            'in_process_at': '2026-02-01',
            'products': [
                {'product_id': 10, 'sku': 100, 'offer_id': 'ART1', 'price': '1500', 'quantity': 1, 'commission_amount': 0},
            ],
        }]
        fbs = [{
            'order_id': 2,
            'posting_number': 'FBS-1',
            'order_number': 'ON-2',
            'status': 'delivered',
            'in_process_at': '2026-02-02',
            'products': [
                {'product_id': 20, 'sku': 200, 'offer_id': 'ART2', 'price': '2000', 'quantity': 2, 'commission_amount': 0},
            ],
        }]
        result = etl._transform_postings(fbo, fbs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['delivery_schema'], 'FBO')
        self.assertEqual(result[1]['delivery_schema'], 'FBS')

    def test_multi_product_posting(self):
        etl = _make_ozon_etl()
        fbo = [{
            'order_id': 1,
            'posting_number': 'FBO-1',
            'order_number': '',
            'status': 'delivered',
            'in_process_at': None,
            'products': [
                {'product_id': 10, 'sku': 100, 'offer_id': 'ART1', 'price': '500', 'quantity': 1, 'commission_amount': 0},
                {'product_id': 20, 'sku': 200, 'offer_id': 'ART2', 'price': '700', 'quantity': 1, 'commission_amount': 0},
            ],
        }]
        result = etl._transform_postings(fbo, [])
        self.assertEqual(len(result), 2)  # One row per product


class TestOzonTransformReturns(unittest.TestCase):
    """Test _transform_returns filters correctly."""

    def test_filters_only_returns(self):
        etl = _make_ozon_etl()
        operations = [
            {
                'operation_type': 'OperationAgentDeliveredToCustomer',
                'operation_id': 1,
                'operation_date': '2026-02-01T10:00:00Z',
                'operation_type_name': 'Delivery',
                'amount': 1000,
                'accruals_for_sale': 1000,
                'sale_commission': -100,
                'items': [{'sku': 1, 'offer_id': 'ART1', 'product_id': 1, 'name': 'Prod1'}],
                'posting': {'posting_number': 'P1', 'order_date': '2026-02-01', 'delivery_schema': 'FBO'},
                'services': [],
            },
            {
                'operation_type': 'OperationReturnGoods',
                'operation_id': 2,
                'operation_date': '2026-02-02T10:00:00Z',
                'operation_type_name': 'Return',
                'amount': -500,
                'accruals_for_sale': -500,
                'sale_commission': 50,
                'items': [{'sku': 2, 'offer_id': 'ART2', 'product_id': 2, 'name': 'Prod2'}],
                'posting': {'posting_number': 'P2', 'order_date': '2026-02-01', 'delivery_schema': 'FBO'},
                'services': [
                    {'name': 'MarketplaceServiceItemReturnFlowLogistic', 'price': -30},
                ],
            },
        ]
        result = etl._transform_returns(operations)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['operation_type'], 'OperationReturnGoods')
        self.assertEqual(row['amount'], -500)
        self.assertEqual(row['lk'], 'Test LK')


class TestOzonTransformStocks(unittest.TestCase):
    """Test _transform_stocks flattening."""

    def test_stock_flattening(self):
        etl = _make_ozon_etl()
        records = [{
            'offer_id': 'ART1',
            'product_id': 10,
            'sku': 100,
            'promised_amount': 5,
            'stocks': [
                {'type': 'fbo', 'present': 50, 'reserved': 5, 'warehouse_id': 1, 'warehouse_name': 'WH1'},
                {'type': 'fbs', 'present': 20, 'reserved': 2, 'warehouse_id': 2, 'warehouse_name': 'WH2'},
            ],
        }]
        result = etl._transform_stocks(records)
        self.assertEqual(len(result), 2)  # One per stock entry
        self.assertEqual(result[0]['delivery_schema'], 'fbo')
        self.assertEqual(result[0]['stockspresent'], 50)
        self.assertEqual(result[1]['delivery_schema'], 'fbs')
        self.assertEqual(result[1]['stockspresent'], 20)


class TestOzonTransformProducts(unittest.TestCase):
    """Test _transform_products mapping."""

    def test_basic_mapping(self):
        etl = _make_ozon_etl()
        records = [{
            'offer_id': 'ART1',
            'product_id': 10,
            'fbo_sku': 100,
            'fbs_sku': 200,
            'barcode': '123456',
            'status': {'state_name': 'Active'},
        }]
        result = etl._transform_products(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['article'], 'ART1')
        self.assertEqual(row['ozon_product_id'], '10')
        self.assertEqual(row['status'], 'Active')
        self.assertEqual(row['lk'], 'Test LK')


class TestOzonTransformAdv(unittest.TestCase):
    """Test _transform_adv mapping."""

    def test_basic_mapping(self):
        etl = _make_ozon_etl()
        records = [{
            'campaign_id': 500,
            'title': 'Campaign1',
            'date': '2026-02-01T00:00:00Z',
            'views': 1000,
            'clicks': 50,
            'orders': 10,
            'orders_amount': 15000,
            'spent': 500,
            'avg_bid': 5.0,
        }]
        result = etl._transform_adv(records)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['id_rk'], 500)
        self.assertEqual(row['operation_date'], '2026-02-01')
        self.assertEqual(row['views'], 1000)
        self.assertEqual(row['rk_expense'], 500)

    def test_empty_date_skipped(self):
        etl = _make_ozon_etl()
        records = [{'campaign_id': 1, 'title': '', 'date': ''}]
        result = etl._transform_adv(records)
        self.assertEqual(result, [])


# ======================================================================
# Load Table SQL Generation Tests
# ======================================================================

class TestWBLoadTable(unittest.TestCase):
    """Test _load_table SQL building (without DB connection)."""

    def test_skip_empty_rows(self):
        etl = _make_wb_etl()
        cursor = MagicMock()
        etl._load_table(cursor, 'wb.abc_date', [], conflict_columns=['date', 'article'])
        cursor.execute.assert_not_called()

    @patch('services.marketplace_etl.etl.wb_etl.execute_values')
    def test_generates_upsert_sql(self, mock_exec):
        etl = _make_wb_etl()
        cursor = MagicMock()
        rows = [{'date': '2026-02-01', 'article': 'ART1', 'revenue_spp': 1000}]
        etl._load_table(cursor, 'wb.abc_date', rows, conflict_columns=['date', 'article'])
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        sql = call_args[0][1]
        self.assertIn('INSERT INTO wb.abc_date', sql)
        self.assertIn('ON CONFLICT (date, article)', sql)
        self.assertIn('DO UPDATE SET', sql)


if __name__ == '__main__':
    unittest.main()
