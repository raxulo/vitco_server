"""
RealTimeTransfer
================

Enterprise Dependency Injector

Python 3.13+
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

from app.core.container.container import Container


class Injector:

    """
    Enterprise Dependency Injector.
    """

    __slots__ = (
        "_container",
    )

    def __init__(
        self,
        container: Container,
    ) -> None:

        self._container = container

    def inject(
        self,
        func: Callable[..., Any],
    ) -> Callable[..., Any]:

        signature = inspect.signature(func)

        @wraps(func)
        async def wrapper(
            *args,
            **kwargs,
        ):

            for (
                name,
                parameter,
            ) in signature.parameters.items():

                #
                # Already supplied
                #

                if name in kwargs:
                    continue

                #
                # No annotation
                #

                if (
                    parameter.annotation
                    is inspect.Signature.empty
                ):
                    continue

                #
                # Resolve
                #

                kwargs[name] = self._container.resolve(

                    parameter.annotation
                )

            return await func(

                *args,

                **kwargs,
            )

        return wrapper