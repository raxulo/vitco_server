"""
RealTimeTransfer
================

Enterprise Logger Manager

Python 3.13+
"""

from __future__ import annotations

import logging

from app.config.logging import LOGGER_CONFIG
from app.config.settings import settings
from app.core.logging.handlers import HandlerFactory
from app.core.logging.queue import LoggerQueue

class LoggerManager:
    """
    Enterprise logger lifecycle manager.

    Thread-safe startup.

    Idempotent startup/shutdown.
    """

    __slots__ = (
        "_logger",
        "_queue",
        "_started",
    )

    def __init__(
        self,
        logger: logging.Logger,
    ) -> None:

        self._logger = logger

        self._queue = LoggerQueue(
            LOGGER_CONFIG.queue_size,
        )

        self._started = False

    # ---------------------------------------------------------

    @property
    def logger(
        self,
    ) -> logging.Logger:

        return self._logger

    # ---------------------------------------------------------

    @property
    def started(
        self,
    ) -> bool:

        return self._started

    # ---------------------------------------------------------

    def startup(
        self,
    ) -> None:

        if self._started:
            return

        handlers = HandlerFactory.create()

        self._logger.setLevel(
            LOGGER_CONFIG.level,
        )

        self._logger.handlers.clear()

        self._logger.addHandler(
            self._queue.handler,
        )

        self._logger.propagate = False

        self._queue.start(
            *handlers,
        )

        self._bind_external_loggers()

        self._started = True

    # ---------------------------------------------------------

    def shutdown(
        self,
    ) -> None:

        if not self._started:
            return

        self._queue.stop()

        self._logger.handlers.clear()

        self._started = False

    # ---------------------------------------------------------

    def _bind_external_loggers(
        self,
    ) -> None:

        names = (

            "uvicorn",

            "uvicorn.error",

            "uvicorn.access",

            "fastapi",

            "sqlalchemy.engine",

            "sqlalchemy.pool",

        )

        handlers = self._logger.handlers

        level = self._logger.level

        # SQL lines carry their values: buyer phone numbers and addresses, password hashes.
        # They stay out of the log files unless DATABASE_ECHO asks for them.
        sql_level = level if settings.DATABASE_ECHO else logging.WARNING

        for name in names:

            logger = logging.getLogger(
                name,
            )

            logger.handlers = handlers

            logger.setLevel(
                sql_level if name.startswith("sqlalchemy") else level,
            )

            logger.propagate = False