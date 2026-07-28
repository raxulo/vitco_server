"""
RealTimeTransfer
================

Enterprise Unit Of Work

Python 3.13+
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.repository.base import BaseRepository
from app.core.database.transaction import (
    TransactionManager,
    TransactionOptions,
)


class UnitOfWork:
    """
    Enterprise Unit Of Work.

    Provides a clean transactional boundary wrapper around database operations.
    """

    __slots__ = (
        "_transactions",
        "_repositories",
        "_session",
    )

    def __init__(
        self,
        transactions: TransactionManager,
    ) -> None:
        self._transactions = transactions
        self._repositories: dict[type, BaseRepository] = {}
        self._session: AsyncSession | None = None

    @asynccontextmanager
    async def transaction(
        self,
        options: TransactionOptions | None = None,
    ) -> AsyncIterator[UnitOfWork]:
        async with self._transactions.transaction(options) as session:
            self._session = session
            self._repositories.clear()
            try:
                yield self
            finally:
                self._repositories.clear()
                self._session = None

    def repository(
        self,
        model: type[Any],
    ) -> BaseRepository:
        if self._session is None:
            raise RuntimeError("No active transaction.")

        repo = self._repositories.get(model)
        if repo is not None:
            return repo

        repo = BaseRepository(
            self._session,
            model,
        )
        self._repositories[model] = repo
        return repo

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("No active transaction.")
        return self._session