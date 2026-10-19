"""
SQLAlchemy Common Mixins

Enterprise Database Layer

Python 3.13+
SQLAlchemy 2.x
"""

from __future__ import annotations

import uuid

from datetime import datetime

from app.core.clock import get_ist_now

from sqlalchemy import (
    Boolean,
    DateTime,
    func,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)


__all__ = (
    "UUIDMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
)


# ============================================================
# UUID Mixin
# ============================================================


class UUIDMixin:
    """
    Universal UUID identifier.

    Useful for:
    - Public APIs
    - Distributed systems
    - External references
    """

    __abstract__ = True


    id: Mapped[uuid.UUID] = mapped_column(

        UUID(as_uuid=True),

        primary_key=True,

        default=uuid.uuid4,

        nullable=False,

    )


# ============================================================
# Timestamp Mixin
# ============================================================


class TimestampMixin:
    """
    Created / Updated timestamps.
    """

    __abstract__ = True


    created_at: Mapped[datetime] = mapped_column(
        DateTime(
            timezone=True
        ),
        server_default=func.now(),
        default=get_ist_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(
            timezone=True
        ),
        server_default=func.now(),
        default=get_ist_now,
        onupdate=get_ist_now,
        nullable=False,
    )


# ============================================================
# Soft Delete
# ============================================================


class SoftDeleteMixin:
    """
    Soft delete support.

    Data physically remove nahi hota.
    """

    __abstract__ = True


    deleted_at: Mapped[datetime | None] = mapped_column(

        DateTime(
            timezone=True
        ),

        nullable=True,

    )


    is_deleted: Mapped[bool] = mapped_column(

        Boolean,

        default=False,

        nullable=False,

    )

    deleted_by: Mapped[uuid.UUID | None] = mapped_column( 
        UUID(as_uuid=True), nullable=True,
    )

    


# ============================================================
# Audit
# ============================================================


class AuditMixin(
    TimestampMixin,
):
    """
    Common audit information.
    """

    __abstract__ = True


    created_by: Mapped[uuid.UUID | None] = mapped_column(

        UUID(as_uuid=True),

        nullable=True,

    )


    updated_by: Mapped[uuid.UUID | None] = mapped_column(

        UUID(as_uuid=True),

        nullable=True,

    )