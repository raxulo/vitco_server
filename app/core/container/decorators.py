"""
RealTimeTransfer
================

Dependency Injection Decorators

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.container.scope import Scope


#
# Metadata attribute name
#

_PROVIDER_METADATA = "__provider_metadata__"


def injectable(
    *,
    scope: Scope = Scope.SINGLETON,
    lazy: bool = True,
):
    """
    Marks a class as injectable.
    """

    def decorator(cls):

        setattr(

            cls,

            _PROVIDER_METADATA,

            {

                "scope": scope,

                "lazy": lazy,
            },
        )

        return cls

    return decorator


def singleton(cls):

    return injectable(

        scope=Scope.SINGLETON

    )(cls)


def scoped(cls):

    return injectable(

        scope=Scope.SCOPED

    )(cls)


def transient(cls):

    return injectable(

        scope=Scope.TRANSIENT

    )(cls)


#
# Semantic decorators
#

service = scoped

repository = scoped

controller = transient

component = singleton