"""
RealTimeTransfer
================

Enterprise Logger

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import logging
from typing import Any


class EnterpriseLogger:
    """
    Enterprise logger wrapper.

    This class NEVER creates loggers.

    It only wraps logging.Logger.

    Creation is handled by LoggerFactory.
    """

    __slots__ = (
        "_logger",
    )

    def __init__(
        self,
        logger: logging.Logger,
    ) -> None:

        self._logger = logger

    @property
    def name(
        self,
    ) -> str:

        return self._logger.name

    def debug(
        self,
        message: str,
        **extra: Any,
    ) -> None:

        self._logger.debug(

            message,

            extra=extra,

            stacklevel=2,
        )

    def info(
        self,
        message: str,
        **extra: Any,
    ) -> None:

        self._logger.info(

            message,

            extra=extra,

            stacklevel=2,
        )

    def warning(
        self,
        message: str,
        **extra: Any,
    ) -> None:

        self._logger.warning(

            message,

            extra=extra,

            stacklevel=2,
        )

    def error(
        self,
        message: str,
        *,
        exception: Exception | None = None,
        **extra: Any,
    ) -> None:

        self._logger.error(

            message,

            exc_info=exception,

            extra=extra,

            stacklevel=2,
        )

    def critical(
        self,
        message: str,
        *,
        exception: Exception | None = None,
        **extra: Any,
    ) -> None:

        self._logger.critical(

            message,

            exc_info=exception,

            extra=extra,

            stacklevel=2,
        )

    def exception(
        self,
        message: str,
        **extra: Any,
    ) -> None:

        self._logger.exception(

            message,

            extra=extra,

            stacklevel=2,
        )