"""
RealTimeTransfer
================

Enterprise Session Manager

Python 3.13+
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

class SessionManager:
    """
    Enterprise SQLAlchemy Session Manager.

    Responsibilities
    ----------------
    • Create AsyncSession
    • Close AsyncSession
    • Read-only Session
    • Background Session
    """
    
    __slots__ = (
        "_engine",
        "_factory",
    )

    def __init__(
        self,
        engine: AsyncEngine,
    ) -> None:
        self._engine = engine
        self._factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def factory(self) -> async_sessionmaker[AsyncSession]:
        return self._factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self._factory()
        try:
            yield session
        finally:
            await session.close()

    @asynccontextmanager
    async def readonly(self) -> AsyncIterator[AsyncSession]:
        session = self._factory()
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()
            await session.close()

    def create(self) -> AsyncSession:
        """
        Create unmanaged session.
        """
        return self._factory()

    async def close(self, session: AsyncSession) -> None:
        if session.in_transaction():
            await session.rollback()
        await session.close()

    def __call__(self) -> AsyncSession:
        return self.create()