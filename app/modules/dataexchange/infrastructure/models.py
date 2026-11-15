"""
Excel Job Database Model

One row per Excel import / export. The API inserts QUEUED rows; the exchange
worker process claims them, reports progress and heartbeats, and finishes them.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import (
    AuditMixin,
    TimestampMixin,
    UUIDMixin,
)
from app.core.database.types import NaiveDateTime
from app.modules.dataexchange.domain.enums import (
    ExcelJobKind,
    ExcelJobStatus,
    ImportMode,
)


class ExcelJobModel(Base, UUIDMixin, TimestampMixin):

    __tablename__ = "excel_jobs"

    __table_args__ = (
        Index("ix_excel_jobs_user_kind_status", "created_by", "kind", "status"),
        Index("ix_excel_jobs_status_created", "status", "created_at"),
    )

    # =========================================================
    # Job Definition
    # =========================================================

    kind: Mapped[ExcelJobKind] = mapped_column(
        Enum(ExcelJobKind),
        nullable=False,
    )

    status: Mapped[ExcelJobStatus] = mapped_column(
        Enum(ExcelJobStatus),
        nullable=False,
        default=ExcelJobStatus.QUEUED,
    )

    mode: Mapped[ImportMode | None] = mapped_column(
        Enum(ImportMode),
        nullable=True,
    )

    dry_run: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # =========================================================
    # Requesting User & Target
    # =========================================================

    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner_role: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    owner_own_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    target_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    # =========================================================
    # Files (names relative to the job folder)
    # =========================================================

    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)

    result_file: Mapped[str | None] = mapped_column(String(255), nullable=True)

    report_file: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # =========================================================
    # Progress
    # =========================================================

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    discarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # =========================================================
    # Worker Lifecycle
    # =========================================================

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    worker_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    heartbeat_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)

    finished_at: Mapped[datetime | None] = mapped_column(
        NaiveDateTime(),
        nullable=True,
        index=True,
    )


class ExcelColumnLayoutModel(Base, UUIDMixin, AuditMixin):
    """
    A user's export column order and visibility (REQ-55, DECISION-030).

    No row = the default layout, so nothing is written when a user is created.
    `columns` is read whole and normalised in Python; it is never queried inside.
    """

    __tablename__ = "excel_column_layouts"

    __table_args__ = (
        UniqueConstraint("user_id", "sheet", name="uq_excel_column_layouts_user_sheet"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sheet: Mapped[str] = mapped_column(String(40), nullable=False)

    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)    # [{"key", "visible"}]
