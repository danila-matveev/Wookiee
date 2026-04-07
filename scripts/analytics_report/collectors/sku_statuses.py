"""SKU statuses collector: model and article status mappings."""
from __future__ import annotations

from shared.data_layer.sku_mapping import (
    get_model_statuses_mapped,
    get_artikuly_statuses,
)


def collect_sku_statuses() -> dict:
    """Collect SKU status data.

    Returns:
        {"sku_statuses": {...}} with model and article statuses.
    """
    return {
        "sku_statuses": {
            "model_statuses": get_model_statuses_mapped(),
            "article_statuses": get_artikuly_statuses(),
        }
    }
