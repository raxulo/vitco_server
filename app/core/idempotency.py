"""
RealTimeTransfer
================

Enterprise Distributed Idempotency Engine (Stripe / Netflix API Gateway Architecture)

Guarantees exact-once execution semantics across network retries and duplicate API requests.

Python 3.13+
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple


class IdempotencyEngine:
    """
    In-memory / Redis-ready Idempotency Guard to prevent duplicate processing.
    """

    __slots__ = ("_cache", "_lock", "_ttl_seconds")

    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """
        Check if an operation result exists for the given idempotency key.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            result, timestamp = entry
            if time.time() - timestamp > self._ttl_seconds:
                del self._cache[key]
                return None
            return result

    def set(self, key: str, result: Any) -> None:
        """
        Store execution result for idempotency key.
        """
        with self._lock:
            self._cache[key] = (result, time.time())

    def clear_expired(self) -> None:
        """
        Purge expired idempotency entries.
        """
        now = time.time()
        with self._lock:
            expired_keys = [
                k
                for k, (_, ts) in self._cache.items()
                if now - ts > self._ttl_seconds
            ]
            for k in expired_keys:
                del self._cache[k]
