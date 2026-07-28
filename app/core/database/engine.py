"""
RealTimeTransfer
================

Enterprise Database Engine Factory

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)


@dataclass(slots=True, frozen=True)
class EngineOptions:
    """
    SQLAlchemy Engine Options config container.
    """

    url: str | URL
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True


class EngineFactory:
    """
    Enterprise SQLAlchemy Async Engine Factory.
    """

    @staticmethod
    def create(options: EngineOptions) -> AsyncEngine:
        """
        Create and configure an asynchronous SQLAlchemy engine.
        """
        url = str(options.url)

        if url.startswith("sqlite"):
            # SQLite does not support pool_size / max_overflow parameters
            return create_async_engine(
                url,
                echo=options.echo,
                future=True,
            )

        return create_async_engine(
            url,
            echo=options.echo,
            future=True,
            pool_size=options.pool_size,
            max_overflow=options.max_overflow,
            pool_timeout=options.pool_timeout,
            pool_recycle=options.pool_recycle,
            pool_pre_ping=options.pool_pre_ping,
            pool_reset_on_return="rollback",
        )