"""
RealTimeTransfer
================

Enterprise Logger Handlers

Python 3.13+
"""

from __future__ import annotations

import logging

from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.logging import LOGGER_CONFIG
from app.core.logging.filters import (
    ContextFilter,
    ErrorOnlyFilter,
)
from app.core.logging.formatter import (
    ConsoleFormatter,
    JsonFormatter,
)


class HandlerFactory:
    """
    Creates logging handlers.

    Stateless.

    Thread-safe.
    """

    __slots__ = ()

    # ---------------------------------------------------------

    @staticmethod
    def console() -> logging.Handler:

        handler = logging.StreamHandler()

        handler.setLevel(
            LOGGER_CONFIG.console_level,
        )

        handler.setFormatter(
            ConsoleFormatter(),
        )

        handler.addFilter(
            ContextFilter(),
        )

        return handler

    # ---------------------------------------------------------

    @staticmethod
    def application_file() -> logging.Handler:

        Path(
            LOGGER_CONFIG.directory,
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        handler = RotatingFileHandler(

            filename=(
                LOGGER_CONFIG.directory
                /
                LOGGER_CONFIG.application_file
            ),

            maxBytes=LOGGER_CONFIG.max_file_size,

            backupCount=LOGGER_CONFIG.backup_count,

            encoding=LOGGER_CONFIG.encoding,

        )

        handler.setLevel(
            LOGGER_CONFIG.file_level,
        )

        handler.setFormatter(
            JsonFormatter(),
        )

        handler.addFilter(
            ContextFilter(),
        )

        return handler

    # ---------------------------------------------------------

    @staticmethod
    def error_file() -> logging.Handler:

        Path(
            LOGGER_CONFIG.directory,
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        handler = RotatingFileHandler(

            filename=(
                LOGGER_CONFIG.directory
                /
                LOGGER_CONFIG.error_file
            ),

            maxBytes=LOGGER_CONFIG.max_file_size,

            backupCount=LOGGER_CONFIG.backup_count,

            encoding=LOGGER_CONFIG.encoding,

        )

        handler.setLevel(
            LOGGER_CONFIG.error_level,
        )

        handler.setFormatter(
            JsonFormatter(),
        )

        handler.addFilter(
            ContextFilter(),
        )

        handler.addFilter(
            ErrorOnlyFilter(),
        )

        return handler

    # ---------------------------------------------------------

    @classmethod
    def create(
        cls,
    ) -> tuple[logging.Handler, ...]:

        return (

            cls.console(),

            cls.application_file(),

            cls.error_file(),

        )