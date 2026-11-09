"""
In-memory sliding-window rate limiter.

The server runs one process (CON-08), so memory is shared by every request. Several
processes would each count on their own and a limit would multiply by their number.

Python 3.13+
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from collections.abc import Callable


class SlidingWindowLimiter:
    """Memory is bounded: past `max_keys`, the key used longest ago is forgotten."""

    __slots__ = ("_hits", "_max_keys", "_clock")

    def __init__(self, max_keys: int = 10_000, clock: Callable[[], float] = time.monotonic) -> None:
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._max_keys = max_keys
        self._clock = clock

    def __len__(self) -> int:
        return len(self._hits)

    def hit(self, key: str, limit: int, window_seconds: int) -> int:
        """Counts one attempt. Returns 0 when allowed, else the seconds to wait."""
        now = self._clock()
        hits = self._hits.get(key)
        if hits is None:
            hits = deque()
            self._hits[key] = hits
        self._hits.move_to_end(key)

        while hits and hits[0] <= now - window_seconds:
            hits.popleft()

        if len(hits) >= limit:
            return max(int(hits[0] + window_seconds - now) + 1, 1)

        hits.append(now)
        while len(self._hits) > self._max_keys:
            self._hits.popitem(last=False)
        return 0
