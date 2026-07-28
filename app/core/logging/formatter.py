"""
RealTimeTransfer
================

Enterprise JSON Formatter

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import json
import logging
import socket
from datetime import UTC, datetime
from typing import Any


_STANDARD_FIELDS = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
)


class JsonFormatter(logging.Formatter):
    """
    Enterprise JSON formatter.
    """

    __slots__ = (
        "_application",
        "_hostname",
    )

    def __init__(
        self,
        application: str,
    ) -> None:

        super().__init__()

        self._application = application

        self._hostname = socket.gethostname()

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        payload: dict[str, Any] = {

            "timestamp": datetime.now(
                UTC
            ).isoformat(),

            "application": self._application,

            "hostname": self._hostname,

            "level": record.levelname,

            "logger": record.name,

            "module": record.module,

            "function": record.funcName,

            "line": record.lineno,

            "process": record.process,

            "thread": record.threadName,

            "message": record.getMessage(),
        }

        #
        # Extra fields
        #

        for key, value in record.__dict__.items():

            if key in _STANDARD_FIELDS:
                continue

            payload[key] = value

        #
        # Exception
        #

        if record.exc_info:

            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(

            payload,

            ensure_ascii=False,

            separators=(",", ":"),

            default=str,
        )