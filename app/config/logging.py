# """
# RealTimeTransfer
# ================

# Logging Configuration

# This module contains logging configuration only.

# Python : 3.13
# """

# from __future__ import annotations

# from dataclasses import dataclass
# from pathlib import Path

# from app.config.settings import settings


# @dataclass(slots=True, frozen=True)
# class LoggingConfig:
#     """
#     Application logging configuration.
#     """

#     level: str
#     file_path: Path

#     rotation: str
#     retention: str
#     compression: str | None

#     enqueue: bool
#     backtrace: bool
#     diagnose: bool
#     serialize: bool

#     console: bool
#     file: bool

#     format: str


# logging_config = LoggingConfig(
#     level=settings.LOG_LEVEL,
#     file_path=Path(settings.LOG_FILE),

#     rotation="100 MB",
#     retention="30 days",
#     compression="zip",

#     enqueue=True,
#     backtrace=False if settings.is_production else True,
#     diagnose=False if settings.is_production else True,
#     serialize=False,

#     console=True,
#     file=True,

#     format=(
#         "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
#         "<level>{level: <8}</level> | "
#         "<cyan>{process}</cyan>:<cyan>{thread}</cyan> | "
#         "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
#         "<level>{message}</level>"
#     ),
# )


"""
RealTimeTransfer
================

Logger Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.settings import settings
from app.core.logging.types import (
    LogFile,
    LogLevel,
)


# ==========================================================
# Configuration
# ==========================================================

@dataclass(
    slots=True,
    frozen=True,
)
class LoggerConfig:
    """
    Immutable logger configuration.
    """

    # ------------------------------------------------------
    # Logger
    # ------------------------------------------------------

    name: str = "realtimetransfer"

    level: int = LogLevel.INFO

    # ------------------------------------------------------
    # Queue
    # ------------------------------------------------------

    queue_size: int = 50_000

    # ------------------------------------------------------
    # Files
    # ------------------------------------------------------

    directory: Path = Path("logs")

    application_file: str = LogFile.APPLICATION

    error_file: str = LogFile.ERROR

    access_file: str = LogFile.ACCESS

    encoding: str = "utf-8"

    # ------------------------------------------------------
    # Rotation
    # ------------------------------------------------------

    max_file_size: int = 100 * 1024 * 1024      # 100 MB

    backup_count: int = 20

    # ------------------------------------------------------
    # Console
    # ------------------------------------------------------

    console_level: int = LogLevel.DEBUG if settings.DEBUG else LogLevel.INFO

    file_level: int = LogLevel.INFO

    error_level: int = LogLevel.ERROR

    # ------------------------------------------------------
    # JSON
    # ------------------------------------------------------

    json_indent: int | None = None

    ensure_ascii: bool = False


# ==========================================================
# Singleton Config
# ==========================================================

LOGGER_CONFIG = LoggerConfig()