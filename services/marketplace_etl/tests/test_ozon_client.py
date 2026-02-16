"""
Tests for OzonAPIClient.

Tests cover: construction, authentication, pagination, error handling.
Uses unittest.mock to avoid real HTTP requests.
"""

import unittest
from unittest.mock import patch, MagicMock

from services.marketplace_etl.api_clients.ozon_client import OzonAPIClient
from services.marketplace_etl.api_clients.base_client import BaseAPIClient


class TestOzonClientConstruction(unittest.TestCase):
    """Test client initialization."""

    def test_requires_client_id_and_api_key(self):
        with self.assertRaises(ValueError):
            OzonAPIClient(client_id='', api_key='key')
        with self.assertRaises(ValueError):
            OzonAPIClient(client_id='id', api_key='')

    def test_sets_headers(self):
        client = OzonAPIClient(client_id='123', api_key='test_key', lk='Test LK')
        self.assertEqual(client._headers['Client-Id'], '123')
        self.assertEqual(client._headers['Api-Key'], 'test_key')
        self.assertEqual(client._headers['Content-Type'], 'application/json')
        self.assertEqual(client.lk, 'Test LK')

    def test_default_rate_limits(self):
        client = OzonAPIClient(client_id='id', api_key='key')
        self.assertEqual(client.RATE_LIMITS['finance'], 1.0)
        self.assertEqual(client.RATE_LIMITS['default'], 0.1)


class TestOzonClientFormatDate(unittest.TestCase):
    """Test date formatting."""

    def test_string_passthrough_with_T(self):
        self.assertEqual(
            OzonAPIClient._format_datetime('2026-02-01T00:00:00Z'),
            '2026-02-01T00:00:00Z',
        )

    def test_string_date_to_datetime(self):
        self.assertEqual(
            OzonAPIClient._format_datetime('2026-02-01'),
            '2026-02-01T00:00:00Z',
        )

    def test_format_date_string(self):
        self.assertEqual(OzonAPIClient._format_date('2026-02-01T12:00:00'), '2026-02-01')

    def test_format_date_datetime(self):
        from datetime import datetime
        dt = datetime(2026, 2, 1)
        self.assertEqual(OzonAPIClient._format_date(dt), '2026-02-01')


class TestOzonClientTestConnection(unittest.TestCase):
    """Test connection check."""

    @patch.object(BaseAPIClient, '_request')
    def test_connection_success(self, mock_request):
        mock_request.return_value = {'result': []}
        client = OzonAPIClient(client_id='id', api_key='key', lk='Test')
        self.assertTrue(client.test_connection())

    @patch.object(BaseAPIClient, '_request')
    def test_connection_failure(self, mock_request):
        mock_request.side_effect = Exception("Connection refused")
        client = OzonAPIClient(client_id='id', api_key='key', lk='Test')
        self.assertFalse(client.test_connection())


class TestOzonClientFinanceTransactions(unittest.TestCase):
    """Test get_finance_transaction_list with pagination."""

    @patch.object(BaseAPIClient, '_request')
    def test_single_page(self, mock_request):
        mock_request.return_value = {
            'result': {
                'operations': [{'operation_id': 1}, {'operation_id': 2}],
                'page_count': 1,
            },
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_finance_transaction_list('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 2)

    @patch.object(BaseAPIClient, '_request')
    def test_multi_page(self, mock_request):
        mock_request.side_effect = [
            {
                'result': {
                    'operations': [{'operation_id': i} for i in range(1000)],
                    'page_count': 2,
                },
            },
            {
                'result': {
                    'operations': [{'operation_id': 1000 + i} for i in range(500)],
                    'page_count': 2,
                },
            },
        ]
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_finance_transaction_list('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 1500)

    @patch.object(BaseAPIClient, '_request')
    def test_empty_response(self, mock_request):
        mock_request.return_value = {'result': {'operations': [], 'page_count': 0}}
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_finance_transaction_list('2026-02-01', '2026-02-07')
        self.assertEqual(result, [])

    @patch.object(BaseAPIClient, '_request')
    def test_uses_finance_rate_limit(self, mock_request):
        mock_request.return_value = {'result': {'operations': [], 'page_count': 0}}
        client = OzonAPIClient(client_id='id', api_key='key')
        client.get_finance_transaction_list('2026-02-01', '2026-02-07')
        self.assertEqual(client.min_interval_sec, 1.0)


class TestOzonClientPostings(unittest.TestCase):
    """Test FBO and FBS posting endpoints."""

    @patch.object(BaseAPIClient, '_request')
    def test_fbo_postings(self, mock_request):
        mock_request.return_value = {
            'result': [
                {'posting_number': 'FBO-1', 'products': [{'sku': 1}]},
                {'posting_number': 'FBO-2', 'products': [{'sku': 2}]},
            ],
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_fbo_posting_list('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 2)

    @patch.object(BaseAPIClient, '_request')
    def test_fbs_postings(self, mock_request):
        mock_request.return_value = {
            'result': {
                'postings': [{'posting_number': 'FBS-1'}],
            },
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_fbs_posting_list('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 1)


class TestOzonClientProducts(unittest.TestCase):
    """Test product-related endpoints."""

    @patch.object(BaseAPIClient, '_request')
    def test_products_list_single_page(self, mock_request):
        mock_request.return_value = {
            'result': {
                'items': [{'product_id': 1}, {'product_id': 2}],
                'last_id': '',
            },
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_products_list()
        self.assertEqual(len(result), 2)

    @patch.object(BaseAPIClient, '_request')
    def test_products_info(self, mock_request):
        mock_request.return_value = {
            'result': {'items': [{'product_id': 1, 'name': 'Test'}]},
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_products_info(offer_ids=['ART1'])
        self.assertEqual(len(result), 1)


class TestOzonClientStocks(unittest.TestCase):
    """Test stocks endpoint."""

    @patch.object(BaseAPIClient, '_request')
    def test_stocks_single_page(self, mock_request):
        mock_request.return_value = {
            'result': {
                'items': [
                    {'offer_id': 'ART1', 'stocks': [{'present': 10}]},
                ],
            },
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_stocks()
        self.assertEqual(len(result), 1)


class TestOzonClientAdvStatistics(unittest.TestCase):
    """Test advertising endpoints."""

    @patch.object(OzonAPIClient, '_get_adv_campaigns')
    @patch.object(BaseAPIClient, '_request')
    def test_no_campaigns(self, mock_request, mock_campaigns):
        mock_campaigns.return_value = []
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_adv_statistics('2026-02-01', '2026-02-07')
        self.assertEqual(result, [])

    @patch.object(OzonAPIClient, '_get_adv_campaigns')
    @patch.object(BaseAPIClient, '_request')
    def test_with_campaigns(self, mock_request, mock_campaigns):
        mock_campaigns.return_value = [{'id': 1}]
        mock_request.return_value = {
            'rows': [{'views': 100, 'clicks': 10, 'date': '2026-02-01'}],
        }
        client = OzonAPIClient(client_id='id', api_key='key')
        result = client.get_adv_statistics('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['campaign_id'], 1)


if __name__ == '__main__':
    unittest.main()
