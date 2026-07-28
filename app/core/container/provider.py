# """
# RealTimeTransfer
# ================

# Dependency Injection Providers

# Author : Rahul Baghel

# Python : 3.13
# """

# from __future__ import annotations

# from dishka import Provider
# from dishka import Scope
# from dishka import provide

# from app.core.config import config


# class ConfigProvider(Provider):

#     scope = Scope.APP

#     @provide
#     def settings(self):

#         return config.settings

#     @provide
#     def database(self):

#         return config.database

#     @provide
#     def logging(self):

#         return config.logging

#     @provide
#     def websocket(self):

#         return config.websocket

#     @provide
#     def transfer(self):

#         return config.chunk

#     @provide
#     def storage(self):

#         return config.storage

#     @provide
#     def security(self):

#         return config.jwt

"""
RealTimeTransfer
================

Dependency Injection Provider

Python 3.13+
"""

from __future__ import annotations

import inspect

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.container.scope import Scope


@dataclass(slots=True)
class ServiceProvider:
    """
    Describes how a service should be created.
    """

    service_type: type

    factory: Callable[..., Any]

    scope: Scope = Scope.SINGLETON

    lazy: bool = True

    dispose: bool = True

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def create(
        self,
        container,
    ) -> Any:
        """
        Create service instance.
        """

        signature = inspect.signature(
            self.factory
        )

        kwargs = {}

        for parameter in (
            signature.parameters.values()
        ):

            annotation = parameter.annotation

            if annotation is inspect._empty:

                raise TypeError(

                    f"{self.factory.__name__}"

                    f"() parameter "

                    f"'{parameter.name}' "

                    "must have type annotation."
                )

            kwargs[
                parameter.name
            ] = container.resolve(
                annotation
            )

        return self.factory(
            **kwargs
        )