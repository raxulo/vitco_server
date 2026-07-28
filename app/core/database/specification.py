"""
RealTimeTransfer
================

Enterprise Specification Pattern for Database Querying

Encapsulates query criteria and business rules away from repository infrastructure.

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from sqlalchemy.sql.selectable import Select

ModelT = TypeVar("ModelT")


class Specification(ABC, Generic[ModelT]):
    """
    Abstract Specification base class.
    """

    @abstractmethod
    def apply(self, statement: Select) -> Select:
        """
        Apply criteria to the SQLAlchemy select statement.
        """

    def __and__(self, other: Specification[ModelT]) -> Specification[ModelT]:
        return AndSpecification(self, other)

    def __or__(self, other: Specification[ModelT]) -> Specification[ModelT]:
        return OrSpecification(self, other)

    def __invert__(self) -> Specification[ModelT]:
        return NotSpecification(self)


class AndSpecification(Specification[ModelT]):
    """
    Combines two specifications with logical AND.
    """

    __slots__ = ("_left", "_right")

    def __init__(
        self, left: Specification[ModelT], right: Specification[ModelT]
    ) -> None:
        self._left = left
        self._right = right

    def apply(self, statement: Select) -> Select:
        return self._right.apply(self._left.apply(statement))


class OrSpecification(Specification[ModelT]):
    """
    Combines two specifications with logical OR via UNION.
    """

    __slots__ = ("_left", "_right")

    def __init__(
        self, left: Specification[ModelT], right: Specification[ModelT]
    ) -> None:
        self._left = left
        self._right = right

    def apply(self, statement: Select) -> Select:
        return self._left.apply(statement).union(self._right.apply(statement))


class NotSpecification(Specification[ModelT]):
    """
    Inverts a specification logic.
    """

    __slots__ = ("_spec",)

    def __init__(self, spec: Specification[ModelT]) -> None:
        self._spec = spec

    def apply(self, statement: Select) -> Select:
        return self._spec.apply(statement)
