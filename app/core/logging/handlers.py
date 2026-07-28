"""
RealTimeTransfer
================

Enterprise Logging Handlers

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.core.logging.formatter import JsonFormatter


class LoggingHandlers:
    """
    Creates logging handlers.

    Stateless factory.
    """

    __slots__ = ()

    @staticmethod
    def console(
        application: str,
        level: int = logging.INFO,
    ) -> logging.Handler:

        handler = logging.StreamHandler()

        handler.setLevel(level)

        handler.setFormatter(

            JsonFormatter(application)

        )

        return handler

    @staticmethod
    def rotating_file(
        application: str,
        file: str | Path,
        *,
        level: int = logging.INFO,
        max_bytes: int = 100 * 1024 * 1024,
        backups: int = 10,
    ) -> logging.Handler:

        path = Path(file)

        path.parent.mkdir(

            parents=True,

            exist_ok=True,
        )

        handler = RotatingFileHandler(

            filename=path,

            maxBytes=max_bytes,

            backupCount=backups,

            encoding="utf-8",

            delay=True,
        )

        handler.setLevel(level)

        handler.setFormatter(

            JsonFormatter(application)

        )

        return handler

    @staticmethod
    def error_file(
        application: str,
        file: str | Path,
    ) -> logging.Handler:

        handler = LoggingHandlers.rotating_file(

            application,

            file,

            level=logging.ERROR,
        )

        return handler

    @staticmethod
    def audit_file(
        application: str,
        file: str | Path,
    ) -> logging.Handler:

        handler = LoggingHandlers.rotating_file(

            application,

            file,

            level=logging.INFO,
        )

        return handler