"""
RealTimeTransfer
================

Enterprise CQRS & Mediator Pattern (Microsoft / Netflix Architecture)

Decouples Commands (mutations) from Queries (reads) via a central Mediator Engine.

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Dict, Type

R = TypeVar("R")


class Command(ABC, Generic[R]):
    """
    Base Command representing a state mutation request.
    """


class Query(ABC, Generic[R]):
    """
    Base Query representing a read-only data request.
    """


class CommandHandler(ABC, Generic[R]):
    """
    Handler for processing a specific Command.
    """

    @abstractmethod
    async def handle(self, command: Any) -> R:
        """
        Execute command mutation logic.
        """


class QueryHandler(ABC, Generic[R]):
    """
    Handler for executing a specific Query.
    """

    @abstractmethod
    async def handle(self, query: Any) -> R:
        """
        Execute read-only query logic.
        """


class Mediator:
    """
    Enterprise Mediator Engine for routing Commands and Queries to their handlers.
    """

    __slots__ = ("_command_handlers", "_query_handlers")

    def __init__(self) -> None:
        self._command_handlers: Dict[Type[Any], CommandHandler] = {}
        self._query_handlers: Dict[Type[Any], QueryHandler] = {}

    def register_command_handler(
        self, command_type: Type[Any], handler: CommandHandler
    ) -> None:
        """
        Register a command handler instance for a command type.
        """
        self._command_handlers[command_type] = handler

    def register_query_handler(
        self, query_type: Type[Any], handler: QueryHandler
    ) -> None:
        """
        Register a query handler instance for a query type.
        """
        self._query_handlers[query_type] = handler

    async def send(self, command: Command[R]) -> R:
        """
        Dispatch a Command mutation to its registered CommandHandler.
        """
        cmd_type = type(command)
        handler = self._command_handlers.get(cmd_type)
        if not handler:
            raise KeyError(
                f"No CommandHandler registered for '{cmd_type.__name__}'"
            )
        return await handler.handle(command)

    async def query(self, query: Query[R]) -> R:
        """
        Dispatch a Query read request to its registered QueryHandler.
        """
        query_type = type(query)
        handler = self._query_handlers.get(query_type)
        if not handler:
            raise KeyError(
                f"No QueryHandler registered for '{query_type.__name__}'"
            )
        return await handler.handle(query)
