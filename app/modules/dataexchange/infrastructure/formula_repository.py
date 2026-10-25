"""
Formula Rate-Chart Exchange Repository

Data access for Formula-based rate chart configuration export and import.
Follows Clean Architecture & DDD standards.

Python 3.13+
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.ratechart.domain.enums import MilkType, RateChartType
from app.modules.ratechart.infrastructure.models import RateChartModel, RateFormulaConfigModel


class FormulaExchangeRepository:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    async def get_chart_info(self, rate_chart_id: UUID) -> RateChartModel | None:
        return await self._session.scalar(
            select(RateChartModel).where(RateChartModel.id == rate_chart_id)
        )

    async def get_formula_config(self, rate_chart_id: UUID) -> RateFormulaConfigModel | None:
        return await self._session.scalar(
            select(RateFormulaConfigModel).where(RateFormulaConfigModel.rate_chart_id == rate_chart_id)
        )

    async def save_formula_config(
        self,
        rate_chart_id: UUID,
        *,
        milk_type: MilkType = MilkType.MIXED,
        cow_standard_fat: float | None = None,
        cow_standard_snf: float | None = None,
        cow_standard_rate: float | None = None,
        cow_fat_percentage: float | None = None,
        cow_snf_percentage: float | None = None,
        buffalo_standard_fat: float | None = None,
        buffalo_standard_snf: float | None = None,
        buffalo_standard_rate: float | None = None,
        buffalo_fat_percentage: float | None = None,
        buffalo_snf_percentage: float | None = None,
    ) -> RateFormulaConfigModel:
        existing = await self.get_formula_config(rate_chart_id)
        if existing is not None:
            existing.milk_type = milk_type
            if cow_standard_fat is not None:
                existing.cow_standard_fat = cow_standard_fat
            if cow_standard_snf is not None:
                existing.cow_standard_snf = cow_standard_snf
            if cow_standard_rate is not None:
                existing.cow_standard_rate = cow_standard_rate
            if cow_fat_percentage is not None:
                existing.cow_fat_percentage = cow_fat_percentage
            if cow_snf_percentage is not None:
                existing.cow_snf_percentage = cow_snf_percentage

            if buffalo_standard_fat is not None:
                existing.buffalo_standard_fat = buffalo_standard_fat
            if buffalo_standard_snf is not None:
                existing.buffalo_standard_snf = buffalo_standard_snf
            if buffalo_standard_rate is not None:
                existing.buffalo_standard_rate = buffalo_standard_rate
            if buffalo_fat_percentage is not None:
                existing.buffalo_fat_percentage = buffalo_fat_percentage
            if buffalo_snf_percentage is not None:
                existing.buffalo_snf_percentage = buffalo_snf_percentage

            existing.updated_at = now_naive_ist()
            await self._session.flush()
            return existing

        new_config = RateFormulaConfigModel(
            id=uuid4(),
            rate_chart_id=rate_chart_id,
            milk_type=milk_type,
            cow_standard_fat=cow_standard_fat,
            cow_standard_snf=cow_standard_snf,
            cow_standard_rate=cow_standard_rate,
            cow_fat_percentage=cow_fat_percentage,
            cow_snf_percentage=cow_snf_percentage,
            buffalo_standard_fat=buffalo_standard_fat,
            buffalo_standard_snf=buffalo_standard_snf,
            buffalo_standard_rate=buffalo_standard_rate,
            buffalo_fat_percentage=buffalo_fat_percentage,
            buffalo_snf_percentage=buffalo_snf_percentage,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )
        self._session.add(new_config)
        await self._session.flush()
        return new_config
