"""
SQLAlchemy ORM Base

Enterprise Database Foundation

Python 3.13+
SQLAlchemy 2.x
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import (DeclarativeBase,declared_attr)

from app.core.database.metadata import metadata
from app.core.database.types import NaiveDateTime


__all__ = (
    "Base",
)


class Base(DeclarativeBase):
    """
    Global ORM Base.

    All database models must inherit from this class.
    """

    metadata = metadata

    # `Mapped[datetime]` without an explicit type is naive IST too (DECISION-025)
    type_annotation_map = {
        datetime: NaiveDateTime(),
    }


    # ---------------------------------------------------------
    # Automatic table naming
    # ---------------------------------------------------------

    @declared_attr.directive
    def __tablename__(
        cls,
    ) -> str:
        """
        Automatically generate table names.

        Example:

        UserModel
            ->
        user_models
        """

        name = cls.__name__

        result: list[str] = []


        for index, char in enumerate(name):

            if char.isupper() and index > 0:

                result.append("_")

            result.append(char.lower())


        return "".join(result)


    # ---------------------------------------------------------
    # Debug Representation
    # ---------------------------------------------------------

    def __repr__(self) -> str:

        values: dict[str, Any] = {}

        for column in self.__table__.columns:

            values[column.name] = getattr(
                self,
                column.name,
                None,
            )


        return (
            f"{self.__class__.__name__}("
            f"{values}"
            ")"
        )