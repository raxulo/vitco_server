"""
RateChart ViewModel Assembler
"""

from uuid import UUID
from app.modules.ratechart.application.command import (
    CreateRateChartCommand,
    UpdateRateChartCommand,
)
from app.modules.ratechart.presentation.requests import (
    CreateRateChartRequest,
    UpdateRateChartRequest,
)


class RateChartAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        data: CreateRateChartRequest,
        created_by: UUID | None = None,
    ) -> CreateRateChartCommand:
        return CreateRateChartCommand(
            chart_name=data.chart_name,
            chart_type=data.chart_type,
            milk_type=data.milk_type,
            calculation_type=data.calculation_type,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            status=data.status,
            description=data.description,
            created_by=created_by,
        )

    @staticmethod
    def update(
        id: UUID,
        data: UpdateRateChartRequest,
    ) -> UpdateRateChartCommand:
        return UpdateRateChartCommand(
            id=id,
            chart_name=data.chart_name,
            chart_type=data.chart_type,
            milk_type=data.milk_type,
            calculation_type=data.calculation_type,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            status=data.status,
            description=data.description,
        )
