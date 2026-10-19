"""
RealTimeTransfer
================

Logger Factory

Python 3.13+
"""

from __future__ import annotations
from app.core.logging.manager import LoggerManager

import logging

from app.config.logging import LOGGER_CONFIG


def get_logger(
    name: str | None = None,
) -> logging.Logger:
    """
    Return application logger.

    Parameters
    ----------
    name:
        Optional child logger name.

    Examples
    --------

    logger = get_logger(__name__)

    logger = get_logger("auth")
    """

    root = logging.getLogger(
        LOGGER_CONFIG.name,
    )

    if name is None:
        return root

    return root.getChild(name)


logger = get_logger()

logger_manager = LoggerManager(logger)