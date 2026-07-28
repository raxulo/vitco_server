"""
RealTimeTransfer
================

Enterprise Logger Factory

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import logging
import threading

from app.core.logging.logger import EnterpriseLogger


class LoggerFactory:
    """
    Creates EnterpriseLogger instances.

    Thread-safe.

    Singleton.

    One logger per name.
    """

    __slots__ = ()

    _cache: dict[
        str,
        EnterpriseLogger,
    ] = {}

    _lock = threading.RLock()

    @classmethod
    def get(
        cls,
        name: str,
    ) -> EnterpriseLogger:

        logger = cls._cache.get(name)

        if logger is not None:
            return logger

        with cls._lock:

            logger = cls._cache.get(name)

            if logger is not None:
                return logger

            raw_logger = logging.getLogger(name)

            enterprise_logger = EnterpriseLogger(
                raw_logger
            )

            cls._cache[name] = enterprise_logger

            return enterprise_logger

    @classmethod
    def clear(cls) -> None:

        with cls._lock:

            cls._cache.clear()

    @classmethod
    def registered(cls) -> tuple[str, ...]:

        return tuple(
            cls._cache.keys()
        )