"""Tests for services/wb_localization/calculators/il_irp_analyzer.py"""
from __future__ import annotations

import pytest

from services.wb_localization.calculators.il_irp_analyzer import (
    CIS_REGIONS,
    analyze_il_irp,
    classify_status,
)


# ============================================================================
# Fixture helpers
# ============================================================================

def _order(
    article: str,
    warehouse: str,
    oblast: str,
    is_cancel: bool = False,
) -> dict:
    return {
        'supplierArticle': article,
        'warehouseName': warehouse,
        'oblastOkrugName': oblast,
        'isCancel': is_cancel,
    }


# Orders for the main test corpus
#   Коледино → Центральный ФО (warehouse)
#   Москва → Центральный ФО (delivery)   → LOCAL
#   Казань (oblast) → Приволжский ФО      → NON-LOCAL with Коледино
#   Новосибирская область → Дальневосточный+Сибирский → NON-LOCAL with Коледино
#   Минск warehouse → Беларусь (CIS)

ORDERS_VUKI_80_LOCAL = [
    # 8 local (Коледино → Москва)
    *[_order('Vuki/black', 'Коледино', 'Москва') for _ in range(8)],
    # 2 non-local (Коледино → Казань oblast = Приволжский)
    *[_order('Vuki/black', 'Коледино', 'Татарстан') for _ in range(2)],
]

ORDERS_RUBY_0_LOCAL = [
    # 10 non-local (Коледино → Новосибирская область = Дальневосточный+Сибирский)
    *[_order('Ruby/red', 'Коледино', 'Новосибирская область') for _ in range(10)],
]

ALL_ORDERS = ORDERS_VUKI_80_LOCAL + ORDERS_RUBY_0_LOCAL

PRICES = {
    'vuki/black': 1000.0,
    'ruby/red': 500.0,
}


# ============================================================================
# classify_status
# ============================================================================

class TestClassifyStatus:
    def test_otlichnaya(self):
        assert classify_status(0.50) == 'Отличная'
        assert classify_status(0.90) == 'Отличная'

    def test_nejtralnaya(self):
        assert classify_status(1.00) == 'Нейтральная'
        assert classify_status(1.05) == 'Нейтральная'

    def test_slabaya(self):
        assert classify_status(1.10) == 'Слабая'
        assert classify_status(1.30) == 'Слабая'

    def test_kriticheskaya(self):
        assert classify_status(1.40) == 'Критическая'
        assert classify_status(2.20) == 'Критическая'


# ============================================================================
# Overall metrics
# ============================================================================

class TestOverallMetrics:
    def setup_method(self):
        self.result = analyze_il_irp(ALL_ORDERS, PRICES, period_days=30)
        self.summary = self.result['summary']

    def test_total_rf_orders(self):
        assert self.summary['total_rf_orders'] == 20

    def test_total_cis_orders(self):
        assert self.summary['total_cis_orders'] == 0

    def test_overall_il_approx(self):
        # vuki: 10 orders, loc=80% → кТР=0.80; ruby: 10 orders, loc=0% → КТР=2.20
        # weighted IL = (10*0.80 + 10*2.20) / 20 = (8 + 22) / 20 = 1.50
        assert abs(self.summary['overall_il'] - 1.50) < 0.01

    def test_total_articles(self):
        assert self.summary['total_articles'] == 2

    def test_local_nonlocal_counts(self):
        assert self.summary['local_orders'] == 8
        assert self.summary['nonlocal_orders'] == 12

    def test_loc_pct(self):
        assert self.summary['loc_pct'] == pytest.approx(40.0, abs=0.2)


# ============================================================================
# Per-article details
# ============================================================================

class TestArticleDetails:
    def setup_method(self):
        result = analyze_il_irp(ALL_ORDERS, PRICES, period_days=30)
        self.articles = {a['article']: a for a in result['articles']}

    def test_vuki_loc_pct(self):
        a = self.articles['vuki/black']
        assert a['loc_pct'] == 80.0
        assert a['wb_local'] == 8
        assert a['wb_nonlocal'] == 2

    def test_vuki_ktr_krp(self):
        a = self.articles['vuki/black']
        assert a['ktr'] == 0.80
        assert a['krp_pct'] == 0.00

    def test_vuki_status(self):
        assert self.articles['vuki/black']['status'] == 'Отличная'

    def test_ruby_loc_pct(self):
        a = self.articles['ruby/red']
        assert a['loc_pct'] == 0.0
        assert a['wb_local'] == 0
        assert a['wb_nonlocal'] == 10

    def test_ruby_ktr_krp(self):
        a = self.articles['ruby/red']
        assert a['ktr'] == 2.20
        assert a['krp_pct'] == 2.50

    def test_ruby_status(self):
        assert self.articles['ruby/red']['status'] == 'Критическая'

    def test_irp_per_order_ruby(self):
        a = self.articles['ruby/red']
        # price=500, krp=2.50% → 500*2.50/100 = 12.50
        assert a['irp_per_order'] == pytest.approx(12.50, abs=0.01)

    def test_irp_per_order_vuki(self):
        # vuki krp=0 → no IRP charge
        assert self.articles['vuki/black']['irp_per_order'] == 0.0

    def test_regional_breakdown_present(self):
        a = self.articles['vuki/black']
        assert 'Центральный' in a['regions']
        assert 'Приволжский' in a['regions']
        # Центральный: 8 local, 0 non-local
        r = a['regions']['Центральный']
        assert r['local'] == 8
        assert r['nonlocal'] == 0

    def test_weakest_region_vuki(self):
        # vuki has 2 non-local in Приволжский (0% local) and 8 local in Центральный
        a = self.articles['vuki/black']
        assert a['weakest_region'] == 'Приволжский'

    def test_weakest_region_ruby(self):
        a = self.articles['ruby/red']
        assert a['weakest_region'] == 'Дальневосточный + Сибирский'


