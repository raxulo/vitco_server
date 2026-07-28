"""
RealTimeTransfer
================

Enterprise Logging Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class RotationConfig:
    """
    File rotation configuration.
    """

    max_bytes: int = 100 * 1024 * 1024

    backup_count: int = 10


@dataclass(slots=True, frozen=True)
class QueueConfig:
    """
    Logging queue configuration.
    """

    enabled: bool = True

    max_size: int = 50_000


@dataclass(slots=True, frozen=True)
class ConsoleConfig:
    """
    Console handler configuration.
    """

    enabled: bool = True


@dataclass(slots=True, frozen=True)
class FileConfig:
    """
    File logging configuration.
    """

    enabled: bool = True

    directory: Path = Path("logs")

    application_log: str = "application.log"

    error_log: str = "error.log"

    audit_log: str = "audit.log"


@dataclass(slots=True, frozen=True)
class LoggingConfig:
    """
    Enterprise logging configuration.
    """

    application: str = "RealTimeTransfer"

    level: str = "INFO"

    json: bool = True

    console: ConsoleConfig = ConsoleConfig()

    files: FileConfig = FileConfig()

    queue: QueueConfig = QueueConfig()

    rotation: RotationConfig = RotationConfig()