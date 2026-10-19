"""
RealTimeTransfer
================

Database Query Specification

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

ModelT = TypeVar("ModelT")


class Specification(ABC, Generic[ModelT]):
    """
    Base class for implementing Query Specifications.
    """

    __slots__ = ()

    @abstractmethod
    def apply(self, query: Any) -> Any:
        """
        Apply specification logic to a query statement.
        """
