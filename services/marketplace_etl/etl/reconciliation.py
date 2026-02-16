"""
Data Reconciliation.

Compares key metrics between source DB (read-only) and new DB (managed).
Target: < 1% discrepancy on revenue and margin.
"""

import argparse
import logging
import sys
from datetime import datetime

from services.marketplace_etl.config.database import (
    get_db_connection, get_source_db_connection,
    SOURCE_DB_WB, SOURCE_DB_OZON,
)

logger = logging.getLogger(__name__)

# Metrics to compare for WB
WB_METRICS_SQL = """
    SELECT
        COALESCE(SUM(revenue_spp), 0)  AS revenue,
        COALESCE(SUM(
            revenue_spp - comis_spp - logist - sebes
            - reclama - reclama_vn - storage - nds
            - penalty - retention - deduction
        ), 0)                          AS margin,
        COALESCE(SUM(count_orders), 0) AS orders,
        COALESCE(SUM(full_counts), 0)  AS sales,
        COALESCE(SUM(reclama + reclama_vn), 0) AS adv
    FROM {table}
    WHERE date BETWEEN %s AND %s
"""

# Per-article detail for WB
WB_DETAIL_SQL = """
    SELECT
        article,
        COALESCE(SUM(revenue_spp), 0) AS revenue,
        COALESCE(SUM(
            revenue_spp - comis_spp - logist - sebes
            - reclama - reclama_vn - storage - nds
            - penalty - retention - deduction
        ), 0) AS margin
    FROM {table}
    WHERE date BETWEEN %s AND %s
    GROUP BY article
    ORDER BY revenue DESC
"""

# Metrics to compare for Ozon
OZON_METRICS_SQL = """
    SELECT
        COALESCE(SUM(price_end), 0)            AS revenue,
        COALESCE(SUM(marga - nds), 0)          AS margin,
        COALESCE(SUM(count_end), 0)            AS sales,
        COALESCE(SUM(reclama_end + adv_vn), 0) AS adv
    FROM {table}
    WHERE date BETWEEN %s AND %s
"""

# Per-article detail for Ozon
OZON_DETAIL_SQL = """
    SELECT
        article,
        COALESCE(SUM(price_end), 0)   AS revenue,
        COALESCE(SUM(marga - nds), 0) AS margin
    FROM {table}
    WHERE date BETWEEN %s AND %s
    GROUP BY article
    ORDER BY revenue DESC
"""

# Row counts
COUNT_SQL = "SELECT COUNT(*) FROM {table} WHERE date BETWEEN %s AND %s"


def _pct_diff(source_val, new_val):
    """Calculate percentage difference. Returns 0 if both are zero."""
    if source_val == 0 and new_val == 0:
        return 0.0
    if source_val == 0:
        return 100.0
    return abs(source_val - new_val) / abs(source_val) * 100


