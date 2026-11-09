"""
Limits on what anyone can do without logging in.

Limits are per client IP and generous, because a whole village may share one mobile IP.

Python 3.13+
"""

from __future__ import annotations

from app.core.rate_limit import SlidingWindowLimiter
from app.modules.marketplace.domain.exceptions import TooManyRequestsException

_WINDOW_SECONDS = 600
ACTION_LIMITS = {
    "enquiry": 10,
    "checkout": 20,
    "track": 20,
}


class StoreRateLimiter:

    __slots__ = ("_limiter", "_enabled")

    def __init__(self, limiter: SlidingWindowLimiter, enabled: bool = True) -> None:
        self._limiter = limiter
        self._enabled = enabled

    def ensure_allowed(self, action: str, client: str | None) -> None:
        if not self._enabled:
            return
        retry_after = self._limiter.hit(f"{action}:{client or 'unknown'}", ACTION_LIMITS[action], _WINDOW_SECONDS)
        if retry_after:
            raise TooManyRequestsException(retry_after)
