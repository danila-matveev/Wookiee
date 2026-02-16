"""
Wildberries API Client.

Implements all WB API endpoints needed for ETL:
- reportDetailByPeriod (abc_date) — main financial data
- sales, orders, stocks — operational data
- advert statistics, content cards — marketing & nomenclature

Documentation: https://dev.wildberries.ru/docs/openapi/api-information
"""

import logging
from datetime import datetime

from services.marketplace_etl.api_clients.base_client import BaseAPIClient

logger = logging.getLogger(__name__)


class WildberriesAPIClient(BaseAPIClient):
    """Client for Wildberries API with rate limiting and pagination."""

    BASE_URLS = {
        'statistics': 'https://statistics-api.wildberries.ru/api/v1',
        'content': 'https://content-api.wildberries.ru',
        'advert': 'https://advert-api.wildberries.ru/api/v2',
        'analytics': 'https://seller-analytics-api.wildberries.ru/api/v2',
    }

    # sales/orders: 5 req/min = 12s interval; others: 60 req/min = 1s
    RATE_LIMITS = {
        'sales': 12.0,
        'orders': 12.0,
        'default': 1.0,
    }

    def __init__(self, api_key, lk=None, min_interval_sec=1.0, max_retries=5, timeout=30):
        """
        Args:
            api_key: WB API Bearer token.
            lk: Legal entity name (e.g. 'WB ИП Медведева П.В.').
        """
        super().__init__(min_interval_sec=min_interval_sec, max_retries=max_retries, timeout=timeout)
        if not api_key:
            raise ValueError("WB API key is required")
        self.api_key = api_key
        self.lk = lk
        self._headers = {'Authorization': f'Bearer {self.api_key}'}

    def _get(self, url, params=None, rate_key='default'):
        """GET request with appropriate rate limit."""
        self.min_interval_sec = self.RATE_LIMITS.get(rate_key, self.RATE_LIMITS['default'])
        return self._request('GET', url, headers=self._headers, params=params)

    def _post(self, url, json_data=None, rate_key='default'):
        """POST request with appropriate rate limit."""
        self.min_interval_sec = self.RATE_LIMITS.get(rate_key, self.RATE_LIMITS['default'])
        return self._request('POST', url, headers=self._headers, json_data=json_data)

    @staticmethod
    def _format_date(dt):
        """Format datetime to RFC3339 string."""
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%dT00:00:00Z')

    # --- Test ---

    def test_connection(self):
        """Test API connection by requesting stocks for today."""
        try:
            url = f"{self.BASE_URLS['statistics']}/supplier/stocks"
            self._get(url, params={'dateFrom': datetime.now().strftime('%Y-%m-%d')})
            logger.info(f"WB API connection OK (lk={self.lk})")
            return True
        except Exception as e:
            logger.error(f"WB API connection failed (lk={self.lk}): {e}")
            return False

    # --- reportDetailByPeriod (basis for abc_date) ---

    def get_report_detail_by_period(self, date_from, date_to, limit=100000):
        """
        Get detailed financial report — the main data source for wb.abc_date.
        Handles pagination via rrdid automatically.

        Args:
            date_from: Start date (datetime or string).
            date_to: End date.
            limit: Records per page (max 100000).

        Returns:
            list: All report records for the period.
        """
        url = f"{self.BASE_URLS['statistics']}/supplier/reportDetailByPeriod"
        all_records = []
        rrdid = 0

        while True:
            params = {
                'dateFrom': self._format_date(date_from),
                'dateTo': self._format_date(date_to),
                'limit': limit,
                'rrdid': rrdid,
            }
            data = self._get(url, params=params)

            if not data:
                break

            all_records.extend(data)
            logger.info(f"reportDetailByPeriod: fetched {len(data)} records (total {len(all_records)}, rrdid={rrdid})")

            if len(data) < limit:
                break

            # Next page: rrdid = last record's rrd_id
            rrdid = data[-1].get('rrd_id', 0)
            if rrdid == 0:
                break

        logger.info(f"reportDetailByPeriod: total {len(all_records)} records for {date_from} — {date_to}")
        return all_records

    # --- Sales ---

    def get_sales(self, date_from, flag=0):
        """
        Get sales data.

        Args:
            date_from: Start date (RFC3339 or datetime). Returns data from this date onward.
            flag: 0 = all new since dateFrom, 1 = updated since last request.

        Returns:
            list: Sales records.
        """
        url = f"{self.BASE_URLS['statistics']}/supplier/sales"
        params = {
            'dateFrom': self._format_date(date_from),
            'flag': flag,
        }
        data = self._get(url, params=params, rate_key='sales')
        logger.info(f"get_sales: {len(data)} records from {date_from}")
        return data or []

    # --- Orders ---

    def get_orders(self, date_from, flag=0):
        """
        Get orders data.

        Args:
            date_from: Start date.
            flag: 0 = new orders, 1 = updated.

        Returns:
            list: Order records.
        """
        url = f"{self.BASE_URLS['statistics']}/supplier/orders"
        params = {
            'dateFrom': self._format_date(date_from),
            'flag': flag,
        }
        data = self._get(url, params=params, rate_key='orders')
        logger.info(f"get_orders: {len(data)} records from {date_from}")
        return data or []

    # --- Stocks ---

    def get_stocks(self, date_from):
        """
        Get warehouse stock data.

        Args:
            date_from: Date (returns stocks as of this date).

        Returns:
            list: Stock records.
        """
        url = f"{self.BASE_URLS['statistics']}/supplier/stocks"
        params = {'dateFrom': self._format_date(date_from)}
        data = self._get(url, params=params)
        logger.info(f"get_stocks: {len(data)} records")
        return data or []

    # --- Incomes ---

    def get_incomes(self, date_from):
        """
        Get income (supply) records.

        Args:
            date_from: Start date.

        Returns:
            list: Income records.
        """
        url = f"{self.BASE_URLS['statistics']}/supplier/incomes"
        params = {'dateFrom': self._format_date(date_from)}
        data = self._get(url, params=params)
        logger.info(f"get_incomes: {len(data)} records")
        return data or []

    # --- Content cards (nomenclature) ---

    def get_content_cards(self, limit=100):
        """
        Get product cards (nomenclature) with pagination via cursor.

        Args:
            limit: Cards per page (max 100).

        Returns:
            list: All product cards.
        """
        url = f"{self.BASE_URLS['content']}/content/v2/get/cards/list"
        all_cards = []
        cursor = {'limit': limit}

        while True:
            body = {
                'settings': {
                    'cursor': cursor,
                    'filter': {'withPhoto': -1},
                },
            }
            resp = self._post(url, json_data=body)
            cards = resp.get('cards', [])
            if not cards:
                break

            all_cards.extend(cards)
            logger.info(f"get_content_cards: fetched {len(cards)} cards (total {len(all_cards)})")

            cursor_data = resp.get('cursor', {})
            if not cursor_data.get('total', 0):
                break

            cursor = {
                'limit': limit,
                'updatedAt': cursor_data.get('updatedAt', ''),
                'nmID': cursor_data.get('nmID', 0),
            }
            if not cursor['updatedAt']:
                break

        logger.info(f"get_content_cards: total {len(all_cards)} cards")
        return all_cards

    # --- Advertising statistics ---

    def get_adv_statistics(self, date_from, date_to):
        """
        Get advertising campaign statistics (fullstats).

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            list: Advertising statistics records.
        """
        # First, get list of active campaigns
        campaigns = self._get_adv_campaigns()
        if not campaigns:
            logger.info("get_adv_statistics: no campaigns found")
            return []

        campaign_ids = [c['advertId'] for c in campaigns]
        logger.info(f"get_adv_statistics: found {len(campaign_ids)} campaigns")

        # Get fullstats for campaigns (max 100 per request)
        all_stats = []
        for i in range(0, len(campaign_ids), 100):
            batch = campaign_ids[i:i + 100]
            url = f"{self.BASE_URLS['advert']}/fullstats"
            body = batch
            params = {}
            if isinstance(date_from, datetime):
                params['dateFrom'] = date_from.strftime('%Y-%m-%d')
                params['dateTo'] = date_to.strftime('%Y-%m-%d')
            else:
                params['dateFrom'] = str(date_from)
                params['dateTo'] = str(date_to)

            try:
                stats = self._post(
                    f"{url}?dateFrom={params['dateFrom']}&dateTo={params['dateTo']}",
                    json_data=body,
                )
                if isinstance(stats, list):
                    all_stats.extend(stats)
            except Exception as e:
                logger.warning(f"get_adv_statistics batch error: {e}")

        logger.info(f"get_adv_statistics: {len(all_stats)} campaign stat entries")
        return all_stats

    # --- Content analysis (organic funnel: card views -> cart -> order -> buyout) ---

    def get_nm_report(self, date_from, date_to):
        """
        Get card analytics (content_analysis): views, add_to_cart, orders, buyouts per SKU per day.
        WB Seller Analytics API: /api/v2/nm-report/detail

        Args:
            date_from: Start date (YYYY-MM-DD or datetime).
            date_to: End date (YYYY-MM-DD or datetime).

        Returns:
            list: Card analytics records.
        """
        url = f"{self.BASE_URLS['analytics']}/nm-report/detail"
        all_cards = []
        page = 1

        begin = str(date_from)[:10] if not isinstance(date_from, str) else date_from[:10]
        end = str(date_to)[:10] if not isinstance(date_to, str) else date_to[:10]

        while True:
            body = {
                "period": {"begin": begin, "end": end},
                "page": page,
            }
            try:
                resp = self._post(url, json_data=body)
            except Exception as e:
                logger.warning(f"get_nm_report page {page} error: {e}")
                break

            if not resp:
                break

            cards = resp.get('data', {}).get('cards', [])
            if not cards:
                break

            all_cards.extend(cards)
            logger.info(f"get_nm_report: page {page}, {len(cards)} cards (total {len(all_cards)})")

            if not resp.get('data', {}).get('isNextPage', False):
                break
            page += 1

        logger.info(f"get_nm_report: total {len(all_cards)} cards for {begin} — {end}")
        return all_cards

    def _get_adv_campaigns(self):
        """Get list of all advertising campaigns."""
        url = f"{self.BASE_URLS['advert']}/adverts"
        try:
            data = self._get(url)
            if isinstance(data, list):
                # Flatten: each element has 'advert_list'
                campaigns = []
                for group in data:
                    campaigns.extend(group.get('advert_list', []))
                return campaigns
            return []
        except Exception as e:
            logger.warning(f"_get_adv_campaigns error: {e}")
            return []


# Example usage:
if __name__ == '__main__':
    from services.marketplace_etl.config.database import get_accounts

    accounts = get_accounts()
    for acc in accounts.get('wb', []):
        client = WildberriesAPIClient(api_key=acc['api_key'], lk=acc['lk'])
        if client.test_connection():
            print(f"WB API connection successful for {acc['lk']}")
        else:
            print(f"WB API connection failed for {acc['lk']}")
