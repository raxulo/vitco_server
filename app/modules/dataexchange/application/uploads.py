"""
Excel Upload Service

Resumable chunked uploads for the web panel and the mobile app (DECISION-009):

    create(size, sha256) -> put_chunk(n) ... (any order, re-sendable) -> complete()

Uploads never touch the database: session metadata is a small JSON file in the
upload folder, written atomically. So an upload request never holds a DB
connection while bytes are on the wire (NFR-13), and a dropped mobile network
only costs the chunk that was in flight.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.modules.dataexchange.domain.exceptions import (
    ExcelFileTooLargeException,
    ExcelUploadIncompleteException,
    ExcelUploadNotFoundException,
    InvalidExcelFileException,
)
from app.modules.dataexchange.infrastructure.file_guard import FileGuard
from app.modules.dataexchange.infrastructure.storage import AsyncReadable, ExchangeStorage

_META = "upload.json"
_SOURCE = "source.xlsx"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_BLOCK = 1 << 20


@dataclass(slots=True, kw_only=True)
class UploadStatus:

    id: UUID
    file_name: str
    size: int
    chunk_size: int
    total_chunks: int
    received: list[int] = field(default_factory=list)
    missing: list[int] = field(default_factory=list)
    completed: bool = False


class ExcelUploadService:

    __slots__ = ("_storage", "_guard", "_chunk_size", "_single_limit")

    def __init__(
        self,
        *,
        storage: ExchangeStorage,
        guard: FileGuard,
        chunk_size: int,
        single_limit: int = 10 * 1024 * 1024,
    ) -> None:
        self._storage = storage
        self._guard = guard
        self._chunk_size = chunk_size
        self._single_limit = single_limit

    # =========================================================
    # CHUNKED
    # =========================================================

    def create(self, owner: CurrentUser, *, file_name: str, size: int, sha256: str) -> UploadStatus:
        file_name = _clean_name(file_name)
        sha256 = (sha256 or "").strip().lower()
        if not _SHA256.fullmatch(sha256):
            raise InvalidExcelFileException("sha256 must be the 64-character hex digest of the file.")
        if size <= 0:
            raise InvalidExcelFileException("The file is empty.")
        if size > self._storage.max_upload_bytes:
            raise ExcelFileTooLargeException(
                f"The file is larger than {self._storage.max_upload_bytes // (1024 * 1024)} MB."
            )
        self._storage.ensure_free_space(size * 2)            # chunks + the joined file

        upload_id = uuid4()
        meta = {
            "id": str(upload_id),
            "owner_id": str(owner.id),
            "file_name": file_name,
            "size": size,
            "sha256": sha256,
            "chunk_size": self._chunk_size,
            "total_chunks": -(-size // self._chunk_size),
            "completed": False,
            "created_at": now_naive_ist().isoformat(),
        }
        self._write_meta(self._storage.upload_dir(upload_id), meta)
        return self._status(upload_id, meta)

    async def put_chunk(self, owner: CurrentUser, upload_id: UUID, index: int, chunks: AsyncIterator[bytes]) -> UploadStatus:
        folder, meta = self._session(owner, upload_id)
        if meta["completed"]:
            return self._status(upload_id, meta)
        total = meta["total_chunks"]
        if not 0 <= index < total:
            raise InvalidExcelFileException(f"Chunk index must be between 0 and {total - 1}.")
        expected = meta["chunk_size"] if index < total - 1 else meta["size"] - meta["chunk_size"] * (total - 1)

        dest = self._storage.path(folder, _chunk_name(index))
        written = await self._storage.write_stream(dest, chunks, limit=expected)
        if written != expected:
            dest.unlink(missing_ok=True)
            raise InvalidExcelFileException(f"Chunk {index} must be exactly {expected} bytes (got {written}).")
        return self._status(upload_id, meta)

    def status(self, owner: CurrentUser, upload_id: UUID) -> UploadStatus:
        _, meta = self._session(owner, upload_id)
        return self._status(upload_id, meta)

    async def complete(self, owner: CurrentUser, upload_id: UUID) -> UploadStatus:
        folder, meta = self._session(owner, upload_id)
        if meta["completed"]:
            return self._status(upload_id, meta)
        state = self._status(upload_id, meta)
        if state.missing:
            raise ExcelUploadIncompleteException(f"{len(state.missing)} chunk(s) still missing.")

        # Joining hundreds of MB is blocking file IO: keep it off the event loop
        await asyncio.to_thread(self._join, folder, meta)
        source = self._storage.path(folder, _SOURCE)
        try:
            await asyncio.to_thread(self._guard.inspect, source)
        except BaseException:
            source.unlink(missing_ok=True)
            raise
        meta["completed"] = True
        self._write_meta(folder, meta)
        return self._status(upload_id, meta)

    # =========================================================
    # SINGLE REQUEST (small files)
    # =========================================================

    async def save_single(self, owner: CurrentUser, upload: AsyncReadable, file_name: str) -> UploadStatus:
        file_name = _clean_name(file_name)
        upload_id = uuid4()
        folder = self._storage.upload_dir(upload_id)
        try:
            limit = min(self._single_limit, self._storage.max_upload_bytes)
            source = self._storage.path(folder, _SOURCE)
            size = await self._storage.save_upload_file(source, upload, limit=limit)
            await asyncio.to_thread(self._guard.inspect, source)
        except BaseException:
            self._storage.delete_dir(folder)
            raise
        meta = {
            "id": str(upload_id), "owner_id": str(owner.id), "file_name": file_name, "size": size,
            "sha256": "", "chunk_size": size, "total_chunks": 1, "completed": True,
            "created_at": now_naive_ist().isoformat(),
        }
        self._write_meta(folder, meta)
        return self._status(upload_id, meta)

    # =========================================================
    # HAND-OVER TO A JOB
    # =========================================================

    def take(self, owner: CurrentUser, upload_id: UUID) -> Path:
        """Path of a completed upload owned by `owner` (moved into the job folder by the job handler)."""
        folder, meta = self._session(owner, upload_id)
        if not meta["completed"]:
            raise ExcelUploadIncompleteException()
        source = self._storage.path(folder, _SOURCE)
        if not source.is_file():
            raise ExcelUploadNotFoundException()
        return source

    def discard(self, upload_id: UUID) -> None:
        self._storage.delete_dir(self._storage.root / "uploads" / str(UUID(str(upload_id))))

    # =========================================================
    # HELPERS
    # =========================================================

    def _session(self, owner: CurrentUser, upload_id: UUID) -> tuple[Path, dict]:
        folder = self._storage.root / "uploads" / str(UUID(str(upload_id)))
        try:
            meta = json.loads((folder / _META).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ExcelUploadNotFoundException() from None
        if meta.get("owner_id") != str(owner.id):
            raise ExcelUploadNotFoundException()            # another user's upload looks missing
        return folder, meta

    def _status(self, upload_id: UUID, meta: dict) -> UploadStatus:
        total = meta["total_chunks"]
        if meta["completed"]:
            received, missing = list(range(total)), []
        else:
            folder = self._storage.root / "uploads" / str(upload_id)
            present = {index for index in range(total) if (folder / _chunk_name(index)).is_file()}
            received = sorted(present)
            missing = [index for index in range(total) if index not in present]
        return UploadStatus(
            id=upload_id,
            file_name=meta["file_name"],
            size=meta["size"],
            chunk_size=meta["chunk_size"],
            total_chunks=total,
            received=received,
            missing=missing,
            completed=meta["completed"],
        )

    def _join(self, folder: Path, meta: dict) -> None:
        digest = hashlib.sha256()
        target = self._storage.path(folder, _SOURCE)
        partial = target.with_name(f"{_SOURCE}.part")
        size = 0
        try:
            with open(partial, "wb") as out:
                for index in range(meta["total_chunks"]):
                    with open(self._storage.path(folder, _chunk_name(index)), "rb") as chunk:
                        while block := chunk.read(_BLOCK):
                            digest.update(block)
                            size += len(block)
                            out.write(block)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        if size != meta["size"] or digest.hexdigest() != meta["sha256"]:
            partial.unlink(missing_ok=True)
            raise InvalidExcelFileException("Checksum mismatch: the uploaded file is not the one announced. Please upload it again.")
        os.replace(partial, target)
        for index in range(meta["total_chunks"]):
            self._storage.path(folder, _chunk_name(index)).unlink(missing_ok=True)

    def _write_meta(self, folder: Path, meta: dict) -> None:
        temp = folder / f"{_META}.tmp"
        temp.write_text(json.dumps(meta), encoding="utf-8")
        os.replace(temp, folder / _META)


def _chunk_name(index: int) -> str:
    return f"chunk_{index:06d}"


def _clean_name(file_name: str) -> str:
    name = Path((file_name or "").replace("\\", "/")).name.strip()
    if not name.lower().endswith(".xlsx"):
        raise InvalidExcelFileException("Only .xlsx Excel files can be uploaded.")
    return name[:200]


__all__ = ("ExcelUploadService", "UploadStatus")
