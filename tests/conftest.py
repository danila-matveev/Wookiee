"""
Shared fixtures for price analysis tests.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_daily_data():
    """30 days of synthetic daily price-margin data (inelastic model)."""
    import numpy as np
    np.random.seed(42)
    base_date = datetime(2026, 1, 1)
    data = []
    for i in range(30):
        price = 2500 + np.random.normal(0, 50)
        sales = max(1, int(50 - 0.005 * (price - 2500) + np.random.normal(0, 3)))
        margin_per_unit = price * 0.22
        margin = margin_per_unit * sales
        revenue = price * sales
        data.append({
            'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'model': 'wendy',
            'price_per_unit': round(price, 2),
            'sales_count': sales,
            'margin': round(margin, 2),
            'margin_pct': round(margin_per_unit / price * 100, 2),
            'revenue': round(revenue, 2),
            'revenue_before_spp': round(revenue, 2),
            'spp_pct': round(15 + np.random.normal(0, 1), 2),
            'drr_pct': round(8 + np.random.normal(0, 0.5), 2),
            'logistics_per_unit': round(150 + np.random.normal(0, 10), 2),
            'cogs_per_unit': round(800 + np.random.normal(0, 20), 2),
            'adv': round(10000 + np.random.normal(0, 500), 2),
            'adv_total': round(10000 + np.random.normal(0, 500), 2),
        })
    return data


@pytest.fixture
def elastic_demand_data():
    """30 days of data with elastic demand (|beta| > 1.5)."""
    import numpy as np
    np.random.seed(123)
    base_date = datetime(2026, 1, 1)
    data = []
    for i in range(30):
        # Price varies significantly
        price = 2000 + i * 30 + np.random.normal(0, 20)
        # Sales drop sharply with price increases (elastic)
        sales = max(1, int(100 - 0.07 * (price - 2000) + np.random.normal(0, 2)))
        margin = price * 0.20 * sales
        revenue = price * sales
        data.append({
            'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'model': 'ruby',
            'price_per_unit': round(price, 2),
            'sales_count': sales,
            'margin': round(margin, 2),
            'margin_pct': 20.0,
            'revenue': round(revenue, 2),
            'revenue_before_spp': round(revenue, 2),
            'spp_pct': 15.0,
            'drr_pct': 8.0,
            'logistics_per_unit': 150.0,
            'cogs_per_unit': 800.0,
            'adv': 10000.0,
            'adv_total': 10000.0,
        })
    return data


@pytest.fixture
def rising_price_data():
    """30 days of monotonically rising prices."""
    base_date = datetime(2026, 1, 1)
    data = []
    for i in range(30):
        price = 2000 + i * 20
        data.append({
            'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'model': 'test',
            'price_per_unit': float(price),
            'sales_count': 50,
            'margin': float(price * 0.2 * 50),
            'margin_pct': 20.0,
            'revenue': float(price * 50),
            'revenue_before_spp': float(price * 50),
            'spp_pct': 15.0,
            'drr_pct': 8.0,
            'logistics_per_unit': 150.0,
            'cogs_per_unit': 800.0,
        })
    return data


@pytest.fixture
def falling_price_data():
    """30 days of monotonically falling prices."""
    base_date = datetime(2026, 1, 1)
    data = []
    for i in range(30):
        price = 3000 - i * 20
        data.append({
            'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'model': 'test',
            'price_per_unit': float(price),
            'sales_count': 50,
            'margin': float(price * 0.2 * 50),
            'margin_pct': 20.0,
            'revenue': float(price * 50),
            'revenue_before_spp': float(price * 50),
        })
    return data


@pytest.fixture
def stable_price_data():
    """30 days of stable prices with noise."""
    import numpy as np
    np.random.seed(99)
    base_date = datetime(2026, 1, 1)
    data = []
    for i in range(30):
        price = 2500 + np.random.normal(0, 5)  # very small noise
        data.append({
            'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'model': 'test',
            'price_per_unit': round(price, 2),
            'sales_count': 50,
            'margin': round(price * 0.2 * 50, 2),
            'margin_pct': 20.0,
            'revenue': round(price * 50, 2),
            'revenue_before_spp': round(price * 50, 2),
        })
    return data


@pytest.fixture
def low_margin_data():
    """Data where margin is below 20% threshold."""
    base_date = datetime(2026, 1, 1)
    data = []
    for i in range(30):
        price = 2500 + i * 10
        sales = max(1, 50 - i)
        margin_pct = 15.0  # below MIN_MARGIN_PCT
        margin = price * (margin_pct / 100) * sales
        data.append({
            'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'model': 'test',
            'price_per_unit': float(price),
            'sales_count': sales,
            'margin': round(margin, 2),
            'margin_pct': margin_pct,
            'revenue': float(price * sales),
            'revenue_before_spp': float(price * sales),
            'spp_pct': 15.0,
            'drr_pct': 8.0,
            'logistics_per_unit': 150.0,
            'cogs_per_unit': 800.0,
        })
    return data
