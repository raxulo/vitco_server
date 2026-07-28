"""
RealTimeTransfer
================

Logging Configuration

This module contains logging configuration only.

Python : 3.13
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.settings import settings


@dataclass(slots=True, frozen=True)
class LoggingConfig:
    """
    Application logging configuration.
    """

    level: str
    file_path: Path

    rotation: str
    retention: str
    compression: str | None

    enqueue: bool
    backtrace: bool
    diagnose: bool
    serialize: bool

    console: bool
    file: bool

    format: str


logging_config = LoggingConfig(
    level=settings.LOG_LEVEL,
    file_path=Path(settings.LOG_FILE),

    rotation="100 MB",
    retention="30 days",
    compression="zip",

    enqueue=True,
    backtrace=False if settings.is_production else True,
    diagnose=False if settings.is_production else True,
    serialize=False,

    console=True,
    file=True,

    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{process}</cyan>:<cyan>{thread}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
)