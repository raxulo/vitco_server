
"""
RealTimeTransfer
================

Enterprise Logger Filters

Python 3.13+
"""

from __future__ import annotations

import logging
from app.core.logging.context import LoggerContext

class ContextFilter(logging.Filter):
    """
    Inject request context into LogRecord.

    Extremely lightweight.
    """

    __slots__ = ()

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:

        ctx = LoggerContext.get()

        record.request_id = ctx.request_id
        # record.trace_id = ctx.trace_id
        record.user_id = ctx.user_id
        record.ip = ctx.ip

        return True


class ErrorOnlyFilter(logging.Filter):
    """
    Allow only ERROR and above.
    """

    __slots__ = ()

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:

        return record.levelno >= logging.ERROR