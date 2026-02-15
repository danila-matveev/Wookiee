"""
Backward-compatible re-export.

Actual implementation lives in shared/data_layer.py.
Standalone scripts (ozon_*.py, etc.) can still do:
    from scripts.data_layer import get_wb_finance, ...
"""
from shared.data_layer import *  # noqa: F401,F403
