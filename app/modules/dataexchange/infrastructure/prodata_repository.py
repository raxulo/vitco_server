"""
Prodata Exchange Repository

Core SQL queries for exporting and replacing Prodata rate-chart rows.
Export streams rows ordered by row_number ASC.
Replacement is an atomic transaction.

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.ratechart.infrastructure.models import ProdataRateRowModel

_ROWS = ProdataRateRowModel.__table__

_SHEET_COLUMNS = (
    _ROWS.c.row_number.label("row_number"),
    _ROWS.c.fat_min.label("fat_min"),
    _ROWS.c.fat_max.label("fat_max"),
    _ROWS.c.snf_min.label("snf_min"),
    _ROWS.c.snf_max.label("snf_max"),
    _ROWS.c.fat_rate_per_kg.label("fat_rate_per_kg"),
    _ROWS.c.snf_rate_per_kg.label("snf_rate_per_kg"),
    _ROWS.c.snf_cutoff.label("snf_cutoff"),
    _ROWS.c.snf_deduction.label("snf_deduction"),
)


class ProdataExchangeRepository:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # EXPORT
    # =========================================================

    async def count_export(self, rate_chart_id: UUID) -> int:
        stmt = select(func.count()).select_from(_ROWS).where(
            _ROWS.c.rate_chart_id == rate_chart_id,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def export_page(self, rate_chart_id: UUID, after_row_number: int | None, limit: int) -> Sequence[Row]:
        """
        One keyset page in row_number order.
        """
        stmt = (
            select(*_SHEET_COLUMNS)
            .select_from(_ROWS)
            .where(_ROWS.c.rate_chart_id == rate_chart_id)
            .order_by(_ROWS.c.row_number.asc())
            .limit(limit)
        )
        if after_row_number is not None:
            stmt = stmt.where(_ROWS.c.row_number > after_row_number)
        return (await self._session.execute(stmt)).all()

    # =========================================================
    # IMPORT — ATOMIC REPLACE
    # =========================================================

    async def replace_rows(self, rate_chart_id: UUID, rows: list[dict[str, Any]]) -> None:
        """
        Atomically replace all rows for this chart in one transaction.
        """
        await self._session.execute(
            delete(_ROWS).where(_ROWS.c.rate_chart_id == rate_chart_id)
        )
        if rows:
            await self._session.execute(insert(_ROWS), rows)
