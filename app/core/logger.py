"""
RealTimeTransfer
================

Enterprise Logger Service

Python : 3.13
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import config


class LoggerService:
    """
    Enterprise Logger
    """

    _initialized = False

    def initialize(self) -> None:

        if self._initialized:
            return

        log_path = Path(config.logging.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.remove()

        # Console Logger
        if config.logging.console:
            logger.add(
                sys.stdout,
                level=config.logging.level,
                format=config.logging.format,
                enqueue=True,
                backtrace=config.logging.backtrace,
                diagnose=config.logging.diagnose,
            )

        # File Logger
        if config.logging.file:

            logger.add(
                log_path,
                level=config.logging.level,
                rotation=config.logging.rotation,
                retention=config.logging.retention,
                compression=config.logging.compression,
                enqueue=True,
                format=config.logging.format,
                backtrace=config.logging.backtrace,
                diagnose=config.logging.diagnose,
                serialize=config.logging.serialize,
            )

        self._initialized = True

    def bind(self, **kwargs: Any):

        return logger.bind(**kwargs)

    def trace(self, message: str, *args, **kwargs):

        logger.trace(message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs):

        logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):

        logger.info(message, *args, **kwargs)

    def success(self, message: str, *args, **kwargs):

        logger.success(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):

        logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):

        logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):

        logger.critical(message, *args, **kwargs)

    def exception(self, message: str):

        logger.exception(message)


log = LoggerService()