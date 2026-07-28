"""
RealTimeTransfer
================

Logging Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config.base import BaseConfig


# ==========================================================
# Log Level
# ==========================================================

class LogLevel(StrEnum):

    CRITICAL = "CRITICAL"

    ERROR = "ERROR"

    WARNING = "WARNING"

    INFO = "INFO"

    DEBUG = "DEBUG"

    TRACE = "TRACE"


# ==========================================================
# Log Format
# ==========================================================

class LogFormat(StrEnum):

    JSON = "json"

    TEXT = "text"


# ==========================================================
# Console Logging
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class ConsoleConfig(BaseConfig):

    enabled: bool = True

    level: LogLevel = LogLevel.INFO

    colored: bool = True


# ==========================================================
# File Logging
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class FileConfig(BaseConfig):

    enabled: bool = True

    directory: str = "logs"

    filename: str = "application.log"

    max_size: int = 100 * 1024 * 1024

    backup_count: int = 10

    compress: bool = True


# ==========================================================
# Access Log
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class AccessLogConfig(BaseConfig):

    enabled: bool = True

    filename: str = "access.log"


# ==========================================================
# Error Log
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class ErrorLogConfig(BaseConfig):

    enabled: bool = True

    filename: str = "error.log"


# ==========================================================
# Main Logging Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class LoggingConfig(BaseConfig):

    level: LogLevel = LogLevel.INFO

    format: LogFormat = LogFormat.JSON

    console: ConsoleConfig = ConsoleConfig()

    file: FileConfig = FileConfig()

    access: AccessLogConfig = AccessLogConfig()

    error: ErrorLogConfig = ErrorLogConfig()

    request_id: bool = True

    transaction_id: bool = True

    stack_trace: bool = True