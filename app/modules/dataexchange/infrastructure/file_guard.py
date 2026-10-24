"""
Hostile File Guard

Inspects an uploaded .xlsx before anything parses it. Only the zip directory
and the first 64 KB of a few XML parts are read — nothing is extracted — so a
zip bomb is rejected without being inflated (NFR-09).

Python 3.13+
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from app.modules.dataexchange.domain.exceptions import InvalidExcelFileException

_ZIP_MAGIC = b"PK\x03\x04"
_SCAN_BYTES = 64 * 1024
_RATIO_MIN_SIZE = 1024 * 1024          # small parts compress extremely well and are harmless
_DECLARATION = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_SCANNED_PARTS = re.compile(r"xl/(workbook\.xml|sharedStrings\.xml|worksheets/[^/]+\.xml)")


class FileGuard:

    __slots__ = ("_max_uncompressed_bytes", "_max_ratio", "_max_members")

    def __init__(
        self,
        *,
        max_uncompressed_bytes: int,
        max_ratio: int = 100,
        max_members: int = 10_000,
    ) -> None:
        self._max_uncompressed_bytes = max_uncompressed_bytes
        self._max_ratio = max_ratio
        self._max_members = max_members

    def inspect(self, path: Path) -> None:
        """Raise InvalidExcelFileException unless `path` looks like a safe .xlsx workbook."""
        with open(path, "rb") as handle:
            if handle.read(4) != _ZIP_MAGIC:
                raise InvalidExcelFileException("Not an .xlsx file. Please upload an Excel workbook.")

        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                self._check_directory(members)
                self._check_declarations(archive, members)
        except zipfile.BadZipFile as error:
            raise InvalidExcelFileException(f"The file is damaged ({error}).") from None

    # ---------------------------------------------------------

    def _check_directory(self, members: list[zipfile.ZipInfo]) -> None:
        if len(members) > self._max_members:
            raise InvalidExcelFileException("The file contains too many parts to be an Excel workbook.")

        names = set()
        total = 0
        for info in members:
            name = info.filename
            if name.startswith(("/", "\\")) or ".." in name.split("/") or ":" in name:
                raise InvalidExcelFileException("The file contains an unsafe path.")
            if info.flag_bits & 0x1:
                raise InvalidExcelFileException("Password-protected workbooks are not supported.")
            total += info.file_size
            if total > self._max_uncompressed_bytes:
                raise InvalidExcelFileException("The file is too large once uncompressed.")
            if info.file_size > _RATIO_MIN_SIZE and info.file_size / max(info.compress_size, 1) > self._max_ratio:
                raise InvalidExcelFileException("The file is compressed suspiciously well and was rejected.")
            names.add(name)

        if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
            raise InvalidExcelFileException("Not an Excel workbook. Please upload an .xlsx file.")

    def _check_declarations(self, archive: zipfile.ZipFile, members: list[zipfile.ZipInfo]) -> None:
        for info in members:
            if not _SCANNED_PARTS.fullmatch(info.filename):
                continue
            with archive.open(info) as part:
                head = part.read(_SCAN_BYTES)
            if _DECLARATION.search(head):
                raise InvalidExcelFileException("The file contains XML declarations that are not allowed.")
