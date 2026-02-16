"""
Wildberries ETL Process.

Extract data from WB API -> Transform (field mapping) -> Load to PostgreSQL (UPSERT).
Supports multiple legal entities (one API key per LK).
"""

import logging
import argparse
from datetime import datetime, timedelta

from psycopg2.extras import execute_values

from services.marketplace_etl.api_clients.wb_client import WildberriesAPIClient
from services.marketplace_etl.config.database import get_db_connection, get_accounts

logger = logging.getLogger(__name__)


class WildberriesETL:
    """ETL process for Wildberries data."""

    def __init__(self, api_key, lk):
        """
        Args:
            api_key: WB API Bearer token.
            lk: Legal entity name (e.g. 'WB ИП Медведева П.В.').
        """
        self.client = WildberriesAPIClient(api_key=api_key, lk=lk)
        self.lk = lk

    # ================================================================
    # EXTRACT
    # ================================================================

    def extract(self, date_from, date_to):
        """
        Extract data from all WB API endpoints.

        Returns:
            dict with keys: report_detail, sales, orders, stocks, nomenclature, adv
        """
        logger.info(f"[{self.lk}] Extracting WB data {date_from} — {date_to}")

        data = {}

        # reportDetailByPeriod — main financial data for abc_date
        data['report_detail'] = self.client.get_report_detail_by_period(date_from, date_to)

        # Sales
        data['sales'] = self.client.get_sales(date_from)

        # Orders
        data['orders'] = self.client.get_orders(date_from)

        # Stocks (snapshot for today)
        data['stocks'] = self.client.get_stocks(date_from)

        # Nomenclature (product cards)
        data['nomenclature'] = self.client.get_content_cards()

        # Advertising statistics
        data['adv'] = self.client.get_adv_statistics(date_from, date_to)

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
            dict with keys matching table names: abc_date, orders, sales, stocks, nomenclature, wb_adv
        """
        logger.info(f"[{self.lk}] Transforming WB data")

        transformed = {
            'abc_date': self._transform_report_detail(raw_data.get('report_detail', [])),
            'orders': self._transform_orders(raw_data.get('orders', [])),
            'sales': self._transform_sales(raw_data.get('sales', [])),
            'stocks': self._transform_stocks(raw_data.get('stocks', [])),
            'nomenclature': self._transform_nomenclature(raw_data.get('nomenclature', [])),
            'wb_adv': self._transform_adv(raw_data.get('adv', [])),
        }

        for key, records in transformed.items():
            logger.info(f"[{self.lk}] Transformed {key}: {len(records)} records")

        return transformed

    def _transform_report_detail(self, records):
        """
        Transform reportDetailByPeriod API response to wb.abc_date rows.
        API returns per-transaction rows; we aggregate by (date, article, barcode).
        """
        if not records:
            return []

        # Aggregate by (date, article, barcode)
        aggregated = {}
        for r in records:
            rr_dt = r.get('rr_dt', r.get('date_from', ''))
            date_str = rr_dt[:10] if rr_dt else ''
            article = r.get('sa_name', r.get('supplierArticle', ''))
            barcode = r.get('barcode', '')

            key = (date_str, article, barcode)
            if key not in aggregated:
                aggregated[key] = {
                    'date': date_str,
                    'article': article,
                    'barcode': barcode,
                    'nm_id': r.get('nm_id', 0),
                    'ts_name': r.get('ts_name', ''),
                    # Financial accumulators
                    'retail_amount': 0,        # ppvz_for_pay or retail_amount
                    'delivery_rub': 0,         # delivery_rub (logistics)
                    'commission': 0,           # ppvz_vw_nds (commission)
                    'penalty': 0,
                    'additional_payment': 0,
                    'storage_fee': 0,          # storage_fee
                    'deduction': 0,
                    'acceptance': 0,           # acceptance (приемка)
                    'sale_qty': 0,
                    'return_qty': 0,
                    'return_amount': 0,
                    'ppvz_spp_prc': 0,         # SPP percentage
                    'ppvz_for_pay': 0,
                    'retail_price': 0,
                    'sale_count': 0,
                    'rebill_logistic_cost': 0,
                }

            agg = aggregated[key]

            # Determine if this is a sale or return
            doc_type_name = r.get('doc_type_name', '')
            quantity = r.get('quantity', 0)

            if 'Возврат' in doc_type_name:
                agg['return_qty'] += abs(quantity)
                agg['return_amount'] += abs(r.get('ppvz_for_pay', 0))
            else:
                agg['sale_qty'] += abs(quantity)

            agg['ppvz_for_pay'] += r.get('ppvz_for_pay', 0)
            agg['retail_amount'] += r.get('retail_amount', 0)
            agg['delivery_rub'] += r.get('delivery_rub', 0)
            agg['commission'] += r.get('ppvz_vw_nds', 0)
            agg['penalty'] += r.get('penalty', 0)
            agg['additional_payment'] += r.get('additional_payment', 0)
            agg['storage_fee'] += r.get('storage_fee', 0)
            agg['deduction'] += r.get('deduction', 0)
            agg['acceptance'] += r.get('acceptance', 0)
            agg['rebill_logistic_cost'] += r.get('rebill_logistic_cost', 0)
            agg['retail_price'] = r.get('retail_price', 0) or agg['retail_price']
            agg['sale_count'] += 1

            ppvz_spp_prc = r.get('ppvz_spp_prc', 0) or 0
            if ppvz_spp_prc and not agg['ppvz_spp_prc']:
                agg['ppvz_spp_prc'] = ppvz_spp_prc

        # Build abc_date rows
        result = []
        for key, agg in aggregated.items():
            # revenue_spp = retail_amount (before SPP)
            revenue_spp = agg['retail_amount']
            # spp amount
            spp_prc = agg['ppvz_spp_prc'] / 100 if agg['ppvz_spp_prc'] else 0
            spp_amount = revenue_spp * spp_prc
            revenue = revenue_spp - spp_amount  # after SPP

            # Commission before SPP ~ ppvz_vw_nds
            comis_spp = agg['commission']
            logist = agg['delivery_rub']
            penalty = agg['penalty']
            deduction = agg['deduction']

            row = {
                'date': agg['date'],
                'lk': self.lk,
                'article': agg['article'],
                'barcode': agg['barcode'],
                'nm_id': agg['nm_id'],
                'ts_name': agg['ts_name'],
                'mp': 'wb',
                'revenue_spp': revenue_spp,
                'revenue': revenue,
                'spp': spp_amount,
                'full_counts': agg['sale_qty'],
                'count_return': agg['return_qty'],
                'returns': agg['return_amount'],
                'comis_spp': comis_spp,
                'comis': comis_spp * (1 - spp_prc) if spp_prc else comis_spp,
                'logist': logist,
                'sebes': 0,  # From Google Sheets, not from API
                'reclama': 0,  # Filled from wb_adv join
                'reclama_vn': 0,
                'storage': agg['storage_fee'],
                'nds': 0,  # Calculated separately or from API
                'penalty': penalty,
                'retention': agg['acceptance'],
                'deduction': deduction,
                'retail_price': agg['retail_price'],
                'rebill_logistic_cost': agg['rebill_logistic_cost'],
            }
            result.append(row)

        return result

    def _transform_orders(self, records):
        """Transform orders API response to wb.orders rows."""
        result = []
        for r in records:
            row = {
                'date': r.get('date'),
                'lastchangedate': r.get('lastChangeDate'),
                'supplierarticle': r.get('supplierArticle', ''),
                'techsize': r.get('techSize', ''),
                'barcode': r.get('barcode', ''),
                'totalprice': r.get('totalPrice', 0),
                'discountpercent': r.get('discountPercent', 0),
                'spp': r.get('spp', 0),
                'finishedprice': r.get('finishedPrice', 0),
                'pricewithdisc': r.get('priceWithDisc', 0),
                'warehousename': r.get('warehouseName', ''),
                'oblast': r.get('oblast', ''),
                'region': r.get('region', ''),
                'regionname': r.get('regionName', ''),
                'country': r.get('country', ''),
                'nmid': r.get('nmId', 0),
                'subject': r.get('subject', ''),
                'category': r.get('category', ''),
                'brand': r.get('brand', ''),
                'iscancel': str(r.get('isCancel', '')),
                'cancel_dt': r.get('cancel_dt'),
                'gnumber': r.get('gNumber', ''),
                'gnumberid': r.get('supplierArticle', ''),
                'sticker': r.get('sticker', ''),
                'srid': r.get('srid', ''),
                'ordertype': r.get('orderType', 'Клиентский'),
                'lk': self.lk,
            }
            result.append(row)
        return result

    def _transform_sales(self, records):
        """Transform sales API response to wb.sales rows."""
        result = []
        for r in records:
            row = {
                'date': r.get('date'),
                'lastchangedate': r.get('lastChangeDate'),
                'supplierarticle': r.get('supplierArticle', ''),
                'techsize': r.get('techSize', ''),
                'barcode': r.get('barcode', ''),
                'totalprice': r.get('totalPrice', 0),
                'discountpercent': r.get('discountPercent', 0),
                'spp': r.get('spp', 0),
                'forpay': r.get('forPay', 0),
                'finishedprice': r.get('finishedPrice', 0),
                'pricewithdisc': r.get('priceWithDisc', 0),
                'warehousename': r.get('warehouseName', ''),
                'countryname': r.get('countryName', ''),
                'oblastokrugname': r.get('oblastOkrugName', ''),
                'regionname': r.get('regionName', ''),
                'nmid': r.get('nmId', 0),
                'subject': r.get('subject', ''),
                'category': r.get('category', ''),
                'brand': r.get('brand', ''),
                'isstorno': r.get('IsStorno', 0),
                'gnumber': r.get('gNumber', ''),
                'saleid': r.get('saleID', ''),
                'srid': r.get('srid', ''),
                'lk': self.lk,
                'paymentsaleamount': r.get('paymentSaleAmount', 0),
            }
            result.append(row)
        return result

    def _transform_stocks(self, records):
        """Transform stocks API response to wb.stocks rows."""
        result = []
        for r in records:
            row = {
                'lastchangedate': r.get('lastChangeDate'),
                'supplierarticle': r.get('supplierArticle', ''),
                'techsize': r.get('techSize', ''),
                'barcode': r.get('barcode', ''),
                'quantity': r.get('quantity', 0),
                'issupply': str(r.get('isSupply', '')),
                'isrealization': str(r.get('isRealization', '')),
                'quantityfull': r.get('quantityFull', 0),
                'warehousename': r.get('warehouseName', ''),
                'nmid': r.get('nmId', 0),
                'subject': r.get('subject', ''),
                'category': r.get('category', ''),
                'daysonsite': r.get('daysOnSite', 0),
                'brand': r.get('brand', ''),
                'sccode': r.get('SCCode', ''),
                'price': r.get('Price', 0),
                'discount': r.get('Discount', 0),
                'lk': self.lk,
            }
            result.append(row)
        return result

    def _transform_nomenclature(self, records):
        """Transform content cards API response to wb.nomenclature rows."""
        result = []
        for r in records:
            sizes = r.get('sizes', [{}])
            barcodes = []
            for s in sizes:
                barcodes.extend(s.get('skus', []))
            barcode = barcodes[0] if barcodes else ''

            row = {
                'vendorcode': r.get('vendorCode', ''),
                'nmid': r.get('nmID', 0),
                'brand': r.get('brand', ''),
                'object': r.get('subjectName', ''),
                'title': r.get('title', ''),
                'barcod': barcode,
                'colors': ','.join(r.get('colors', [])) if isinstance(r.get('colors'), list) else str(r.get('colors', '')),
                'techsize': sizes[0].get('techSize', '') if sizes else '',
                'chrtid': str(sizes[0].get('chrtID', '')) if sizes else '',
                'imtid': str(r.get('imtID', '')),
                'video': r.get('video', ''),
                'tags': ','.join(r.get('tags', [])) if isinstance(r.get('tags'), list) else '',
                'description': r.get('description', ''),
                'link_card': '',
                'mediafiles': ','.join(r.get('photos', [])) if isinstance(r.get('photos'), list) else '',
                'lk': self.lk,
                'createdat': r.get('createdAt', '')[:10] if r.get('createdAt') else None,
                'updateat': r.get('updatedAt', '')[:10] if r.get('updatedAt') else None,
            }
            result.append(row)
        return result

    def _transform_adv(self, records):
        """Transform advertising statistics to wb.wb_adv rows."""
        result = []
        for campaign in records:
            advert_id = campaign.get('advertId', 0)
            name_rk = campaign.get('name', '')
            days = campaign.get('days', [])
            for day in days:
                date_str = day.get('date', '')[:10]
                apps = day.get('apps', [])
                for app in apps:
                    nm_items = app.get('nm', [])
                    for nm_item in nm_items:
                        row = {
                            'date': date_str,
                            'nmid': nm_item.get('nmId', 0),
                            'views': nm_item.get('views', 0),
                            'clicks': nm_item.get('clicks', 0),
                            'sum': nm_item.get('sum', 0),
                            'atbs': nm_item.get('atbs', 0),
                            'orders': nm_item.get('orders', 0),
                            'ctr': nm_item.get('ctr', 0),
                            'cpc': nm_item.get('cpc', 0),
                            'cr': nm_item.get('cr', 0),
                            'frq': nm_item.get('frq', 0),
                            'shks': nm_item.get('shks', 0),
                            'unique_users': nm_item.get('unique_users', 0),
                            'canceled': 0,
                            'advertid': advert_id,
                            'name_rk': name_rk,
                            'lk': self.lk,
                        }
                        result.append(row)
        return result

    # ================================================================
    # LOAD
    # ================================================================

    def load(self, transformed_data):
        """Load transformed data to PostgreSQL using UPSERT."""
        logger.info(f"[{self.lk}] Loading WB data to database")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            self._load_table(cursor, 'wb.abc_date', transformed_data.get('abc_date', []),
                             conflict_columns=['date', 'article', 'barcode', 'lk'])
            self._load_table(cursor, 'wb.orders', transformed_data.get('orders', []),
                             conflict_columns=['srid', 'lk'])
            self._load_table(cursor, 'wb.sales', transformed_data.get('sales', []),
                             conflict_columns=['srid', 'lk'])
            self._load_table(cursor, 'wb.stocks', transformed_data.get('stocks', []),
                             conflict_columns=['dateupdate', 'barcode', 'warehousename', 'lk'])
            self._load_table(cursor, 'wb.nomenclature', transformed_data.get('nomenclature', []),
                             conflict_columns=['nmid', 'barcod', 'lk'])
            self._load_table(cursor, 'wb.wb_adv', transformed_data.get('wb_adv', []),
                             conflict_columns=['date', 'nmid', 'advertid', 'lk'])

            conn.commit()
            logger.info(f"[{self.lk}] WB data loaded successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"[{self.lk}] Error loading WB data: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _load_table(self, cursor, table_name, rows, conflict_columns):
        """
        UPSERT rows into table using execute_values.

        Args:
            cursor: psycopg2 cursor.
            table_name: Full table name (e.g. 'wb.abc_date').
            rows: List of dicts.
            conflict_columns: Columns for ON CONFLICT.
        """
        if not rows:
            logger.info(f"  {table_name}: 0 rows, skipping")
            return

        columns = list(rows[0].keys())
        # Remove dateupdate/date_update from insert — let DB default handle it
        skip_cols = {'dateupdate', 'date_update'}
        columns = [c for c in columns if c not in skip_cols]

        update_columns = [c for c in columns if c not in conflict_columns]

        placeholders = ', '.join(['%s'] * len(columns))
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
        logger.info(f"[{self.lk}] Starting WB ETL: {date_from} -> {date_to}")

        raw_data = self.extract(date_from, date_to)
        transformed_data = self.transform(raw_data)
        self.load(transformed_data)

        logger.info(f"[{self.lk}] WB ETL completed")


def run_all_accounts(date_from, date_to):
    """Run ETL for all WB accounts."""
    accounts = get_accounts()
    wb_accounts = accounts.get('wb', [])

    if not wb_accounts:
        logger.error("No WB accounts configured")
        return

    for acc in wb_accounts:
        logger.info(f"Processing WB account: {acc['lk']}")
        etl = WildberriesETL(api_key=acc['api_key'], lk=acc['lk'])
        etl.run(date_from, date_to)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')

    parser = argparse.ArgumentParser(description='Wildberries ETL')
    parser.add_argument('--date-from', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--date-to', required=True, help='End date (YYYY-MM-DD)')

    args = parser.parse_args()
    run_all_accounts(args.date_from, args.date_to)


if __name__ == '__main__':
    main()
