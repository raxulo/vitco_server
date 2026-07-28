"""
RealTimeTransfer
================

Enterprise Dependency Scanner

Python 3.13+
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Iterable

from app.core.container.container import Container


class Scanner:
    """
    Automatically discovers injectable classes.
    """

    __slots__ = (
        "_container",
    )

    def __init__(
        self,
        container: Container,
    ) -> None:

        self._container = container

    # --------------------------------------------------

    def scan(
        self,
        *packages: str,
    ) -> None:

        for package in packages:

            self._scan_package(
                package
            )

    # --------------------------------------------------

    def _scan_package(
        self,
        package_name: str,
    ) -> None:

        package = importlib.import_module(
            package_name
        )

        for module in self._walk(
            package
        ):

            self._register_module(
                module
            )

    # --------------------------------------------------

    def _walk(
        self,
        package: ModuleType,
    ) -> Iterable[ModuleType]:

        yield package

        if not hasattr(
            package,
            "__path__",
        ):
            return

        for info in pkgutil.walk_packages(

            package.__path__,

            package.__name__ + ".",
        ):

            yield importlib.import_module(

                info.name
            )

    # --------------------------------------------------

    def _register_module(
        self,
        module: ModuleType,
    ) -> None:

        for _, cls in inspect.getmembers(

            module,

            inspect.isclass,
        ):

            #
            # Skip imported classes
            #

            if cls.__module__ != module.__name__:
                continue

            #
            # Injectable?
            #

            if not getattr(

                cls,

                "__di_injectable__",

                False,
            ):

                continue

            self._container.register(
                cls
            )