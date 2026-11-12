"""
Exchange File Storage

Job and upload folders on local disk. Every write is streamed with a byte
limit and lands atomically (`.part` file renamed on success), so a partial
or oversized file never looks complete. Free disk space is checked before
work starts.

Python 3.13+
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

import aiofiles

from app.modules.dataexchange.domain.exceptions import (
    ExcelFileTooLargeException,
    ExcelStorageFullException,
)

_READ_SIZE = 1 << 20          # 1 MB
_SAFE_NAME = re.compile(r"[A-Za-z0-9._-]{1,128}")
_PARAMS_FILE = "params.json"  # a job's options beyond its target, e.g. list filters (DECISION-028)


class AsyncReadable(Protocol):
    """What we need from an upload (Starlette's UploadFile satisfies it)."""

    async def read(self, size: int = -1) -> bytes: ...


class ExchangeStorage:

    __slots__ = ("_root", "_max_upload_bytes", "_min_free_bytes")

    def __init__(self, root: Path, *, max_upload_bytes: int, min_free_bytes: int) -> None:
        self._root = Path(root)
        self._max_upload_bytes = max_upload_bytes
        self._min_free_bytes = min_free_bytes

    @property
    def root(self) -> Path:
        return self._root

    @property
    def max_upload_bytes(self) -> int:
        return self._max_upload_bytes

    # =========================================================
    # FOLDERS
    # =========================================================

    def job_dir(self, job_id: UUID) -> Path:
        return self._folder("jobs", job_id)

    def upload_dir(self, upload_id: UUID) -> Path:
        return self._folder("uploads", upload_id)

    def path(self, base_dir: Path, name: str) -> Path:
        """`base_dir / name` for a plain file name; anything path-like is refused on every OS."""
        if not _SAFE_NAME.fullmatch(name or "") or name in (".", ".."):
            raise ValueError(f"Unsafe file name: {name!r}")
        base = Path(base_dir).resolve()
        candidate = (base / name).resolve()
        if candidate == base or not candidate.is_relative_to(base):
            raise ValueError(f"Unsafe file name: {name!r}")
        return candidate

    def delete_dir(self, path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)

    # =========================================================
    # JOB PARAMETERS
    # =========================================================

    def write_params(self, job_dir: Path, params: dict[str, Any]) -> None:
        """Store a job's parameters next to its files; written whole or not at all."""
        dest = self.path(job_dir, _PARAMS_FILE)
        partial = dest.with_name(f"{dest.name}.part")
        partial.write_text(json.dumps(params), encoding="utf-8")
        os.replace(partial, dest)

    def read_params(self, job_dir: Path) -> dict[str, Any]:
        """A job's parameters; empty when it has none."""
        source = self.path(job_dir, _PARAMS_FILE)
        if not source.exists():
            return {}
        return json.loads(source.read_text(encoding="utf-8"))

    @staticmethod
    def folder_size(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())

    # =========================================================
    # DISK GUARD
    # =========================================================

    def ensure_free_space(self, expected_bytes: int) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self._root).free
        if free < self._min_free_bytes + max(expected_bytes, 0):
            raise ExcelStorageFullException()

    # =========================================================
    # STREAMED WRITES
    # =========================================================

    async def write_stream(self, dest: Path, chunks: AsyncIterator[bytes], *, limit: int) -> int:
        """Write `chunks` to `dest`; raise as soon as more than `limit` bytes arrive."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(f"{dest.name}.part")
        written = 0
        try:
            async with aiofiles.open(partial, "wb") as handle:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > limit:
                        raise ExcelFileTooLargeException()
                    await handle.write(chunk)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        os.replace(partial, dest)
        return written

    async def save_upload_file(self, dest: Path, upload: AsyncReadable, *, limit: int | None = None) -> int:
        async def chunks() -> AsyncIterator[bytes]:
            while chunk := await upload.read(_READ_SIZE):
                yield chunk

        return await self.write_stream(dest, chunks(), limit=limit or self._max_upload_bytes)

    # ---------------------------------------------------------

    def _folder(self, kind: str, item_id: UUID) -> Path:
        folder = self._root / kind / str(UUID(str(item_id)))
        folder.mkdir(parents=True, exist_ok=True)
        return folder
