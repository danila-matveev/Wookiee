"""
Shared data layer — SQL queries for WB/OZON/Supabase databases.

Refactored from a single 4400-line file into domain modules.
This __init__.py re-exports everything for full backward compatibility:

    from shared.data_layer import get_wb_finance  # still works
    from shared.data_layer.finance import get_wb_finance  # also works
"""

from shared.data_layer._connection import *       # noqa: F401,F403
from shared.data_layer._sql_fragments import *    # noqa: F401,F403
from shared.data_layer.finance import *            # noqa: F401,F403
from shared.data_layer.traffic import *            # noqa: F401,F403
from shared.data_layer.sku_mapping import *        # noqa: F401,F403
from shared.data_layer.article import *            # noqa: F401,F403
from shared.data_layer.time_series import *        # noqa: F401,F403
from shared.data_layer.pricing import *            # noqa: F401,F403
from shared.data_layer.pricing_article import *    # noqa: F401,F403
from shared.data_layer.inventory import *          # noqa: F401,F403
from shared.data_layer.advertising import *        # noqa: F401,F403
from shared.data_layer.funnel_seo import *         # noqa: F401,F403
from shared.data_layer.planning import *           # noqa: F401,F403
from shared.data_layer.logistics import *          # noqa: F401,F403
