"""
Excel Job Database Model

One row per Excel import / export. The API inserts QUEUED rows; the exchange
worker process claims them, reports progress and heartbeats, and finishes them.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)
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

    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )
