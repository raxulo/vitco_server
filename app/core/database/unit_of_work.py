# # """
# # RealTimeTransfer
# # ================

# # Enterprise Unit Of Work

# # Python 3.13+
# # """

# # from __future__ import annotations

# # from collections.abc import AsyncIterator
# # from contextlib import asynccontextmanager
# # from typing import Any

# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.core.database.repository.base import BaseRepository
# # from app.core.database.transaction import (
# #     TransactionManager,
# #     TransactionOptions,
# # )


# # class UnitOfWork:
# #     """
# #     Enterprise Unit Of Work.

# #     Provides a clean transactional boundary wrapper around database operations.
# #     Supports request-scoped SessionContext fallbacks.
# #     """

# #     __slots__ = (
# #         "_transactions",
# #         "_repositories",
# #         "_session",
# #     )

# #     def __init__(
# #         self,
# #         transactions: Any,
# #     ) -> None:
# #         self._transactions = transactions
# #         self._repositories: dict[type, BaseRepository] = {}
# #         self._session: AsyncSession | None = None

# #     @asynccontextmanager
# #     async def transaction(
# #         self,
# #         options: TransactionOptions | None = None,
# #     ) -> AsyncIterator[UnitOfWork]:
# #         transactions = self._transactions
# #         if callable(transactions):
# #             transactions = transactions()
# #         async with transactions.transaction(options) as session:
# #             self._session = session
# #             self._repositories.clear()
# #             try:
# #                 yield self
# #             finally:
# #                 self._repositories.clear()
# #                 self._session = None

# #     def repository(
# #         self,
# #         model: type[Any],
# #     ) -> BaseRepository:
# #         """
# #         Get or create a repository for a given model class.
# #         """
# #         session = self.session  # Resolves active or request-scoped session
# #         repo = self._repositories.get(model)
# #         if repo is not None:
# #             # Verify the cached repository matches the current active session
# #             if repo.session is session:
# #                 return repo

# #         repo = BaseRepository(
# #             session,
# #             model,
# #         )
# #         self._repositories[model] = repo
# #         return repo

# #     @property
# #     def session(self) -> AsyncSession:
# #         """
# #         Get the active session. Falls back to request-scoped SessionContext if active.
# #         """
# #         if self._session is not None:
# #             return self._session

# #         from app.core.database.session_context import SessionContext
# #         if SessionContext.exists():
# #             return SessionContext.get()

# #         raise RuntimeError("No active transaction or request-scoped session context.")


# """
# Enterprise Unit Of Work

# Python 3.13+
# """

# from app.core.database.transaction import TransactionOptions
# from app.core.database.manager import DatabaseManager
# from __future__ import annotations

# from contextlib import AbstractAsyncContextManager
# from typing import Any

# from sqlalchemy.ext.asyncio import AsyncSession


# class UnitOfWork(AbstractAsyncContextManager["UnitOfWork"]):
#     """
#     Enterprise Unit Of Work.

#     Features

#     - Automatic Commit
#     - Automatic Rollback
#     - Lazy Repository Resolution
#     - Repository Cache
#     - Zero Manual Session Handling
#     """

#     __slots__ = (
#         "_container",
#         "_transactions",
#         "_session",
#         "_repositories",
#     )

#     def __init__(
#         self,
#         container: ServiceContainer,
#         transactions: TransactionManager,
#     ) -> None:

#         self._container = container
#         self._transactions = transactions

#         self._session: AsyncSession | None = None

#         self._repositories: dict[type[Any], Any] = {}

#     # ---------------------------------------------------------

#     async def __aenter__(self) -> "UnitOfWork":

#         self._session = await self._transactions.begin()

#         return self

#     # ---------------------------------------------------------

#     async def __aexit__(
#         self,
#         exc_type,
#         exc,
#         tb,
#     ) -> bool:

#         try:

#             if exc is None:

#                 await self._transactions.commit()

#             else:

#                 await self._transactions.rollback()

#         finally:

#             self._repositories.clear()

#             self._session = None

#         return False

#     # ---------------------------------------------------------

#     @property
#     def session(self) -> AsyncSession:

#         if self._session is None:

#             raise RuntimeError(
#                 "UnitOfWork is not active."
#             )

#         return self._session

#     # ---------------------------------------------------------

#     def resolve(
#         self,
#         repository_type: type[Any],
#     ) -> Any:
#         """
#         Resolve repository lazily.

#         Repository is created only once
#         per transaction.
#         """

#         repository = self._repositories.get(repository_type)

#         if repository is not None:

#             return repository

#         repository = self._container.resolve(
#             repository_type,
#         )

#         self._repositories[repository_type] = repository

#         return repository
from app.core.database.manager import DatabaseManager


from sqlalchemy.ext.asyncio import AsyncSession

class UnitOfWork:

    __slots__ = (
        "_database",
        "_options",
    )

    def __init__(
        self,
        database: DatabaseManager,
    ):
        self._database = database

        # self._options = TransactionOptions()

    async def __aenter__(self):

        self._tx = self._database.transaction()

        await self._tx.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc, tb):

        await self._tx.__aexit__(exc_type, exc, tb)