# ============================================================================
# Sorting by contribution desc
# ============================================================================

class TestSortedByContributionDesc:
    def test_worst_first(self):
        result = analyze_il_irp(ALL_ORDERS, PRICES, period_days=30)
        articles = result['articles']
        assert len(articles) == 2
        # ruby contribution = (2.20-1)*10 = 12.0; vuki = (0.80-1)*10 = -2.0
        assert articles[0]['article'] == 'ruby/red'
        assert articles[0]['contribution'] == pytest.approx(12.0, abs=0.1)
        assert articles[1]['article'] == 'vuki/black'
        assert articles[1]['contribution'] == pytest.approx(-2.0, abs=0.1)


# ============================================================================
# Top problems — only contribution > 0
# ============================================================================

class TestTopProblems:
    def test_only_positive_contribution(self):
        result = analyze_il_irp(ALL_ORDERS, PRICES, period_days=30)
        top = result['top_problems']
        # Only ruby has contribution > 0
        assert len(top) == 1
        assert top[0]['article'] == 'ruby/red'
        assert top[0]['rank'] == 1

    def test_max_10_items(self):
        # Create 12 articles each with 0% localization
        orders = [
            _order(f'art{i:02d}', 'Коледино', 'Новосибирская область')
            for i in range(12)
            for _ in range(5)
        ]
        prices = {f'art{i:02d}': 1000.0 for i in range(12)}
        result = analyze_il_irp(orders, prices, period_days=30)
        assert len(result['top_problems']) == 10


# ============================================================================
# CIS orders
# ============================================================================

class TestCisOrders:
    def test_cis_warehouse_excluded_from_il(self):
        """Orders shipped from CIS warehouse must not affect ИЛ."""
        orders = [
            # CIS warehouse → should be counted as CIS, not RF
            *[_order('test/cis', 'Минск', 'Москва') for _ in range(5)],
            # Normal RF order
            *[_order('test/rf', 'Коледино', 'Москва') for _ in range(10)],
        ]
        prices = {'test/rf': 1000.0, 'test/cis': 1000.0}
        result = analyze_il_irp(orders, prices, period_days=30)

        summary = result['summary']
        assert summary['total_cis_orders'] == 5
        assert summary['total_rf_orders'] == 10
        # ИЛ computed only from RF orders → all 10 are local → КТР=0.50
        assert summary['overall_il'] == pytest.approx(0.50, abs=0.01)

    def test_cis_orders_in_irp_denominator(self):
        """CIS orders included in ИРП denominator, reducing its value."""
        # rf article with 0% local → krp=2.50%, 10 orders
        # plus 10 CIS orders
        # ИРП = (10 * 2.50) / (10 + 10) = 25 / 20 = 1.25
        orders = [
            *[_order('bad/art', 'Коледино', 'Новосибирская область') for _ in range(10)],
            *[_order('cis/art', 'Минск', 'Москва') for _ in range(10)],
        ]
        prices = {'bad/art': 1000.0, 'cis/art': 1000.0}
        result = analyze_il_irp(orders, prices, period_days=30)
        summary = result['summary']
        # CIS counted
        assert summary['total_cis_orders'] == 10
        # IRP denom = 10+10=20; numerator = 10*2.50 = 25 → 1.25%
        assert summary['overall_irp_pct'] == pytest.approx(1.25, abs=0.01)

    def test_cancelled_orders_skipped(self):
        orders = [
            _order('art/a', 'Коледино', 'Москва', is_cancel=True),
            _order('art/a', 'Коледино', 'Москва', is_cancel=False),
        ]
        result = analyze_il_irp(orders, {'art/a': 1000.0}, period_days=30)
        summary = result['summary']
        assert summary['total_rf_orders'] == 1

    def test_cis_delivery_excluded(self):
        """Orders delivered to CIS address should be counted as CIS."""
        # Нет oblast для СНГ в OBLAST_TO_FD, но если warehouse is Russian
        # and delivery oblast maps to CIS — count as CIS.
        # Using 'Беларусь' as delivery region directly (not standard oblast field)
        # Since OBLAST_TO_FD does not contain CIS names, test using warehouse CIS path.
        orders = [
            *[_order('x/art', 'Минск', 'Москва') for _ in range(3)],
        ]
        result = analyze_il_irp(orders, {'x/art': 500.0}, period_days=30)
        assert result['summary']['total_cis_orders'] == 3
        assert result['summary']['total_rf_orders'] == 0
