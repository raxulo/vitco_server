"""
Get Mixin

Python 3.13+
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class GetMixin(Generic[T]):
    """
    Provides primary-key lookup functionality.
    """

    __slots__ = ()

    @property
    def session(self) -> AsyncSession:
        ...

    @property
    def model(self) -> type[T]:
        ...

    async def get(
        self,
        primary_key: object,
    ) -> T | None:

        return await self.session.get(
            self.model,
            primary_key,
        )


class ExistsMixin(Generic[T]):
    """
    Provides efficient existence checks.

    Responsibilities
    ----------------
    • EXISTS queries

    Does NOT
    --------
    • Load entities
    """

    __slots__ = ()

    @property
    def session(self) -> AsyncSession:
        ...

    @property
    def model(self) -> type[T]:
        ...

    async def exists(
        self,
        **filters,
    ) -> bool:

        statement = select(
            exists().where(
                *(
                    getattr(self.model, key) == value
                    for key, value in filters.items()
                )
            )
        )

        result = await self.session.scalar(statement)

        return bool(result)


class CountMixin(Generic[T]):
    """
    Provides optimized COUNT queries.
    """

    __slots__ = ()

    @property
    def session(self) -> AsyncSession:
        ...

    @property
    def model(self) -> type[T]:
        ...

    async def count(
        self,
        *criteria,
    ) -> int:
        """
        Count entities matching the given criteria.
        """

        statement = (
            select(func.count())
            .select_from(self.model)
            .where(*criteria)
        )

        result = await self.session.scalar(statement)

        return int(result or 0)