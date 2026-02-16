"""
Tests for WildberriesAPIClient.

Tests cover: construction, rate limiting, pagination, error handling.
Uses unittest.mock to avoid real HTTP requests.
"""

import time
import unittest
from unittest.mock import patch, MagicMock

from services.marketplace_etl.api_clients.wb_client import WildberriesAPIClient
from services.marketplace_etl.api_clients.base_client import BaseAPIClient


class TestWBClientConstruction(unittest.TestCase):
    """Test client initialization."""

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            WildberriesAPIClient(api_key='', lk='Test')

    def test_sets_headers(self):
        client = WildberriesAPIClient(api_key='test_key', lk='Test LK')
        self.assertEqual(client._headers['Authorization'], 'Bearer test_key')
        self.assertEqual(client.lk, 'Test LK')

    def test_default_rate_limits(self):
        client = WildberriesAPIClient(api_key='key')
        self.assertEqual(client.RATE_LIMITS['sales'], 12.0)
        self.assertEqual(client.RATE_LIMITS['orders'], 12.0)
        self.assertEqual(client.RATE_LIMITS['default'], 1.0)


class TestWBClientFormatDate(unittest.TestCase):
    """Test date formatting."""

    def test_string_passthrough(self):
        self.assertEqual(
            WildberriesAPIClient._format_date('2026-02-01'),
            '2026-02-01',
        )

    def test_datetime_format(self):
        from datetime import datetime
        dt = datetime(2026, 2, 1)
        self.assertEqual(
            WildberriesAPIClient._format_date(dt),
            '2026-02-01T00:00:00Z',
        )


class TestWBClientTestConnection(unittest.TestCase):
    """Test the test_connection method."""

    @patch.object(BaseAPIClient, '_request')
    def test_connection_success(self, mock_request):
        mock_request.return_value = [{'some': 'data'}]
        client = WildberriesAPIClient(api_key='key', lk='Test')
        self.assertTrue(client.test_connection())

    @patch.object(BaseAPIClient, '_request')
    def test_connection_failure(self, mock_request):
        mock_request.side_effect = Exception("Connection refused")
        client = WildberriesAPIClient(api_key='key', lk='Test')
        self.assertFalse(client.test_connection())


