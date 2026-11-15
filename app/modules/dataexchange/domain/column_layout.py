"""
Collection Column Layout (REQ-55, DECISION-030)

A user's order and visibility of the collection export columns. One layout covers
both the MCC and the VLCC export: each sheet takes the visible keys in order and
skips the columns it does not have.

Stored layouts are normalised on every read, so the catalogue may grow or shrink
without a data migration: unknown or repeated keys are dropped, and a catalogue
column the layout does not know yet is put back, visible, right after the column
that precedes it in the default order.

Pure Python: no framework, no database.

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.dataexchange.domain.columns import ColumnSpec
from app.modules.dataexchange.domain.exceptions import ColumnLayoutInvalidException
from app.modules.dataexchange.domain.sheets import (
    COLLECTION_COLUMN_KEYS,
    CollectionSheet,
    collection_columns,
)

COLLECTION_LAYOUT = "collections"          # the `sheet` value of a collection layout row


@dataclass(slots=True, frozen=True)
class LayoutUser:
    """The user whose layout is read or changed."""

    id: UUID
    name: str
    role: int


@dataclass(slots=True, frozen=True)
class ColumnLayoutItem:

    key: str
    visible: bool = True

    def to_json(self) -> dict[str, Any]:
        return {"key": self.key, "visible": self.visible}


@dataclass(slots=True, frozen=True)
class ColumnLayout:

    items: tuple[ColumnLayoutItem, ...]
    is_default: bool = False

    # ---------------------------------------------------------
    # BUILD
    # ---------------------------------------------------------

    @classmethod
    def default(cls) -> ColumnLayout:
        return cls(items=tuple(ColumnLayoutItem(key) for key in COLLECTION_COLUMN_KEYS), is_default=True)

    @classmethod
    def normalise(cls, stored: Iterable[Mapping[str, Any]] | None) -> ColumnLayout:
        """A stored layout made complete and valid for today's catalogue (None = the default)."""
        if stored is None:
            return cls.default()
        known = set(COLLECTION_COLUMN_KEYS)
        items: list[ColumnLayoutItem] = []
        seen: set[str] = set()
        for entry in stored:
            if not isinstance(entry, Mapping):
                continue
            key = entry.get("key")
            if key not in known or key in seen:
                continue
            seen.add(key)
            items.append(ColumnLayoutItem(key, bool(entry.get("visible", True))))
        _insert_missing(items, seen)
        return cls(items=tuple(items))

    @classmethod
    def from_request(cls, entries: Iterable[tuple[str, bool]]) -> ColumnLayout:
        """
        A layout sent by a user: every key must be a catalogue key, at most once.
        Catalogue keys left out are added visible; each export must keep a visible column.
        """
        known = set(COLLECTION_COLUMN_KEYS)
        items: list[ColumnLayoutItem] = []
        seen: set[str] = set()
        for key, visible in entries:
            if key not in known:
                raise ColumnLayoutInvalidException(f"Unknown column: {key}")
            if key in seen:
                raise ColumnLayoutInvalidException(f"Column listed twice: {key}")
            seen.add(key)
            items.append(ColumnLayoutItem(key, bool(visible)))
        _insert_missing(items, seen)
        layout = cls(items=tuple(items))
        layout.ensure_visible()
        return layout

    # ---------------------------------------------------------
    # USE
    # ---------------------------------------------------------

    @property
    def visible_keys(self) -> list[str]:
        return [item.key for item in self.items if item.visible]

    def ensure_visible(self) -> None:
        empty = [sheet.label for sheet in CollectionSheet if not collection_columns(sheet, self.visible_keys)]
        if empty:
            raise ColumnLayoutInvalidException(
                f"Keep at least one column visible for the {' and '.join(empty)} collection export."
            )

    def columns_for(self, sheet: CollectionSheet) -> tuple[ColumnSpec, ...]:
        """The sheet's visible columns in this order (the default ones should none be left)."""
        return collection_columns(sheet, self.visible_keys) or collection_columns(sheet)

    def to_json(self) -> list[dict[str, Any]]:
        return [item.to_json() for item in self.items]


def _insert_missing(items: list[ColumnLayoutItem], seen: set[str]) -> None:
    """Put each catalogue key not in `seen` back, visible, after its default predecessor."""
    for position, key in enumerate(COLLECTION_COLUMN_KEYS):
        if key in seen:
            continue
        if position == 0:
            at = 0
        else:
            before = COLLECTION_COLUMN_KEYS[position - 1]
            at = next(index for index, item in enumerate(items) if item.key == before) + 1
        items.insert(at, ColumnLayoutItem(key))
        seen.add(key)


__all__ = [
    "COLLECTION_LAYOUT",
    "ColumnLayout",
    "ColumnLayoutItem",
    "LayoutUser",
]
