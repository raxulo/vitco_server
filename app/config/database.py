"""
RealTimeTransfer
================

Database Configuration

This module contains database-related configuration.

Python : 3.13
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings


@dataclass(slots=True, frozen=True)
class DatabaseConfig:
    """
    Database Configuration
    """

    url: str
    echo: bool
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool


database_config = DatabaseConfig(
    url=settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)