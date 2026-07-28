"""
RealTimeTransfer
================

Enterprise Dependency Injection Container

Python 3.13+
"""

from __future__ import annotations

import inspect

from typing import Any


class Container:
    """
    Enterprise Dependency Injection Container.
    """

    __slots__ = (
        "_providers",
        "_singletons",
    )

    def __init__(self) -> None:

        self._providers: dict[
            type,
            Any,
        ] = {}

        self._singletons: dict[
            type,
            object,
        ] = {}

    # --------------------------------------------------
    # Register
    # --------------------------------------------------

    def register_instance(
        self,
        interface: type,
        instance: object,
    ) -> None:

        self._singletons[
            interface
        ] = instance

    def register_factory(
        self,
        interface: type,
        factory,
    ) -> None:

        self._providers[
            interface
        ] = factory

    # --------------------------------------------------
    # Resolve
    # --------------------------------------------------

    def resolve(
        self,
        cls: type,
    ) -> object:

        #
        # Existing singleton
        #

        if cls in self._singletons:

            return self._singletons[cls]

        #
        # Registered provider
        #

        if cls in self._providers:

            return self._providers[
                cls
            ]()

        #
        # Automatic constructor injection
        #

        signature = inspect.signature(
            cls.__init__
        )

        kwargs = {}

        for name, parameter in list(
            signature.parameters.items()
        )[1:]:

            dependency = parameter.annotation

            kwargs[name] = self.resolve(
                dependency
            )

        instance = cls(
            **kwargs
        )

        return instance