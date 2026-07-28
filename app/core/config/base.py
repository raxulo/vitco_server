"""
RealTimeTransfer
================

Base Configuration

Python 3.13+
"""

from __future__ import annotations

from abc import ABC
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(
    slots=True,
    frozen=True,
    kw_only=True,
)
class BaseConfig(ABC):
    """
    Base class for every configuration section.

    Responsibilities
    ----------------

    • Immutable

    • Type Safe

    • Serializable

    • Environment Friendly

    • Validation Ready
    """

    def dict(self) -> dict[str, Any]:
        """
        Return configuration as dictionary.
        """

        return asdict(self)

    def copy(
        self,
        **changes: Any,
    ):
        """
        Create modified copy.
        """

        values = self.dict()

        values.update(changes)

        return self.__class__(**values)

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Dictionary style access.
        """

        return self.dict().get(
            key,
            default,
        )

    def __getitem__(
        self,
        key: str,
    ) -> Any:

        return self.dict()[key]

    def __contains__(
        self,
        key: str,
    ) -> bool:

        return key in self.dict()


@dataclass(
    slots=True,
    frozen=True,
)
class Paths:
    """
    Project directories.
    """

    root: Path

    app: Path

    logs: Path

    storage: Path

    temp: Path

    uploads: Path

    downloads: Path

    certificates: Path