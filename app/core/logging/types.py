"""
RealTimeTransfer
================

Logger Types

Python 3.13+
"""

from __future__ import annotations

from enum import IntEnum
from enum import StrEnum

import logging


class LogLevel(IntEnum):
    """
    Logging levels.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(StrEnum):
    """
    Formatter type.
    """

    CONSOLE = "console"

    JSON = "json"


class LogFile(StrEnum):
    """
    Log filenames.
    """

    APPLICATION = "application.log"

    ERROR = "error.log"

    ACCESS = "access.log"