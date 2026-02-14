"""
Backward-compatible re-export.

Actual configuration lives in shared/config.py.
Scripts can still do: from scripts.config import DB_CONFIG, ...
"""
from shared.config import *  # noqa: F401,F403
