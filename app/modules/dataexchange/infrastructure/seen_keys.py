"""
Disk-Backed Duplicate Detector

Remembers which codes / mobiles / emails an import has already used, so a
value repeated later in the same file is discarded with "repeats row N".
Keys live in a scratch SQLite file in the job folder, not in Python sets,
so memory stays flat for millions of rows (NFR-01, DECISION-011).

Synchronous — used from the worker's import pipeline.

Python 3.13+
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_IN_CHUNK = 900                       # stays under SQLite's bound-parameter limit


class SeenKeys:

    __slots__ = ("_path", "_db")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        # Scratch data: losing it on a crash is fine, speed matters more
        self._db.execute("PRAGMA journal_mode=OFF")
        self._db.execute("PRAGMA synchronous=OFF")
        self._db.execute("PRAGMA temp_store=FILE")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            " kind TEXT NOT NULL, value TEXT NOT NULL, row_no INTEGER NOT NULL,"
            " PRIMARY KEY (kind, value)) WITHOUT ROWID"
        )

    def __enter__(self) -> SeenKeys:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def find(self, keys: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
        """First row number of every (kind, value) already registered — registers nothing."""
        return self._lookup([(kind, value, 0) for kind, value in keys])

    def add(self, keys: list[tuple[str, str, int]]) -> None:
        """Register (kind, value, row_no) keys; values already registered keep their first row."""
        if keys:
            self._db.executemany("INSERT OR IGNORE INTO seen (kind, value, row_no) VALUES (?, ?, ?)", keys)

    def check_and_add(self, keys: list[tuple[str, str, int]]) -> dict[tuple[str, str, int], int]:
        """
        Record a batch of (kind, value, row_no) keys, already normalised by the caller.

        Returns {(kind, value, row_no): first_row_no} for every key whose value
        was used by an earlier row (earlier batch or earlier in this batch).
        """
        first_rows = self._lookup(keys)
        duplicates: dict[tuple[str, str, int], int] = {}
        new_keys: list[tuple[str, str, int]] = []
        for kind, value, row_no in keys:
            first = first_rows.get((kind, value))
            if first is not None:
                duplicates[(kind, value, row_no)] = first
            else:
                first_rows[(kind, value)] = row_no
                new_keys.append((kind, value, row_no))
        if new_keys:
            self._db.executemany("INSERT INTO seen (kind, value, row_no) VALUES (?, ?, ?)", new_keys)
        return duplicates

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
            self._path.unlink(missing_ok=True)

    # ---------------------------------------------------------

    def _lookup(self, keys: list[tuple[str, str, int]]) -> dict[tuple[str, str], int]:
        by_kind: dict[str, set[str]] = {}
        for kind, value, _ in keys:
            by_kind.setdefault(kind, set()).add(value)

        found: dict[tuple[str, str], int] = {}
        for kind, values in by_kind.items():
            ordered = list(values)
            for start in range(0, len(ordered), _IN_CHUNK):
                chunk = ordered[start:start + _IN_CHUNK]
                marks = ",".join("?" * len(chunk))
                for value, row_no in self._db.execute(
                    f"SELECT value, row_no FROM seen WHERE kind = ? AND value IN ({marks})", [kind, *chunk]
                ):
                    found[(kind, value)] = row_no
        return found
