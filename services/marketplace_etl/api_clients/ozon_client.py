"""
Ozon Seller API Client.

Implements all Ozon API endpoints needed for ETL:
- finance/transaction/list (abc_date) — main financial data
- FBO/FBS postings (orders, returns) — operational data
- product info, stocks, analytics, advertising

Documentation: https://docs.ozon.ru/api/seller/
"""

import logging
from datetime import datetime

from services.marketplace_etl.api_clients.base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class OzonAPIClient(BaseAPIClient):
    """Client for Ozon Seller API with rate limiting and pagination."""

    BASE_URL = 'https://api-seller.ozon.ru'

    # Finance API: 1-2 req/sec; others: up to 20 req/sec
    RATE_LIMITS = {
        'finance': 1.0,
        'default': 0.1,
    }

    def __init__(self, client_id, api_key, lk=None, min_interval_sec=0.1, max_retries=5, timeout=30):
        """
        Args:
            client_id: Ozon Client-Id.
            api_key: Ozon Api-Key.
            lk: Legal entity name (e.g. 'Ozon ИП Медведева П.В.').
        """
        super().__init__(min_interval_sec=min_interval_sec, max_retries=max_retries, timeout=timeout)
        if not client_id or not api_key:
            raise ValueError("Ozon Client-Id and Api-Key are required")
        self.client_id = str(client_id)
        self.api_key = api_key
        self.lk = lk
        self._headers = {
            'Client-Id': self.client_id,
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

    def _post(self, endpoint, json_data=None, rate_key='default'):
        """POST request to Ozon API."""
        self.min_interval_sec = self.RATE_LIMITS.get(rate_key, self.RATE_LIMITS['default'])
        url = f"{self.BASE_URL}{endpoint}"
        return self._request('POST', url, headers=self._headers, json_data=json_data)

    @staticmethod
    def _format_datetime(dt):
        """Format to ISO 8601 with timezone."""
        if isinstance(dt, str):
            if 'T' in dt:
                return dt
            return f"{dt}T00:00:00Z"
        return dt.strftime('%Y-%m-%dT00:00:00Z')

    @staticmethod
    def _format_date(dt):
        """Format to YYYY-MM-DD."""
        if isinstance(dt, str):
            return dt[:10]
        return dt.strftime('%Y-%m-%d')

    # --- Test ---

    def test_connection(self):
        """Test API connection by requesting seller info."""
        try:
            self._post('/v1/warehouse/list', json_data={})
            logger.info(f"Ozon API connection OK (lk={self.lk})")
            return True
        except Exception as e:
            logger.error(f"Ozon API connection failed (lk={self.lk}): {e}")
            return False

    # --- Finance transactions (basis for ozon.abc_date) ---

    def get_finance_transaction_list(self, date_from, date_to, page_size=1000):
        """
        Get financial transactions — the main data source for ozon.abc_date.
        Handles pagination automatically.

        Args:
            date_from: Start date.
            date_to: End date.
            page_size: Records per page (max 1000).

        Returns:
            list: All transaction operation records.
        """
        all_operations = []
        page = 1

        while True:
            body = {
                'filter': {
                    'date': {
                        'from': self._format_datetime(date_from),
                        'to': self._format_datetime(date_to),
                    },
                    'transaction_type': 'all',
                },
                'page': page,
                'page_size': page_size,
            }
            resp = self._post('/v3/finance/transaction/list', json_data=body, rate_key='finance')
            result = resp.get('result', {})
            operations = result.get('operations', [])

            if not operations:
                break

            all_operations.extend(operations)
            logger.info(f"get_finance_transaction_list: page {page}, got {len(operations)} ops (total {len(all_operations)})")

            page_count = result.get('page_count', 1)
            if page >= page_count:
                break

            page += 1

        logger.info(f"get_finance_transaction_list: total {len(all_operations)} operations for {date_from} — {date_to}")
        return all_operations

    # --- FBO postings (orders) ---

    def get_fbo_posting_list(self, since, to, status='', limit=1000):
        """
        Get FBO (Fulfillment by Ozon) postings with pagination.

        Args:
            since: Start datetime.
            to: End datetime.
            status: Filter by status (empty = all).
            limit: Records per page.

        Returns:
            list: All FBO postings.
        """
        all_postings = []
        offset = 0

        while True:
            body = {
                'dir': 'ASC',
                'filter': {
                    'since': self._format_datetime(since),
                    'to': self._format_datetime(to),
                },
                'limit': limit,
                'offset': offset,
            }
            if status:
                body['filter']['status'] = status

            resp = self._post('/v2/posting/fbo/list', json_data=body)
            postings = resp.get('result', [])

            if not postings:
                break

            all_postings.extend(postings)
            logger.info(f"get_fbo_posting_list: offset {offset}, got {len(postings)} (total {len(all_postings)})")

            if len(postings) < limit:
                break

            offset += limit

        logger.info(f"get_fbo_posting_list: total {len(all_postings)} postings")
        return all_postings

    # --- FBS postings (orders) ---

    def get_fbs_posting_list(self, since, to, status='', limit=1000):
        """
        Get FBS (Fulfillment by Seller) postings with pagination.

        Args:
            since: Start datetime.
            to: End datetime.
            status: Filter by status (empty = all).
            limit: Records per page.

        Returns:
            list: All FBS postings.
        """
        all_postings = []
        offset = 0

        while True:
            body = {
                'dir': 'ASC',
                'filter': {
                    'since': self._format_datetime(since),
                    'to': self._format_datetime(to),
                },
                'limit': limit,
                'offset': offset,
            }
            if status:
                body['filter']['status'] = status

            resp = self._post('/v2/posting/fbs/list', json_data=body)
            result = resp.get('result', {})
            postings = result.get('postings', [])

            if not postings:
                break

            all_postings.extend(postings)
            logger.info(f"get_fbs_posting_list: offset {offset}, got {len(postings)} (total {len(all_postings)})")

            if len(postings) < limit:
                break

            offset += limit

        logger.info(f"get_fbs_posting_list: total {len(all_postings)} postings")
        return all_postings

    # --- Analytics data ---

    def get_analytics_data(self, date_from, date_to, metrics=None, dimension='sku', limit=1000):
        """
        Get analytics data.

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date.
            metrics: List of metric names. Default: standard set.
            dimension: Grouping dimension ('sku', 'day', etc.).
            limit: Records per page.

        Returns:
            list: All analytics rows.
        """
        if metrics is None:
            metrics = [
                'revenue', 'ordered_units', 'returns',
                'cancellations', 'delivered_units',
            ]

        all_rows = []
        offset = 0

        while True:
            body = {
                'date_from': self._format_date(date_from),
                'date_to': self._format_date(date_to),
                'metrics': metrics,
                'dimension': [dimension],
                'filters': [],
                'sort': [{'key': 'revenue', 'order': 'DESC'}],
                'limit': limit,
                'offset': offset,
            }
            resp = self._post('/v1/analytics/data', json_data=body)
            result = resp.get('result', {})
            rows = result.get('data', [])

            if not rows:
                break

            all_rows.extend(rows)
            logger.info(f"get_analytics_data: offset {offset}, got {len(rows)} (total {len(all_rows)})")

            if len(rows) < limit:
                break

            offset += limit

        logger.info(f"get_analytics_data: total {len(all_rows)} rows")
        return all_rows

    # --- Product info (nomenclature) ---

    def get_products_info(self, offer_ids=None, product_ids=None, skus=None):
        """
        Get product information.

        Args:
            offer_ids: List of offer IDs (article).
            product_ids: List of product IDs.
            skus: List of SKUs.

        Returns:
            list: Product info items.
        """
        body = {}
        if offer_ids:
            body['offer_id'] = offer_ids
        if product_ids:
            body['product_id'] = product_ids
        if skus:
            body['sku'] = skus

        resp = self._post('/v2/product/info/list', json_data=body)
        items = resp.get('result', {}).get('items', [])
        logger.info(f"get_products_info: {len(items)} products")
        return items

    def get_products_list(self, limit=1000):
        """
        Get full product list with pagination.

        Returns:
            list: All product items with offer_id, product_id, etc.
        """
        all_items = []
        last_id = ''

        while True:
            body = {
                'filter': {'visibility': 'ALL'},
                'limit': limit,
            }
            if last_id:
                body['last_id'] = last_id

            resp = self._post('/v2/product/list', json_data=body)
            result = resp.get('result', {})
            items = result.get('items', [])

            if not items:
                break

            all_items.extend(items)
            last_id = result.get('last_id', '')

            if not last_id or len(items) < limit:
                break

        logger.info(f"get_products_list: total {len(all_items)} products")
        return all_items

    # --- Stocks ---

    def get_stocks(self, limit=1000):
        """
        Get warehouse stock data with pagination via cursor.

        Args:
            limit: Records per page.

        Returns:
            list: Stock records.
        """
        all_stocks = []
        offset = 0

        while True:
            body = {
                'limit': limit,
                'offset': offset,
            }
            resp = self._post('/v1/product/info/stocks', json_data=body)
            result = resp.get('result', {})
            items = result.get('items', [])

            if not items:
                break

            all_stocks.extend(items)
            logger.info(f"get_stocks: offset {offset}, got {len(items)} (total {len(all_stocks)})")

            if len(items) < limit:
                break

            offset += limit

        logger.info(f"get_stocks: total {len(all_stocks)} stock items")
        return all_stocks

    # --- Advertising stats ---

    def get_adv_statistics(self, date_from, date_to):
        """
        Get advertising campaign statistics (daily).

        Args:
            date_from: Start date.
            date_to: End date.

        Returns:
            list: Daily advertising stats.
        """
        # Get campaigns list first
        campaigns = self._get_adv_campaigns()
        if not campaigns:
            logger.info("get_adv_statistics: no campaigns found")
            return []

        all_stats = []
        for campaign in campaigns:
            campaign_id = campaign.get('id')
            try:
                body = {
                    'campaigns': [str(campaign_id)],
                    'dateFrom': self._format_date(date_from),
                    'dateTo': self._format_date(date_to),
                    'groupBy': 'DATE',
                }
                resp = self._post('/v1/performance/statistics/campaign/daily', json_data=body)
                rows = resp.get('rows', [])
                for row in rows:
                    row['campaign_id'] = campaign_id
                all_stats.extend(rows)
            except Exception as e:
                logger.warning(f"get_adv_statistics error for campaign {campaign_id}: {e}")

        logger.info(f"get_adv_statistics: {len(all_stats)} daily stat entries")
        return all_stats

    def _get_adv_campaigns(self):
        """Get list of all advertising campaigns."""
        try:
            resp = self._post('/v1/performance/campaigns', json_data={})
            return resp.get('list', [])
        except Exception as e:
            logger.warning(f"_get_adv_campaigns error: {e}")
            return []

    # --- Client statistics (search_stat) ---

    def get_client_statistics(self, date_from, date_to):
        """
        Get client/search statistics.
        Note: this endpoint may return empty data.

        Args:
            date_from: Start date.
            date_to: End date.

        Returns:
            list: Statistics records (often empty).
        """
        try:
            body = {
                'date_from': self._format_date(date_from),
                'date_to': self._format_date(date_to),
            }
            resp = self._post('/v1/client/statistics', json_data=body)
            data = resp.get('result', [])
            logger.info(f"get_client_statistics: {len(data)} records")
            return data
        except Exception as e:
            logger.warning(f"get_client_statistics error (may not be available): {e}")
            return []


# Example usage:
if __name__ == '__main__':
    from services.marketplace_etl.config.database import get_accounts

    accounts = get_accounts()
    for acc in accounts.get('ozon', []):
        client = OzonAPIClient(
            client_id=acc['client_id'],
            api_key=acc['api_key'],
            lk=acc['lk'],
        )
        if client.test_connection():
            print(f"Ozon API connection successful for {acc['lk']}")
        else:
            print(f"Ozon API connection failed for {acc['lk']}")
