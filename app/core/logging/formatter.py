"""
RealTimeTransfer
================

Enterprise Logger Formatter

Python 3.13+
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from app.core.clock import now_ist

from app.core.logging.context import LoggerContext


# ==========================================================
# Base Formatter
# ==========================================================

class BaseFormatter(logging.Formatter):
    """
    Common formatter utilities.
    """

    __slots__ = ()

    @staticmethod
    def timestamp() -> str:
        return now_ist().isoformat(timespec="milliseconds")


# ==========================================================
# Console Formatter
# ==========================================================

class ConsoleFormatter(BaseFormatter):
    """
    Human readable formatter.
    """

    __slots__ = ()

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        ctx = LoggerContext.get()

        return (
            f"{self.timestamp()} | "
            f"{record.levelname:<8} | "
            f"{ctx.request_id} | "
            f"{record.name} | "
            f"{record.getMessage()}"
        )


# ==========================================================
# JSON Formatter
# ==========================================================

class JsonFormatter(BaseFormatter):
    """
    Structured JSON formatter.
    """

    __slots__ = ()

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        ctx = LoggerContext.get()

        payload = {

            "timestamp": self.timestamp(),

            "level": record.levelname,

            "logger": record.name,

            "message": record.getMessage(),

            "request_id": ctx.request_id,

            # "trace_id": ctx.trace_id,

            "user_id": ctx.user_id,

            "ip": ctx.ip,

        }

        if record.exc_info:

            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )