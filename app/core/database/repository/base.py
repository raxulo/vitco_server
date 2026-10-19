"""
RealTimeTransfer
================

Enterprise Base Repository

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime, timezone
from app.core.clock import get_ist_now
from typing import Any, Generic, Sequence, TypeVar, AsyncIterator
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession


ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """
    Generic Base Repository providing common CRUD, bulk, and streaming operations,
    supporting soft deletes, optimistic locking, and multi-tenant hooks.
    """

    __slots__ = (
        "session",
        "model",
    )

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def _apply_hooks(self, stmt: Any) -> Any:
        """
        Applies soft delete filters, multi-tenancy context filters,
        and sharding hooks.
        """
        # 1. Soft Delete Filter
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.filter(self.model.deleted_at == None)

        # 2. Multi-tenancy Context Hook
        tenant_id = self.session.info.get("tenant_id")
        if tenant_id is not None and hasattr(self.model, "tenant_id"):
            stmt = stmt.filter(self.model.tenant_id == tenant_id)

        # 3. Sharding routing hooks placeholder
        # e.g., sharding_key = self.session.info.get("sharding_key")

        return stmt

    async def get(self, id: Any) -> ModelT | None:
        """
        Get an entity by its primary key, respecting soft deletes.
        """
        entity = await self.session.get(self.model, id)
        if entity is not None and hasattr(entity, "deleted_at"):
            if getattr(entity, "deleted_at") is not None:
                return None
        return entity

    async def get_by(self, **kwargs: Any) -> ModelT | None:
        """
        Get a single entity matching the criteria.
        """
        stmt = select(self.model).filter_by(**kwargs)
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def all(self) -> Sequence[ModelT]:
        """
        Get all entities of this type.
        """
        stmt = select(self.model)
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    def add(self, entity: ModelT) -> None:
        """
        Add a new entity to the session.
        """
        self.session.add(entity)

    async def bulk_add(self, entities: Sequence[ModelT]) -> None:
        """
        Bulk insert objects to the database session.
        """
        self.session.add_all(entities)

    async def bulk_create(self, mappings: list[dict[str, Any]]) -> None:
        """
        High-performance bulk insert using dict mapping insertion.
        """
        if not mappings:
            return
        await self.session.execute(insert(self.model), mappings)

    async def bulk_update(self, mappings: list[dict[str, Any]]) -> None:
        """
        High-performance bulk update using dict mapping updates.
        """
        if not mappings:
            return
        await self.session.execute(update(self.model), mappings)

    async def delete(self, entity: ModelT) -> None:
        """
        Delete an entity (soft delete if model has deleted_at field).
        """
        if hasattr(entity, "deleted_at"):
            setattr(entity, "deleted_at", get_ist_now())
            await self.session.merge(entity)
        else:
            await self.session.delete(entity)

    async def merge(self, entity: ModelT) -> ModelT:
        """
        Merge an entity state into the current session.
        """
        return await self.session.merge(entity)

    async def find_all(self) -> Sequence[ModelT]:
        """
        Retrieve all entities of this type.
        """
        stmt = select(self.model)
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find(self, specification: Specification[ModelT]) -> Sequence[ModelT]:
        """
        Find entities matching a Specification.
        """
        stmt = select(self.model)
        stmt = specification.apply(stmt)
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_one(self, specification: Specification[ModelT]) -> ModelT | None:
        """
        Find a single entity matching a Specification.
        """
        stmt = select(self.model)
        stmt = specification.apply(stmt)
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def stream(self, specification: Specification[ModelT]) -> AsyncIterator[ModelT]:
        """
        Streams database results for large data sets to avoid loading all into memory.
        """
        stmt = select(self.model)
        stmt = specification.apply(stmt)
        stmt = self._apply_hooks(stmt)
        result = await self.session.stream(stmt)
        async for row in result.scalars():
            yield row

    async def batch_get(self, ids: Sequence[Any]) -> Sequence[ModelT]:
        """
        Resolves multiple entities in a single batch query (prevents N+1 database queries).
        """
        if not ids:
            return []
        
        # Get primary key column
        pk_column = self.model.__mapper__.primary_key[0]
        stmt = select(self.model).where(pk_column.in_(ids))
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def keyset_paginate(
        self,
        column: Any,
        last_value: Any | None,
        limit: int,
        order: str = "asc",
    ) -> Sequence[ModelT]:
        """
        High-performance keyset pagination avoiding high offset degradation.
        """
        stmt = select(self.model)
        
        if last_value is not None:
            if order.lower() == "asc":
                stmt = stmt.where(column > last_value)
            else:
                stmt = stmt.where(column < last_value)

        # Apply sorting order
        if order.lower() == "asc":
            stmt = stmt.order_by(column.asc())
        else:
            stmt = stmt.order_by(column.desc())

        stmt = stmt.limit(limit)
        stmt = self._apply_hooks(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_eager(
        self,
        specification: Specification[ModelT],
        options: Sequence[Any],
    ) -> Sequence[ModelT]:
        """
        Finds entities matching a Specification, applying eager loading strategy options.
        """
        stmt = select(self.model)
        stmt = specification.apply(stmt)
        stmt = self._apply_hooks(stmt)
        # Apply eager load options (e.g. joinedload, selectinload)
        if options:
            stmt = stmt.options(*options)
        result = await self.session.execute(stmt)
        return result.scalars().all()



class ReadRepository(BaseRepository[ModelT], Generic[ModelT]):
    """
    Enterprise Read Repository.

    Responsibilities
    ----------------
    • Get entity
    • Find entity
    • List entities
    • Exists
    • Count

    Does NOT
    --------
    • Insert
    • Update
    • Delete
    """

    __slots__ = ()

    async def get(
        self,
        primary_key: object,
    ) -> ModelT | None:
    
        return await self.session.get(
            self.model,
            primary_key,
        )

    async def first(self) -> ModelT | None:

        result = await self.session.execute(
            select(self.model).limit(1)
        )

        return result.scalar_one_or_none()

    async def all(self) -> list[ModelT]:

        result = await self.session.execute(
            select(self.model)
        )

        return list(result.scalars())

    async def exists(
        self,
        primary_key: object,
    ) -> bool:

        return (
            await self.get(primary_key)
        ) is not None

    async def count(self) -> int:

        result = await self.session.execute(
            select(
                func.count()
            ).select_from(
                self.model
            )
        )

        return result.scalar_one()