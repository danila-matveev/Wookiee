"""Simple TTL cache for DB query results.

Data is refreshed daily via ETL, so a 5-minute cache is safe and
dramatically reduces DB load under concurrent dashboard users.
"""
from __future__ import annotations

from functools import wraps

from cachetools import TTLCache

_cache: TTLCache = TTLCache(maxsize=256, ttl=300)  # 5 min


def cached(func):
    """Cache function results for 5 minutes, keyed by all positional & keyword args."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = (func.__name__,) + args + tuple(sorted(kwargs.items()))
        if key in _cache:
            return _cache[key]
        result = func(*args, **kwargs)
        _cache[key] = result
        return result

    return wrapper
