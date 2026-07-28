"""
RealTimeTransfer
================

Dependency Injection Scopes

Python 3.13+
"""

from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from enum import StrEnum
from typing import Any


class Scope(StrEnum):
    """
    Service lifetime.
    """

    SINGLETON = "singleton"

    SCOPED = "scoped"

    TRANSIENT = "transient"


#
# Current request scope
#

_CURRENT_SCOPE: ContextVar[
    dict[type, object] | None
] = ContextVar(

    "di_scope",

    default=None,
)


class ScopeManager:
    """
    Request Scope Manager.
    """

    __slots__ = ()

    @staticmethod
    @contextmanager
    def request_scope():
        """
        Creates a new request scope.
        """

        token = _CURRENT_SCOPE.set({})

        try:

            yield

        finally:

            instances = _CURRENT_SCOPE.get()

            if instances:

                #
                # Dispose scoped instances
                #

                for instance in reversed(

                    list(instances.values())

                ):

                    close = getattr(
                        instance,
                        "close",
                        None,
                    )

                    if callable(close):

                        try:

                            close()

                        except Exception:

                            pass

            _CURRENT_SCOPE.reset(token)

    @staticmethod
    def current() -> dict[type, object]:

        scope = _CURRENT_SCOPE.get()

        if scope is None:

            raise RuntimeError(

                "No active request scope."
            )

        return scope

    @staticmethod
    def has_scope() -> bool:

        return (
            _CURRENT_SCOPE.get()
            is not None
        )