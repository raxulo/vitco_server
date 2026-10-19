"""
RealTimeTransfer Core Infrastructure
===================================

Google, Microsoft, Uber, Netflix scale architecture primitives.

Python 3.13+
"""

from __future__ import annotations

from app.core.logging.logger import get_logger
from app.core.logging.manager import LoggerManager

__all__ = (
    "get_logger",
    "LoggerManager"
)

