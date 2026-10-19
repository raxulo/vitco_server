"""
RealTimeTransfer
================

Enterprise Caching Decorator

Python 3.13+
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable
from typing import Any


def cached(
    ttl_seconds: float | None = None,
    key_prefix: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to cache the results of an asynchronous function.
    Automatically detects and excludes transient 'self' or 'cls' arguments
    to prevent memory-address-dependent keys under heavy load.
    """
    from app.core.cache import cache

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip self/cls in method arguments to ensure stable keys across instances
            key_args = args
            if args:
                first = args[0]
                if hasattr(first, "__class__") and not isinstance(first, (int, float, str, bytes, bool, type(None))):
                    key_args = args[1:]

            arg_str = ":".join(str(a) for a in key_args)
            kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            raw_key = f"{func.__module__}:{func.__name__}:{arg_str}:{kwarg_str}"
            
            # Hash to limit key size and keep structure clean
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            prefix = key_prefix or "cache"
            cache_key = f"{prefix}:{func.__name__}:{key_hash}"

            # Fetch from cache
            value = await cache.get(cache_key)
            if value is not None:
                return value

            # Compute and store
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl_seconds)
            return result

        return wrapper

    return decorator
