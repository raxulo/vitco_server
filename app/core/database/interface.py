# """
# RealTimeTransfer
# ================

# Database Driver Interface

# Enterprise Database Abstraction

# Python 3.13+
# """

# from __future__ import annotations

# from abc import ABC, abstractmethod
# from typing import TYPE_CHECKING

# from sqlalchemy.ext.asyncio import AsyncEngine

# if TYPE_CHECKING:
#     from app.core.database.session import SessionManager


# class DatabaseDriver(ABC):
#     """
#     Base interface for all database drivers.
#     """

#     @property
#     @abstractmethod
#     def engine(self) -> AsyncEngine:
#         """
#         Return SQLAlchemy async engine.
#         """
#         raise NotImplementedError

#     @abstractmethod
#     async def start(self) -> None:
#         """
#         Initialize driver.
#         """
#         raise NotImplementedError

#     @abstractmethod
#     async def stop(self) -> None:
#         """
#         Shutdown driver.
#         """
#         raise NotImplementedError

#     @property
#     @abstractmethod
#     def session_manager(self) -> SessionManager:
#         """
#         Return session manager.
#         """
#         raise NotImplementedError

#     @abstractmethod
#     async def health(self) -> dict:
#         """
#         Health status.
#         """
#         raise NotImplementedError


from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database.session import SessionManager


class DatabaseDriver(ABC):

    __slots__ = ()

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def engine(self) -> AsyncEngine:
        ...

    @property
    @abstractmethod
    def session_manager(self) -> SessionManager:
        ...

    @property
    @abstractmethod
    def connected(self) -> bool:
        ...

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