class TestWBClientReportDetail(unittest.TestCase):
    """Test get_report_detail_by_period with pagination."""

    @patch.object(BaseAPIClient, '_request')
    def test_single_page(self, mock_request):
        records = [{'rrd_id': 1, 'sa_name': 'ART1', 'ppvz_for_pay': 100}]
        mock_request.return_value = records

        client = WildberriesAPIClient(api_key='key')
        result = client.get_report_detail_by_period('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['rrd_id'], 1)

    @patch.object(BaseAPIClient, '_request')
    def test_pagination_via_rrdid(self, mock_request):
        page1 = [{'rrd_id': i} for i in range(100000)]
        page2 = [{'rrd_id': 100000 + i} for i in range(50)]

        mock_request.side_effect = [page1, page2]

        client = WildberriesAPIClient(api_key='key')
        result = client.get_report_detail_by_period('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 100050)
        self.assertEqual(mock_request.call_count, 2)

    @patch.object(BaseAPIClient, '_request')
    def test_empty_response(self, mock_request):
        mock_request.return_value = []

        client = WildberriesAPIClient(api_key='key')
        result = client.get_report_detail_by_period('2026-02-01', '2026-02-07')
        self.assertEqual(result, [])


class TestWBClientSalesOrders(unittest.TestCase):
    """Test get_sales and get_orders."""

    @patch.object(BaseAPIClient, '_request')
    def test_get_sales(self, mock_request):
        mock_request.return_value = [{'saleID': 'S1'}, {'saleID': 'S2'}]
        client = WildberriesAPIClient(api_key='key')
        result = client.get_sales('2026-02-01')
        self.assertEqual(len(result), 2)

    @patch.object(BaseAPIClient, '_request')
    def test_get_sales_rate_limit(self, mock_request):
        mock_request.return_value = []
        client = WildberriesAPIClient(api_key='key')
        client.get_sales('2026-02-01')
        # After call, rate limit should be set to sales value
        self.assertEqual(client.min_interval_sec, 12.0)

    @patch.object(BaseAPIClient, '_request')
    def test_get_orders(self, mock_request):
        mock_request.return_value = [{'gNumber': 'G1'}]
        client = WildberriesAPIClient(api_key='key')
        result = client.get_orders('2026-02-01')
        self.assertEqual(len(result), 1)

    @patch.object(BaseAPIClient, '_request')
    def test_get_sales_empty_list(self, mock_request):
        mock_request.return_value = []
        client = WildberriesAPIClient(api_key='key')
        result = client.get_sales('2026-02-01')
        self.assertEqual(result, [])


class TestWBClientContentCards(unittest.TestCase):
    """Test get_content_cards with cursor pagination."""

    @patch.object(BaseAPIClient, '_request')
    def test_single_page(self, mock_request):
        mock_request.return_value = {
            'cards': [{'nmID': 1}, {'nmID': 2}],
            'cursor': {'total': 0},
        }
        client = WildberriesAPIClient(api_key='key')
        result = client.get_content_cards()
        self.assertEqual(len(result), 2)

    @patch.object(BaseAPIClient, '_request')
    def test_empty_cards(self, mock_request):
        mock_request.return_value = {'cards': [], 'cursor': {}}
        client = WildberriesAPIClient(api_key='key')
        result = client.get_content_cards()
        self.assertEqual(result, [])


class TestWBClientAdvStatistics(unittest.TestCase):
    """Test get_adv_statistics."""

    @patch.object(WildberriesAPIClient, '_get_adv_campaigns')
    @patch.object(BaseAPIClient, '_request')
    def test_no_campaigns(self, mock_request, mock_campaigns):
        mock_campaigns.return_value = []
        client = WildberriesAPIClient(api_key='key')
        result = client.get_adv_statistics('2026-02-01', '2026-02-07')
        self.assertEqual(result, [])
        mock_request.assert_not_called()

    @patch.object(WildberriesAPIClient, '_get_adv_campaigns')
    @patch.object(BaseAPIClient, '_request')
    def test_with_campaigns(self, mock_request, mock_campaigns):
        mock_campaigns.return_value = [
            {'advertId': 100},
            {'advertId': 200},
        ]
        # All campaigns fit in one batch (max 100), so _post is called once
        mock_request.return_value = [{'views': 10, 'clicks': 1}]

        client = WildberriesAPIClient(api_key='key')
        result = client.get_adv_statistics('2026-02-01', '2026-02-07')
        self.assertEqual(len(result), 1)  # One batch returns one stats list


class TestBaseClientRetry(unittest.TestCase):
    """Test base client retry logic."""

    @patch('services.marketplace_etl.api_clients.base_client.requests.get')
    @patch('services.marketplace_etl.api_clients.base_client.time.sleep')
    def test_retry_on_429(self, mock_sleep, mock_get):
        resp_429 = MagicMock()
        resp_429.status_code = 429

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {'data': 'ok'}
        resp_ok.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_429, resp_ok]

        client = BaseAPIClient(min_interval_sec=0, max_retries=3)
        client._last_request_time = time.time()
        result = client._request('GET', 'http://test.com')
        self.assertEqual(result, {'data': 'ok'})
        self.assertEqual(mock_get.call_count, 2)

    @patch('services.marketplace_etl.api_clients.base_client.requests.get')
    @patch('services.marketplace_etl.api_clients.base_client.time.sleep')
    def test_retry_on_500(self, mock_sleep, mock_get):
        resp_500 = MagicMock()
        resp_500.status_code = 500

        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = []
        resp_ok.raise_for_status = MagicMock()

        mock_get.side_effect = [resp_500, resp_ok]

        client = BaseAPIClient(min_interval_sec=0, max_retries=3)
        client._last_request_time = time.time()
        result = client._request('GET', 'http://test.com')
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
