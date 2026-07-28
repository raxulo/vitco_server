"""
RealTimeTransfer
================

Enterprise Scoped Context

Python 3.13+
"""

from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager

from app.core.container.provider import Provider


_SCOPED: ContextVar[
    dict[Provider, object] | None
] = ContextVar(

    "di_scope",

    default=None,
)


class ScopeContext:
    """
    Request Scope Storage.
    """

    __slots__ = ()

    @staticmethod
    @contextmanager
    def begin():

        token = _SCOPED.set({})

        try:

            yield

        finally:

            _SCOPED.reset(token)

    @staticmethod
    def get(
        provider: Provider,
    ) -> object | None:

        scope = _SCOPED.get()

        if scope is None:

            return None

        return scope.get(provider)

    @staticmethod
    def set(

        provider: Provider,

        instance: object,

    ) -> None:

        scope = _SCOPED.get()

        if scope is None:

            raise RuntimeError(
                "No active scope."
            )

        scope[provider] = instance