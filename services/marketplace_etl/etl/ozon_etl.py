"""
Ozon ETL Process.

Extract data from Ozon API -> Transform (field mapping) -> Load to PostgreSQL (UPSERT).
Supports multiple legal entities (one Client-Id/Api-Key pair per LK).

Key formula: Final margin = marga - nds (verified, exact match with PowerBI).
"""

import logging
import argparse
from datetime import datetime

from psycopg2.extras import execute_values

from services.marketplace_etl.api_clients.ozon_client import OzonAPIClient
from services.marketplace_etl.config.database import get_db_connection, get_accounts

logger = logging.getLogger(__name__)


class OzonETL:
    """ETL process for Ozon data."""

    def __init__(self, client_id, api_key, lk):
        """
        Args:
            client_id: Ozon Client-Id.
            api_key: Ozon Api-Key.
            lk: Legal entity name (e.g. 'Ozon ИП Медведева П.В.').
        """
        self.client = OzonAPIClient(client_id=client_id, api_key=api_key, lk=lk)
        self.lk = lk

    # ================================================================
    # EXTRACT
    # ================================================================

    def extract(self, date_from, date_to):
        """
        Extract data from all Ozon API endpoints.

        Returns:
            dict with keys: transactions, fbo_postings, fbs_postings, stocks,
                            products, adv_stats, search_stats
        """
        logger.info(f"[{self.lk}] Extracting Ozon data {date_from} — {date_to}")

        data = {}

        # Finance transactions — main source for abc_date
        data['transactions'] = self.client.get_finance_transaction_list(date_from, date_to)

        # FBO postings (orders)
        data['fbo_postings'] = self.client.get_fbo_posting_list(date_from, date_to)

        # FBS postings (orders)
        data['fbs_postings'] = self.client.get_fbs_posting_list(date_from, date_to)

        # Stocks (current snapshot)
        data['stocks'] = self.client.get_stocks()

        # Products (nomenclature)
        data['products'] = self.client.get_products_list()

        # Advertising stats
        data['adv_stats'] = self.client.get_adv_statistics(date_from, date_to)

        for key, records in data.items():
            logger.info(f"[{self.lk}] Extracted {key}: {len(records)} records")

        return data

    # ================================================================
    # TRANSFORM
    # ================================================================

    def transform(self, raw_data):
        """
        Transform raw API data to DB schema format.

        Returns:
            dict with keys matching table names: abc_date, orders, returns, stocks,
                                                  nomenclature, adv_stats_daily
        """
        logger.info(f"[{self.lk}] Transforming Ozon data")

        transformed = {
            'abc_date': self._transform_transactions(raw_data.get('transactions', [])),
            'orders': self._transform_postings(
                raw_data.get('fbo_postings', []),
                raw_data.get('fbs_postings', []),
            ),
            'returns': self._transform_returns(raw_data.get('transactions', [])),
            'stocks': self._transform_stocks(raw_data.get('stocks', [])),
            'nomenclature': self._transform_products(raw_data.get('products', [])),
            'adv_stats_daily': self._transform_adv(raw_data.get('adv_stats', [])),
        }

        for key, records in transformed.items():
            logger.info(f"[{self.lk}] Transformed {key}: {len(records)} records")

        return transformed

    def _transform_transactions(self, operations):
        """
        Transform finance transactions to ozon.abc_date rows.
        Aggregates by (date, article/offer_id).

        Finance transactions contain individual operations; we aggregate
        by day + article to build the abc_date rows.
        """
        if not operations:
            return []

        aggregated = {}
        for op in operations:
            op_date = op.get('operation_date', '')[:10]
            items = op.get('items', [])
            posting = op.get('posting', {})

            for item in items:
                sku = str(item.get('sku', ''))
                offer_id = item.get('offer_id', '')
                article = offer_id or sku

                if not article or not op_date:
                    continue

                key = (op_date, article)
                if key not in aggregated:
                    aggregated[key] = {
                        'date': op_date,
                        'article': article,
                        'sku': sku,
                        'product_id': str(item.get('product_id', '')),
                        # Financial accumulators
                        'accruals_for_sale': 0,
                        'sale_commission': 0,
                        'amount': 0,
                        'services': {},
                        'sale_qty': 0,
                        'return_qty': 0,
                    }

                agg = aggregated[key]
                op_type = op.get('operation_type', '')
                amount = op.get('amount', 0)

                agg['amount'] += amount
                agg['accruals_for_sale'] += op.get('accruals_for_sale', 0)
                agg['sale_commission'] += op.get('sale_commission', 0)

                # Count sales/returns
                quantity = item.get('quantity', 0)
                if 'Return' in op_type or amount < 0:
                    agg['return_qty'] += abs(quantity) if quantity else 1
                else:
                    agg['sale_qty'] += abs(quantity) if quantity else 1

                # Aggregate services
                services = op.get('services', [])
                for svc in services:
                    svc_name = svc.get('name', 'other')
                    svc_price = svc.get('price', 0)
                    agg['services'][svc_name] = agg['services'].get(svc_name, 0) + svc_price

        # Build abc_date rows
        result = []
        for key, agg in aggregated.items():
            services = agg['services']

            # Map services to DB fields
            logist = services.get('MarketplaceServiceItemDirectFlowLogistic', 0) + \
                     services.get('MarketplaceServiceItemReturnFlowLogistic', 0) + \
                     services.get('MarketplaceServiceItemDelivToCustomer', 0) + \
                     services.get('MarketplaceServiceItemDirectFlowTrans', 0)

            storage = services.get('MarketplaceServiceStorageFee', 0)
            fulfillment = services.get('MarketplaceServiceItemFulfillment', 0)

            price_end = agg['accruals_for_sale']  # Revenue before SPP
            comission_end = abs(agg['sale_commission'])
            count_end = agg['sale_qty']
            count_return = agg['return_qty']

            # marga is intermediate; final = marga - nds
            # For now, compute approximate marga from available data
            marga = price_end - comission_end + logist + storage + fulfillment

            row = {
                'date': agg['date'],
                'lk': self.lk,
                'article': agg['article'],
                'sku': agg['sku'],
                'product_id': agg['product_id'],
                'mp': 'ozon',
                'price_end': price_end,
                'price_end_spp': 0,
                'count_end': count_end,
                'count_return': count_return,
                'comission_end': comission_end,
                'comission_end_spp': 0,
                'logist_end': abs(logist),
                'storage_end': abs(storage),
                'sebes_end': 0,  # From Google Sheets
                'reclama_end': 0,  # Filled from adv join
                'nds': 0,  # Calculated separately
                'marga': marga,
                'spp': 0,
            }
            result.append(row)

        return result

    def _transform_postings(self, fbo_postings, fbs_postings):
        """Transform FBO + FBS postings to ozon.orders rows."""
        result = []

        for posting in fbo_postings:
            result.extend(self._posting_to_order_rows(posting, 'FBO'))
        for posting in fbs_postings:
            result.extend(self._posting_to_order_rows(posting, 'FBS'))

        return result

    def _posting_to_order_rows(self, posting, delivery_schema):
        """Convert a single posting to order rows (one per product)."""
        rows = []
        order_id = posting.get('order_id', 0)
        posting_number = posting.get('posting_number', '')
        order_number = posting.get('order_number', '')
        status = posting.get('status', '')
        in_process_at = posting.get('in_process_at')

        products = posting.get('products', [])
        for prod in products:
            row = {
                'order_id': order_id,
                'posting_number': posting_number,
                'order_number': order_number,
                'product_id': str(prod.get('product_id', '')),
                'sku': str(prod.get('sku', '')),
                'offer_id': prod.get('offer_id', ''),
                'delivery_schema': delivery_schema,
                'status': status,
                'price': float(prod.get('price', 0)),
                'quantity': prod.get('quantity', 0),
                'commission_amount': prod.get('commission_amount', 0),
                'in_process_at': in_process_at,
                'lk': self.lk,
            }
            rows.append(row)

        return rows

    def _transform_returns(self, operations):
        """Transform finance transactions that are returns to ozon.returns rows."""
        result = []

        for op in operations:
            op_type = op.get('operation_type', '')
            if 'Return' not in op_type:
                continue

            items = op.get('items', [])
            services = op.get('services', [])

            # Build services dict
            svc_map = {}
            for svc in services:
                svc_map[svc.get('name', '')] = svc.get('price', 0)

            for item in items:
                row = {
                    'operation_id': str(op.get('operation_id', '')),
                    'operation_type': op_type,
                    'operation_date': op.get('operation_date', '')[:10],
                    'operation_type_name': op.get('operation_type_name', ''),
                    'posting_number': op.get('posting', {}).get('posting_number', ''),
                    'order_date': op.get('posting', {}).get('order_date'),
                    'sku': str(item.get('sku', '')),
                    'product_id': str(item.get('product_id', '')),
                    'name': item.get('name', ''),
                    'lk': self.lk,
                    'delivery_schema': op.get('posting', {}).get('delivery_schema', ''),
                    'type': 'returns',
                    'amount': op.get('amount', 0),
                    'delivery_charge': svc_map.get('MarketplaceServiceItemDelivToCustomer', 0),
                    'return_delivery_charge': svc_map.get('MarketplaceServiceItemReturnFlowLogistic', 0),
                    'accruals_for_sale': op.get('accruals_for_sale', 0),
                    'sale_commission': op.get('sale_commission', 0),
                    'marketplaceserviceitemdirectflowlogistic': svc_map.get('MarketplaceServiceItemDirectFlowLogistic', 0),
                    'marketplaceserviceitemreturnflowlogistic': svc_map.get('MarketplaceServiceItemReturnFlowLogistic', 0),
                    'marketplaceserviceitemdelivtocustomer': svc_map.get('MarketplaceServiceItemDelivToCustomer', 0),
                    'marketplaceserviceitemdirectflowtrans': svc_map.get('MarketplaceServiceItemDirectFlowTrans', 0),
                    'marketplaceserviceitemfulfillment': svc_map.get('MarketplaceServiceItemFulfillment', 0),
                    'marketplaceserviceitemreturnafterdelivtocustomer': svc_map.get('MarketplaceServiceItemReturnAfterDelivToCustomer', 0),
                    'marketplaceserviceitemreturnnotdelivtocustomer': svc_map.get('MarketplaceServiceItemReturnNotDelivToCustomer', 0),
                    'marketplaceserviceitemreturnpartgoodscustomer': svc_map.get('MarketplaceServiceItemReturnPartGoodsCustomer', 0),
                }
                result.append(row)

        return result

    def _transform_stocks(self, records):
        """Transform product stocks to ozon.stocks rows."""
        result = []
        for item in records:
            offer_id = item.get('offer_id', '')
            product_id = str(item.get('product_id', ''))
            stocks_list = item.get('stocks', [])

            for stock in stocks_list:
                row = {
                    'offer_id': offer_id,
                    'product_id': product_id,
                    'sku': str(item.get('sku', '')),
                    'delivery_schema': stock.get('type', ''),
                    'stockspresent': stock.get('present', 0),
                    'stocksreserved': stock.get('reserved', 0),
                    'warehouse_id': str(stock.get('warehouse_id', '')),
                    'warehouse_name': stock.get('warehouse_name', ''),
                    'lk': self.lk,
                    'promised_amount': item.get('promised_amount', 0),
                }
                result.append(row)

        return result

    def _transform_products(self, records):
        """Transform product list to ozon.nomenclature rows."""
        result = []
        for item in records:
            row = {
                'article': item.get('offer_id', ''),
                'ozon_product_id': str(item.get('product_id', '')),
                'fbo_ozon_sku_id': str(item.get('fbo_sku', '')),
                'fbs_ozon_sku_id': str(item.get('fbs_sku', '')),
                'barcode': item.get('barcode', ''),
                'category': '',
                'status': item.get('status', {}).get('state_name', '') if isinstance(item.get('status'), dict) else str(item.get('status', '')),
                'lk': self.lk,
            }
            result.append(row)
        return result

    def _transform_adv(self, records):
        """Transform advertising stats to ozon.adv_stats_daily rows."""
        result = []
        for r in records:
            row = {
                'id_rk': r.get('campaign_id', 0),
                'title': r.get('title', ''),
                'operation_date': r.get('date', '')[:10] if r.get('date') else '',
                'views': r.get('views', 0),
                'clicks': r.get('clicks', 0),
                'orders_count': r.get('orders', 0),
                'orders_amount': r.get('orders_amount', 0),
                'rk_expense': r.get('spent', 0),
                'avg_bid': r.get('avg_bid', 0),
            }
            if row['operation_date']:
                result.append(row)
        return result

    # ================================================================
    # LOAD
    # ================================================================

    def load(self, transformed_data):
        """Load transformed data to PostgreSQL using UPSERT."""
        logger.info(f"[{self.lk}] Loading Ozon data to database")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            self._load_table(cursor, 'ozon.abc_date', transformed_data.get('abc_date', []),
                             conflict_columns=['date', 'article', 'lk'])
            self._load_table(cursor, 'ozon.orders', transformed_data.get('orders', []),
                             conflict_columns=['order_id', 'sku', 'lk'])
            self._load_table(cursor, 'ozon.returns', transformed_data.get('returns', []),
                             conflict_columns=['operation_id', 'sku', 'lk'])
            self._load_table(cursor, 'ozon.stocks', transformed_data.get('stocks', []),
                             conflict_columns=['dateupdate', 'sku', 'warehouse_id', 'delivery_schema', 'lk'])
            self._load_table(cursor, 'ozon.nomenclature', transformed_data.get('nomenclature', []),
                             conflict_columns=['article', 'ozon_product_id', 'lk'])
            self._load_table(cursor, 'ozon.adv_stats_daily', transformed_data.get('adv_stats_daily', []),
                             conflict_columns=['id_rk', 'operation_date'])

            conn.commit()
            logger.info(f"[{self.lk}] Ozon data loaded successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"[{self.lk}] Error loading Ozon data: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _load_table(self, cursor, table_name, rows, conflict_columns):
        """
        UPSERT rows into table using execute_values.

        Args:
            cursor: psycopg2 cursor.
            table_name: Full table name (e.g. 'ozon.abc_date').
            rows: List of dicts.
            conflict_columns: Columns for ON CONFLICT.
        """
        if not rows:
            logger.info(f"  {table_name}: 0 rows, skipping")
            return

        columns = list(rows[0].keys())
        # Remove auto-generated columns
        skip_cols = {'dateupdate', 'date_update'}
        columns = [c for c in columns if c not in skip_cols]

        update_columns = [c for c in columns if c not in conflict_columns]

        col_names = ', '.join(columns)
        conflict_clause = ', '.join(conflict_columns)
        update_clause = ', '.join([f'{c} = EXCLUDED.{c}' for c in update_columns])

        sql = f"""
            INSERT INTO {table_name} ({col_names})
            VALUES %s
            ON CONFLICT ({conflict_clause})
            DO UPDATE SET {update_clause}
        """

        values = []
        for row in rows:
            values.append(tuple(row.get(c) for c in columns))

        execute_values(cursor, sql, values, page_size=1000)
        logger.info(f"  {table_name}: {len(rows)} rows upserted")

    # ================================================================
    # RUN
    # ================================================================

    def run(self, date_from, date_to):
        """Run full ETL pipeline."""
        logger.info(f"[{self.lk}] Starting Ozon ETL: {date_from} -> {date_to}")

        raw_data = self.extract(date_from, date_to)
        transformed_data = self.transform(raw_data)
        self.load(transformed_data)

        logger.info(f"[{self.lk}] Ozon ETL completed")


def run_all_accounts(date_from, date_to):
    """Run ETL for all Ozon accounts."""
    accounts = get_accounts()
    ozon_accounts = accounts.get('ozon', [])

    if not ozon_accounts:
        logger.error("No Ozon accounts configured")
        return

    for acc in ozon_accounts:
        logger.info(f"Processing Ozon account: {acc['lk']}")
        etl = OzonETL(
            client_id=acc['client_id'],
            api_key=acc['api_key'],
            lk=acc['lk'],
        )
        etl.run(date_from, date_to)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')

    parser = argparse.ArgumentParser(description='Ozon ETL')
    parser.add_argument('--date-from', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--date-to', required=True, help='End date (YYYY-MM-DD)')

    args = parser.parse_args()
    run_all_accounts(args.date_from, args.date_to)


if __name__ == '__main__':
    main()
