from __future__ import annotations

from app.modules.ratechart.domain.entities import (
    RateChart,
    RateFormulaConfig,
    RateGridRow,
    ProdataRateRow,
    RateChartAssignment,
)
from app.modules.ratechart.infrastructure.models import (
    RateChartModel,
    RateFormulaConfigModel,
    RateGridModel,
    ProdataRateRowModel,
    RateChartAssignmentModel,
)


class RateChartMapper:

    @staticmethod
    def to_entity(model: RateChartModel, can_modify: bool = False, owner_name: str | None = None) -> RateChart:
        return RateChart(
            id=model.id,
            chart_name=model.chart_name,
            chart_type=model.chart_type,
            milk_type=model.milk_type,
            calculation_type=model.calculation_type,
            effective_from=model.effective_from,
            effective_to=model.effective_to,
            status=model.status,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            description=model.description,
            can_modify=can_modify,
            owner_name=owner_name,
        )

    @staticmethod
    def to_model(entity: RateChart) -> RateChartModel:
        return RateChartModel(
            id=entity.id,
            chart_name=entity.chart_name,
            chart_type=entity.chart_type,
            milk_type=entity.milk_type,
            calculation_type=entity.calculation_type,
            effective_from=entity.effective_from,
            effective_to=entity.effective_to,
            status=entity.status,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            description=entity.description,
        )

    @staticmethod
    def to_formula_entity(model: RateFormulaConfigModel) -> RateFormulaConfig:
        return RateFormulaConfig(
            id=model.id,
            rate_chart_id=model.rate_chart_id,
            milk_type=model.milk_type,
            cow_standard_fat=model.cow_standard_fat,
            cow_standard_snf=model.cow_standard_snf,
            cow_standard_rate=model.cow_standard_rate,
            buffalo_standard_fat=model.buffalo_standard_fat,
            buffalo_standard_snf=model.buffalo_standard_snf,
            buffalo_standard_rate=model.buffalo_standard_rate,
            cow_fat_percentage=model.cow_fat_percentage,
            cow_snf_percentage=model.cow_snf_percentage,
            buffalo_fat_percentage=model.buffalo_fat_percentage,
            buffalo_snf_percentage=model.buffalo_snf_percentage,
        )

    @staticmethod
    def to_formula_model(entity: RateFormulaConfig) -> RateFormulaConfigModel:
        return RateFormulaConfigModel(
            id=entity.id,
            rate_chart_id=entity.rate_chart_id,
            milk_type=entity.milk_type,
            cow_standard_fat=entity.cow_standard_fat,
            cow_standard_snf=entity.cow_standard_snf,
            cow_standard_rate=entity.cow_standard_rate,
            buffalo_standard_fat=entity.buffalo_standard_fat,
            buffalo_standard_snf=entity.buffalo_standard_snf,
            buffalo_standard_rate=entity.buffalo_standard_rate,
            cow_fat_percentage=entity.cow_fat_percentage,
            cow_snf_percentage=entity.cow_snf_percentage,
            buffalo_fat_percentage=entity.buffalo_fat_percentage,
            buffalo_snf_percentage=entity.buffalo_snf_percentage,
        )

    @staticmethod
    def to_grid_entity(model: RateGridModel) -> RateGridRow:
        return RateGridRow(
            id=model.id,
            rate_chart_id=model.rate_chart_id,
            row_number=model.row_number,
            fat=model.fat,
            snf=model.snf,
            rate=model.rate,
        )

    @staticmethod
    def to_grid_model(entity: RateGridRow) -> RateGridModel:
        return RateGridModel(
            id=entity.id,
            rate_chart_id=entity.rate_chart_id,
            row_number=entity.row_number,
            fat=entity.fat,
            snf=entity.snf,
            rate=entity.rate,
        )

    @staticmethod
    def to_prodata_entity(model: ProdataRateRowModel) -> ProdataRateRow:
        return ProdataRateRow(
            id=model.id,
            rate_chart_id=model.rate_chart_id,
            row_number=model.row_number,
            fat_min=model.fat_min,
            fat_max=model.fat_max,
            snf_min=model.snf_min,
            snf_max=model.snf_max,
            fat_rate_per_kg=model.fat_rate_per_kg,
            snf_rate_per_kg=model.snf_rate_per_kg,
            snf_cutoff=model.snf_cutoff,
            snf_deduction=model.snf_deduction,
        )

    @staticmethod
    def to_prodata_model(entity: ProdataRateRow) -> ProdataRateRowModel:
        return ProdataRateRowModel(
            id=entity.id,
            rate_chart_id=entity.rate_chart_id,
            row_number=entity.row_number,
            fat_min=entity.fat_min,
            fat_max=entity.fat_max,
            snf_min=entity.snf_min,
            snf_max=entity.snf_max,
            fat_rate_per_kg=entity.fat_rate_per_kg,
            snf_rate_per_kg=entity.snf_rate_per_kg,
            snf_cutoff=entity.snf_cutoff,
            snf_deduction=entity.snf_deduction,
        )

    @staticmethod
    def to_assignment_entity(model: RateChartAssignmentModel) -> RateChartAssignment:
        return RateChartAssignment(
            id=model.id,
            owner_type=model.owner_type,
            owner_id=model.owner_id,
            rate_chart_id=model.rate_chart_id,
            priority=model.priority,
            is_default=model.is_default,
            is_active=model.is_active,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_assignment_model(entity: RateChartAssignment) -> RateChartAssignmentModel:
        return RateChartAssignmentModel(
            id=entity.id,
            owner_type=entity.owner_type,
            owner_id=entity.owner_id,
            rate_chart_id=entity.rate_chart_id,
            priority=entity.priority,
            is_default=entity.is_default,
            is_active=entity.is_active,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )