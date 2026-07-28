"""
RealTimeTransfer
================

Enterprise Transaction Manager

Python 3.13+
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
import asyncio
import uuid

from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
    OperationalError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.exceptions import (
    DatabaseConnectionError,
    DatabaseIntegrityError,
    DatabaseTimeoutError,
    QueryExecutionError,
)
from app.core.database.session import SessionManager


class IsolationLevel(str, Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass(slots=True, frozen=True)
class RetryPolicy:
    retries: int = 3
    delay: float = 0.5
    exponential_backoff: bool = True
    max_delay: float = 8.0


@dataclass(slots=True)
class TransactionOptions:
    readonly: bool = False
    timeout: float = 30.0
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED
    retry: RetryPolicy = RetryPolicy()


@dataclass(slots=True)
class TransactionContext:
    transaction_id: str
    session: AsyncSession


_CURRENT: ContextVar[TransactionContext | None] = ContextVar(
    "database_transaction",
    default=None,
)


class TransactionManager:
    __slots__ = ("_sessions",)

    RETRY_SQLSTATE = {
        "40001",
        "40P01",
    }

    def __init__(
        self,
        sessions: SessionManager,
    ) -> None:
        self._sessions = sessions

    @property
    def current(self) -> TransactionContext | None:
        return _CURRENT.get()

    @property
    def session(self) -> AsyncSession:
        tx = self.current
        if tx is None:
            raise RuntimeError("No active transaction.")
        return tx.session

    @staticmethod
    def transaction_id() -> str:
        return uuid.uuid4().hex

    async def _sleep(
        self,
        attempt: int,
        retry: RetryPolicy,
    ) -> None:
        delay = retry.delay
        if retry.exponential_backoff:
            delay *= 2**attempt
        await asyncio.sleep(min(delay, retry.max_delay))

    @staticmethod
    def _sqlstate(exc: Exception) -> str | None:
        return getattr(getattr(exc, "orig", None), "sqlstate", None)

    def _retryable(self, exc: Exception) -> bool:
        if not isinstance(exc, OperationalError):
            return False
        return self._sqlstate(exc) in self.RETRY_SQLSTATE

    @asynccontextmanager
    async def transaction(
        self,
        options: TransactionOptions | None = None,
    ) -> AsyncIterator[AsyncSession]:
        if options is None:
            options = TransactionOptions()

        # Nested Transaction
        current = self.current
        if current is not None:
            async with current.session.begin_nested():
                yield current.session
            return

        # Retry Loop
        for attempt in range(options.retry.retries + 1):
            session = self._sessions.create()
            token = _CURRENT.set(
                TransactionContext(
                    transaction_id=self.transaction_id(),
                    session=session,
                )
            )

            try:
                async with asyncio.timeout(options.timeout):
                    connection = await session.connection()
                    await connection.execution_options(
                        isolation_level=options.isolation.value
                    )
                    async with session.begin():
                        if options.readonly:
                            await session.execute("SET TRANSACTION READ ONLY")
                        yield session
                break

            except TimeoutError as ex:
                await session.rollback()
                raise DatabaseTimeoutError() from ex

            except IntegrityError as ex:
                await session.rollback()
                raise DatabaseIntegrityError() from ex

            except OperationalError as ex:
                await session.rollback()
                if attempt < options.retry.retries and self._retryable(ex):
                    await self._sleep(attempt, options.retry)
                    continue
                raise DatabaseConnectionError() from ex

            except DBAPIError as ex:
                await session.rollback()
                raise QueryExecutionError() from ex

            finally:
                _CURRENT.reset(token)
                await session.close()