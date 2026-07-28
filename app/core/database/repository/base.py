"""
RealTimeTransfer
================

Enterprise Base Repository

Python 3.13+
"""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.specification import Specification

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """
    Generic Base Repository providing common CRUD operations.
    """

    __slots__ = (
        "session",
        "model",
    )

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, id: Any) -> ModelT | None:
        """
        Get an entity by its primary key.
        """
        return await self.session.get(self.model, id)

    async def get_by(self, **kwargs: Any) -> ModelT | None:
        """
        Get a single entity matching the criteria.
        """
        stmt = select(self.model).filter_by(**kwargs)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def all(self) -> Sequence[ModelT]:
        """
        Get all entities of this type.
        """
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    def add(self, entity: ModelT) -> None:
        """
        Add a new entity to the session.
        """
        self.session.add(entity)

    async def delete(self, entity: ModelT) -> None:
        """
        Delete an entity from the database.
        """
        await self.session.delete(entity)

    async def merge(self, entity: ModelT) -> ModelT:
        """
        Merge an entity state into the current session.
        """
        return await self.session.merge(entity)

    async def find(
        self, specification: Specification[ModelT]
    ) -> Sequence[ModelT]:
        """
        Find entities matching a Specification.
        """
        stmt = select(self.model)
        stmt = specification.apply(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_one(
        self, specification: Specification[ModelT]
    ) -> ModelT | None:
        """
        Find a single entity matching a Specification.
        """
        stmt = select(self.model)
        stmt = specification.apply(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

