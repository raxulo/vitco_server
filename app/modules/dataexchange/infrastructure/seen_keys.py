"""
Disk-Backed Duplicate Detector

Remembers which codes / mobiles / emails an import has already used, so a
value repeated later in the same file is discarded with "repeats row N".
Keys live in a scratch hash table file in the job folder, not in Python sets,
so memory stays flat for millions of rows (NFR-01, DECISION-011).

The table is a plain file (open addressing over mmap), so a server running on
PostgreSQL needs no sqlite3 module. Each (kind, value) is kept as a 128-bit
BLAKE2b digest: two different values would need around 2^64 keys to share one.

Synchronous — used from the worker's import pipeline.

Python 3.13+
"""

from __future__ import annotations

import hashlib
import mmap
import struct
from pathlib import Path

# One slot: digest of (kind, value) + first row number. An all-zero digest marks an empty slot.
_SLOT = struct.Struct("<16sI")
_EMPTY = bytes(16)
_INITIAL_SLOTS = 1 << 16              # 1.3 MB file; doubles whenever it gets half full


def _digest(kind: str, value: str) -> bytes:
    return hashlib.blake2b(f"{kind}\x00{value}".encode("utf-8"), digest_size=16).digest()


class SeenKeys:

    __slots__ = ("_path", "_file", "_map", "_slots", "_count")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._count = 0
        self._file, self._map = _create(path, _INITIAL_SLOTS)
        self._slots = _INITIAL_SLOTS

    def __enter__(self) -> SeenKeys:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def find(self, keys: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
        """First row number of every (kind, value) already registered — registers nothing."""
        found: dict[tuple[str, str], int] = {}
        for kind, value in keys:
            _, row_no = self._locate(_digest(kind, value))
            if row_no is not None:
                found[(kind, value)] = row_no
        return found

    def add(self, keys: list[tuple[str, str, int]]) -> None:
        """Register (kind, value, row_no) keys; values already registered keep their first row."""
        for kind, value, row_no in keys:
            digest = _digest(kind, value)
            offset, existing = self._locate(digest)
            if existing is None:
                self._insert(offset, digest, row_no)

    def check_and_add(self, keys: list[tuple[str, str, int]]) -> dict[tuple[str, str, int], int]:
        """
        Record a batch of (kind, value, row_no) keys, already normalised by the caller.

        Returns {(kind, value, row_no): first_row_no} for every key whose value
        was used by an earlier row (earlier batch or earlier in this batch).
        """
        duplicates: dict[tuple[str, str, int], int] = {}
        for kind, value, row_no in keys:
            digest = _digest(kind, value)
            offset, first = self._locate(digest)
            if first is not None:
                duplicates[(kind, value, row_no)] = first
            else:
                self._insert(offset, digest, row_no)
        return duplicates

    def close(self) -> None:
        if self._map is not None:
            self._map.close()
            self._file.close()
            self._map = None
            self._file = None
            self._path.unlink(missing_ok=True)

    # ---------------------------------------------------------

    def _locate(self, digest: bytes) -> tuple[int, int | None]:
        """Byte offset of the digest's slot (or of the empty slot it would take) and its row number."""
        table = self._map
        mask = self._slots - 1
        index = int.from_bytes(digest[:8], "little") & mask
        while True:
            offset = index * _SLOT.size
            stored = table[offset:offset + 16]
            if stored == _EMPTY:
                return offset, None
            if stored == digest:
                return offset, _SLOT.unpack_from(table, offset)[1]
            index = (index + 1) & mask

    def _insert(self, offset: int, digest: bytes, row_no: int) -> None:
        _SLOT.pack_into(self._map, offset, digest, row_no)
        self._count += 1
        if self._count * 2 > self._slots:
            self._grow()

    def _grow(self) -> None:
        old_file, old_map, old_slots = self._file, self._map, self._slots
        spare = self._path.with_name(self._path.name + ".grow")
        self._file, self._map = _create(spare, old_slots * 2)
        self._slots = old_slots * 2
        for offset in range(0, old_slots * _SLOT.size, _SLOT.size):
            digest = old_map[offset:offset + 16]
            if digest != _EMPTY:
                new_offset, _ = self._locate(digest)
                self._map[new_offset:new_offset + _SLOT.size] = old_map[offset:offset + _SLOT.size]
        old_map.close()
        old_file.close()

        # Keep the table at `path`: Windows can't replace a file that is still open
        self._map.flush()
        self._map.close()
        self._file.close()
        spare.replace(self._path)
        self._file = open(self._path, "r+b")
        self._map = mmap.mmap(self._file.fileno(), 0)


def _create(path: Path, slots: int):
    file = open(path, "w+b")
    file.truncate(slots * _SLOT.size)          # sparse zeros = every slot empty
    return file, mmap.mmap(file.fileno(), 0)
