"""
==========================================================
Enterprise Session Context

Google
Microsoft
Uber
Netflix

Python 3.13
==========================================================
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession


class SessionContextError(RuntimeError):
    """Base session context error."""


class SessionNotAvailableError(SessionContextError):
    """Raised when no session exists in current context."""


class SessionAlreadyExistsError(SessionContextError):
    """Raised when attempting to overwrite active session."""


class SessionContext:
    """
    Enterprise AsyncSession Context.

    One AsyncSession per async execution context.

    Thread Safe

    Async Safe

    Lock Free
    """

    __slots__ = ()

    _session: Final[
        ContextVar[AsyncSession | None]
    ] = ContextVar(
        "database_session",
        default=None,
    )

    # ---------------------------------------------------------

    @classmethod
    def exists(cls) -> bool:

        return cls._session.get() is not None

    # ---------------------------------------------------------

    @classmethod
    def get(cls) -> AsyncSession:

        session = cls._session.get()

        if session is None:

            raise SessionNotAvailableError(

                "Database session is not available."

            )

        return session

    # ---------------------------------------------------------

    @classmethod
    def set(
        cls,
        session: AsyncSession,
    ):

        if cls.exists():

            raise SessionAlreadyExistsError(

                "Session already exists."

            )

        return cls._session.set(
            session
        )

    # ---------------------------------------------------------

    @classmethod
    def reset(
        cls,
        token,
    ) -> None:

        cls._session.reset(
            token
        )

    # ---------------------------------------------------------

    @classmethod
    def clear(cls) -> None:

        cls._session.set(None)