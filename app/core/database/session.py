# """
# RealTimeTransfer
# ================

# Enterprise Session Manager

# Python 3.13+
# """

# from __future__ import annotations

# from collections.abc import AsyncIterator
# from contextlib import asynccontextmanager

# from sqlalchemy.ext.asyncio import (
#     AsyncEngine,
#     AsyncSession,
#     async_sessionmaker,
# )


# class SessionManager:
#     """
#     Enterprise SQLAlchemy Session Manager.
#     """

#     __slots__ = (
#         "_engine",
#         "_replica_engine",
#         "_factory",
#         "_replica_factory",
#     )

#     def __init__(
#         self,
#         engine: AsyncEngine,
#         replica_engine: AsyncEngine | None = None,
#     ) -> None:
#         self._engine = engine
#         self._replica_engine = replica_engine or engine

#         self._factory = async_sessionmaker(
#             bind=engine,
#             class_=AsyncSession,
#             expire_on_commit=False,
#             autoflush=False,
#         )

#         self._replica_factory = async_sessionmaker(
#             bind=self._replica_engine,
#             class_=AsyncSession,
#             expire_on_commit=False,
#             autoflush=False,
#         )

#     @property
#     def engine(self) -> AsyncEngine:
#         return self._engine

#     @property
#     def replica_engine(self) -> AsyncEngine:
#         return self._replica_engine

#     @property
#     def factory(self) -> async_sessionmaker[AsyncSession]:
#         return self._factory

#     @property
#     def replica_factory(self) -> async_sessionmaker[AsyncSession]:
#         return self._replica_factory

#     @asynccontextmanager
#     async def session(self) -> AsyncIterator[AsyncSession]:
#         """
#         Create managed read-write session.
#         """
#         session = self._factory()
#         try:
#             yield session
#         finally:
#             await session.close()

#     @asynccontextmanager
#     async def readonly(self) -> AsyncIterator[AsyncSession]:
#         """
#         Create managed read-only session routed to replica database.
#         """
#         session = self._replica_factory()
#         try:
#             yield session
#         finally:
#             if session.in_transaction():
#                 await session.rollback()
#             await session.close()

#     def create(self) -> AsyncSession:
#         """
#         Create unmanaged read-write session.
#         """
#         return self._factory()

#     def create_readonly(self) -> AsyncSession:
#         """
#         Create unmanaged read-only session.
#         """
#         return self._replica_factory()

#     async def close(self, session: AsyncSession) -> None:
#         if session.in_transaction():
#             await session.rollback()
#         await session.close()

#     def __call__(self) -> AsyncSession:
#         return self.create()

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)


class SessionManager:

    __slots__ = (
        "_factory",
        "_readonly_factory",
        "_engine",
        "_replica_engine",
    )

    def __init__(
        self,
        engine: AsyncEngine,
        replica_engine: AsyncEngine | None = None,
    ):

        self._engine = engine
        self._replica_engine = replica_engine or engine

        self._factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        self._readonly_factory = async_sessionmaker(
            bind=self._replica_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self):
        return self._engine

    @property
    def replica_engine(self):
        return self._replica_engine

    def create(self) -> AsyncSession:

        return self._factory()

    def create_readonly(self) -> AsyncSession:

        return self._readonly_factory()