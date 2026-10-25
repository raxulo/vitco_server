"""
Excel Import / Export API Schemas

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.dataexchange.application.dto import ExcelJobDto
from app.modules.dataexchange.application.uploads import UploadStatus


class EnumValue(BaseModel):
    """Enums are sent as number + name so apps never hard-code the numbers."""

    value: int
    name: str

    @classmethod
    def of(cls, item: IntEnum | None) -> EnumValue | None:
        return None if item is None else cls(value=int(item), name=item.name)


class ExcelJobResponse(BaseModel):

    id: UUID
    kind: EnumValue
    status: EnumValue
    mode: EnumValue | None
    dry_run: bool
    target_id: UUID | None
    total_rows: int
    processed_rows: int
    inserted: int
    updated: int
    discarded: int
    unchanged: int = Field(description="Imports: matched rows whose values were already the same")
    progress: int = Field(description="0 - 100")
    rows_per_second: float | None
    eta_seconds: int | None
    poll_after_ms: int | None = Field(description="Wait this long before polling again; null once finished")
    has_file: bool
    file_name: str | None
    error_message: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_dto(cls, dto: ExcelJobDto) -> ExcelJobResponse:
        return cls(
            id=dto.id,
            kind=EnumValue.of(dto.kind),
            status=EnumValue.of(dto.status),
            mode=EnumValue.of(dto.mode),
            dry_run=dto.dry_run,
            target_id=dto.target_id,
            total_rows=dto.total_rows,
            processed_rows=dto.processed_rows,
            inserted=dto.inserted,
            updated=dto.updated,
            discarded=dto.discarded,
            unchanged=dto.unchanged,
            progress=dto.progress,
            rows_per_second=dto.rows_per_second,
            eta_seconds=dto.eta_seconds,
            poll_after_ms=dto.poll_after_ms,
            has_file=dto.has_file,
            file_name=dto.file_name,
            error_message=dto.error_message,
            created_at=dto.created_at,
            started_at=dto.started_at,
            finished_at=dto.finished_at,
        )


class FarmerExportRequest(BaseModel):

    vlcc_id: UUID | None = Field(None, description="Ignored for a VLCC login (always its own VLCC)")


class FarmerImportRequest(BaseModel):

    upload_id: UUID = Field(description="A completed upload from /excel/uploads")
    vlcc_id: UUID | None = Field(None, description="Ignored for a VLCC login (always its own VLCC)")
    mode: Literal["UPSERT", "CREATE_ONLY"] = "UPSERT"
    dry_run: bool = Field(False, description="Validate only; nothing is saved")


class VlccOptionResponse(BaseModel):

    id: UUID
    code: str
    name: str


class CreateUploadRequest(BaseModel):

    file_name: str = Field(min_length=6, max_length=200, examples=["farmers.xlsx"])
    size: int = Field(gt=0, description="Total file size in bytes")
    sha256: str = Field(min_length=64, max_length=64, description="Hex SHA-256 of the whole file")


class UploadResponse(BaseModel):

    id: UUID
    file_name: str
    size: int
    chunk_size: int
    total_chunks: int
    received: list[int]
    missing: list[int]
    completed: bool

    @classmethod
    def from_status(cls, status: UploadStatus) -> UploadResponse:
        return cls(
            id=status.id,
            file_name=status.file_name,
            size=status.size,
            chunk_size=status.chunk_size,
            total_chunks=status.total_chunks,
            received=status.received,
            missing=status.missing,
            completed=status.completed,
        )
