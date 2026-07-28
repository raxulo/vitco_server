"""
RealTimeTransfer
================

Enterprise Logging Filters

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import logging
from typing import Final


class SensitiveDataFilter(logging.Filter):
    """
    Removes sensitive values from LogRecord.
    """

    __slots__ = ()

    _REDACT_FIELDS: Final[frozenset[str]] = frozenset({

        "password",

        "passwd",

        "secret",

        "token",

        "jwt",

        "refresh_token",

        "access_token",

        "authorization",

        "cookie",

        "session",

        "session_id",

        "api_key",

        "private_key",

        "credit_card",

        "cvv",
    })

    REDACTED: Final[str] = "********"

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:

        for field in self._REDACT_FIELDS:

            if hasattr(record, field):

                setattr(

                    record,

                    field,

                    self.REDACTED,
                )

        return True


class HealthCheckFilter(logging.Filter):
    """
    Ignore noisy health requests.
    """

    __slots__ = ()

    _IGNORE: Final[frozenset[str]] = frozenset({

        "/health",

        "/healthz",

        "/live",

        "/ready",

        "/metrics",

        "/favicon.ico",
    })

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:

        path = getattr(

            record,

            "path",

            None,
        )

        if path in self._IGNORE:

            return False

        return True


class StaticFileFilter(logging.Filter):
    """
    Ignore static assets.
    """

    __slots__ = ()

    _EXTENSIONS: Final[tuple[str, ...]] = (

        ".css",

        ".js",

        ".png",

        ".jpg",

        ".jpeg",

        ".gif",

        ".svg",

        ".ico",

        ".woff",

        ".woff2",

        ".ttf",
    )

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:

        path = getattr(

            record,

            "path",

            None,
        )

        if not path:

            return True

        return not path.endswith(

            self._EXTENSIONS
        )


class MinimumLevelFilter(logging.Filter):
    """
    Per-handler minimum level filter.
    """

    __slots__ = (
        "_level",
    )

    def __init__(
        self,
        level: int,
    ) -> None:

        super().__init__()

        self._level = level

    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:

        return record.levelno >= self._level