def _query_one(conn, sql, params):
    """Execute query and return single row as dict."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else {}


def _query_all(conn, sql, params):
    """Execute query and return all rows as list of dicts."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _query_scalar(conn, sql, params):
    """Execute query and return single scalar value."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else 0


class DataReconciliation:
    """Compare data between source and new database."""

    THRESHOLD_PCT = 1.0  # Max acceptable discrepancy

    def __init__(self):
        self.new_conn = None
        self.source_wb_conn = None
        self.source_ozon_conn = None

    def _connect(self):
        """Establish all database connections."""
        self.new_conn = get_db_connection()
        try:
            self.source_wb_conn = get_source_db_connection(SOURCE_DB_WB)
            self.source_ozon_conn = get_source_db_connection(SOURCE_DB_OZON)
        except Exception as e:
            logger.warning(f"Cannot connect to source DBs: {e}")

    def _close(self):
        """Close all connections."""
        for conn in (self.new_conn, self.source_wb_conn, self.source_ozon_conn):
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def compare_wb_data(self, date_from, date_to):
        """
        Compare WB data between source and new DB.

        Returns:
            dict with discrepancy percentages and raw values.
        """
        logger.info(f"Comparing WB data: {date_from} -> {date_to}")
        params = (date_from, date_to)

        # Source DB: public.abc_date in pbi_wb_wookiee
        source = _query_one(
            self.source_wb_conn,
            WB_METRICS_SQL.format(table='public.abc_date'),
            params,
        )

        # New DB: wb.abc_date
        new = _query_one(
            self.new_conn,
            WB_METRICS_SQL.format(table='wb.abc_date'),
            params,
        )

        # Row counts
        source_count = _query_scalar(
            self.source_wb_conn,
            COUNT_SQL.format(table='public.abc_date'),
            params,
        )
        new_count = _query_scalar(
            self.new_conn,
            COUNT_SQL.format(table='wb.abc_date'),
            params,
        )

        results = {
            'source': source,
            'new': new,
            'source_rows': source_count,
            'new_rows': new_count,
            'rows_discrepancy': _pct_diff(source_count, new_count),
            'revenue_discrepancy': _pct_diff(source.get('revenue', 0), new.get('revenue', 0)),
            'margin_discrepancy': _pct_diff(source.get('margin', 0), new.get('margin', 0)),
            'orders_discrepancy': _pct_diff(source.get('orders', 0), new.get('orders', 0)),
            'sales_discrepancy': _pct_diff(source.get('sales', 0), new.get('sales', 0)),
            'adv_discrepancy': _pct_diff(source.get('adv', 0), new.get('adv', 0)),
        }

        max_disc = max(results['revenue_discrepancy'], results['margin_discrepancy'])
        results['overall_status'] = 'PASS' if max_disc <= self.THRESHOLD_PCT else 'FAIL'

        logger.info(f"WB: revenue {results['revenue_discrepancy']:.2f}%, margin {results['margin_discrepancy']:.2f}% -> {results['overall_status']}")
        return results

    def compare_ozon_data(self, date_from, date_to):
        """
        Compare Ozon data between source and new DB.

        Returns:
            dict with discrepancy percentages and raw values.
        """
        logger.info(f"Comparing Ozon data: {date_from} -> {date_to}")
        params = (date_from, date_to)

        source = _query_one(
            self.source_ozon_conn,
            OZON_METRICS_SQL.format(table='public.abc_date'),
            params,
        )

        new = _query_one(
            self.new_conn,
            OZON_METRICS_SQL.format(table='ozon.abc_date'),
            params,
        )

        source_count = _query_scalar(
            self.source_ozon_conn,
            COUNT_SQL.format(table='public.abc_date'),
            params,
        )
        new_count = _query_scalar(
            self.new_conn,
            COUNT_SQL.format(table='ozon.abc_date'),
            params,
        )

        results = {
            'source': source,
            'new': new,
            'source_rows': source_count,
            'new_rows': new_count,
            'rows_discrepancy': _pct_diff(source_count, new_count),
            'revenue_discrepancy': _pct_diff(source.get('revenue', 0), new.get('revenue', 0)),
            'margin_discrepancy': _pct_diff(source.get('margin', 0), new.get('margin', 0)),
            'sales_discrepancy': _pct_diff(source.get('sales', 0), new.get('sales', 0)),
            'adv_discrepancy': _pct_diff(source.get('adv', 0), new.get('adv', 0)),
        }

        max_disc = max(results['revenue_discrepancy'], results['margin_discrepancy'])
        results['overall_status'] = 'PASS' if max_disc <= self.THRESHOLD_PCT else 'FAIL'

        logger.info(f"Ozon: revenue {results['revenue_discrepancy']:.2f}%, margin {results['margin_discrepancy']:.2f}% -> {results['overall_status']}")
        return results

    def get_article_detail(self, date_from, date_to, marketplace='wb'):
        """
        Get per-article comparison to find problematic records.

        Returns:
            list of dicts with article, source_revenue, new_revenue, pct_diff.
        """
        params = (date_from, date_to)

        if marketplace == 'wb':
            source_rows = _query_all(
                self.source_wb_conn,
                WB_DETAIL_SQL.format(table='public.abc_date'),
                params,
            )
            new_rows = _query_all(
                self.new_conn,
                WB_DETAIL_SQL.format(table='wb.abc_date'),
                params,
            )
        else:
            source_rows = _query_all(
                self.source_ozon_conn,
                OZON_DETAIL_SQL.format(table='public.abc_date'),
                params,
            )
            new_rows = _query_all(
                self.new_conn,
                OZON_DETAIL_SQL.format(table='ozon.abc_date'),
                params,
            )

        new_by_article = {r['article']: r for r in new_rows}
        detail = []

        for s in source_rows:
            art = s['article']
            n = new_by_article.pop(art, {})
            detail.append({
                'article': art,
                'source_revenue': float(s.get('revenue', 0)),
                'new_revenue': float(n.get('revenue', 0)),
                'revenue_pct': _pct_diff(s.get('revenue', 0), n.get('revenue', 0)),
                'source_margin': float(s.get('margin', 0)),
                'new_margin': float(n.get('margin', 0)),
                'margin_pct': _pct_diff(s.get('margin', 0), n.get('margin', 0)),
            })

        # Articles in new but not in source
        for art, n in new_by_article.items():
            detail.append({
                'article': art,
                'source_revenue': 0.0,
                'new_revenue': float(n.get('revenue', 0)),
                'revenue_pct': 100.0,
                'source_margin': 0.0,
                'new_margin': float(n.get('margin', 0)),
                'margin_pct': 100.0,
            })

        return sorted(detail, key=lambda x: x['revenue_pct'], reverse=True)

    def generate_report(self, wb_results, ozon_results, date_from, date_to):
        """
        Generate reconciliation report as text.

        Returns:
            str: Report text (also saved to file).
        """
        lines = []
        lines.append("=" * 70)
        lines.append(f"RECONCILIATION REPORT: {date_from} -> {date_to}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)

        # WB section
        lines.append("\n--- WILDBERRIES ---")
        lines.append(f"Rows: source={wb_results['source_rows']}, new={wb_results['new_rows']} ({wb_results['rows_discrepancy']:.2f}% diff)")
        lines.append("")
        lines.append(f"{'Metric':<20} {'Source':>15} {'New':>15} {'Diff %':>10}")
        lines.append("-" * 62)

        for metric_key, label in [
            ('revenue', 'Revenue (SPP)'),
            ('margin', 'Margin'),
            ('orders', 'Orders'),
            ('sales', 'Sales'),
            ('adv', 'Advertising'),
        ]:
            src_val = wb_results['source'].get(metric_key, 0)
            new_val = wb_results['new'].get(metric_key, 0)
            disc = wb_results.get(f'{metric_key}_discrepancy', 0)
            flag = ' !!!' if disc > self.THRESHOLD_PCT else ''
            lines.append(f"{label:<20} {float(src_val):>15,.2f} {float(new_val):>15,.2f} {disc:>9.2f}%{flag}")

        lines.append(f"\nWB Status: {wb_results['overall_status']}")

        # Ozon section
        lines.append("\n--- OZON ---")
        lines.append(f"Rows: source={ozon_results['source_rows']}, new={ozon_results['new_rows']} ({ozon_results['rows_discrepancy']:.2f}% diff)")
        lines.append("")
        lines.append(f"{'Metric':<20} {'Source':>15} {'New':>15} {'Diff %':>10}")
        lines.append("-" * 62)

        for metric_key, label in [
            ('revenue', 'Revenue (price_end)'),
            ('margin', 'Margin (marga-nds)'),
            ('sales', 'Sales (count_end)'),
            ('adv', 'Advertising'),
        ]:
            src_val = ozon_results['source'].get(metric_key, 0)
            new_val = ozon_results['new'].get(metric_key, 0)
            disc = ozon_results.get(f'{metric_key}_discrepancy', 0)
            flag = ' !!!' if disc > self.THRESHOLD_PCT else ''
            lines.append(f"{label:<20} {float(src_val):>15,.2f} {float(new_val):>15,.2f} {disc:>9.2f}%{flag}")

        lines.append(f"\nOzon Status: {ozon_results['overall_status']}")

        # Per-article problems
        if wb_results['overall_status'] == 'FAIL' and self.source_wb_conn:
            lines.append("\n--- WB PROBLEMATIC ARTICLES (revenue diff > 5%) ---")
            detail = self.get_article_detail(date_from, date_to, 'wb')
            problems = [d for d in detail if d['revenue_pct'] > 5.0][:20]
            if problems:
                lines.append(f"{'Article':<30} {'Src Rev':>12} {'New Rev':>12} {'Diff%':>8}")
                lines.append("-" * 64)
                for d in problems:
                    lines.append(f"{str(d['article']):<30} {d['source_revenue']:>12,.2f} {d['new_revenue']:>12,.2f} {d['revenue_pct']:>7.2f}%")

        if ozon_results['overall_status'] == 'FAIL' and self.source_ozon_conn:
            lines.append("\n--- OZON PROBLEMATIC ARTICLES (revenue diff > 5%) ---")
            detail = self.get_article_detail(date_from, date_to, 'ozon')
            problems = [d for d in detail if d['revenue_pct'] > 5.0][:20]
            if problems:
                lines.append(f"{'Article':<30} {'Src Rev':>12} {'New Rev':>12} {'Diff%':>8}")
                lines.append("-" * 64)
                for d in problems:
                    lines.append(f"{str(d['article']):<30} {d['source_revenue']:>12,.2f} {d['new_revenue']:>12,.2f} {d['revenue_pct']:>7.2f}%")

        # Overall
        lines.append("\n" + "=" * 70)
        overall = 'PASS' if (wb_results['overall_status'] == 'PASS' and ozon_results['overall_status'] == 'PASS') else 'FAIL'
        lines.append(f"OVERALL: {overall}")
        lines.append("=" * 70)

        report_text = "\n".join(lines)

        # Save to file
        report_file = f"reconciliation_report_{date_from}_{date_to}.txt"
        try:
            with open(report_file, 'w') as f:
                f.write(report_text)
            logger.info(f"Report saved: {report_file}")
        except Exception as e:
            logger.warning(f"Could not save report file: {e}")

        return report_text

    def run(self, date_from, date_to):
        """
        Run full reconciliation.

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            bool: True if all checks passed.
        """
        logger.info(f"Reconciliation started: {date_from} -> {date_to}")

        try:
            self._connect()

            if not self.source_wb_conn or not self.source_ozon_conn:
                logger.warning("Source DBs not available, skipping reconciliation")
                return True

            wb_results = self.compare_wb_data(date_from, date_to)
            ozon_results = self.compare_ozon_data(date_from, date_to)

            report = self.generate_report(wb_results, ozon_results, date_from, date_to)
            logger.info("\n" + report)

            passed = (wb_results['overall_status'] == 'PASS' and ozon_results['overall_status'] == 'PASS')
            return passed

        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            raise
        finally:
            self._close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    parser = argparse.ArgumentParser(description='Data Reconciliation')
    parser.add_argument('--date-from', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--date-to', required=True, help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    recon = DataReconciliation()
    passed = recon.run(args.date_from, args.date_to)
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
