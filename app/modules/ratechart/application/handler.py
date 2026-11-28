from app.config.constants import IST
from app.modules.ratechart.domain.enums import RateChartType
from app.modules.collections.mcc_collection.domain.enums import MilkType
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.ratechart.domain.entities import (
    RateChart,
    RateFormulaConfig,
    RateGridRow,
    ProdataRateRow,
    RateChartAssignment,
)
from app.modules.common.settings.infrastructure.permissions import can_edit_rate_charts, rate_chart_limit
from app.modules.ratechart.domain.exceptions import (
    RateChartLimitReachedException,
    RateChartPermissionException,
    RateChartNotFoundException,
    RateChartAssignmentNotFoundException,
)
from app.modules.ratechart.infrastructure.repository import RateChartRepository
from app.middleware.authentication import CurrentUser
from app.core.clock import now_naive_ist
from app.modules.ratechart.domain.dto import (
    RateChartDto,
    RateChartListDto,
    RateChartAssignmentDto,
    RateChartAssignmentListDto,
    BulkAssignmentResultDto,
)
from app.modules.ratechart.application.command import (
    CreateRateChartCommand,
    UpdateRateChartCommand,
    DeleteRateChartCommand,
    SaveFormulaConfigCommand,
    SaveGridRowsCommand,
    SaveProdataRowsCommand,
    GetRateChartQuery,
    ListRateChartsQuery,
    CreateRateChartAssignmentCommand,
    AssignChartToOwnersCommand,
    UpdateRateChartAssignmentCommand,
    DeleteRateChartAssignmentCommand,
    GetRateChartAssignmentQuery,
    GetAssignmentsByOwnerQuery,
    ListRateChartAssignmentsQuery,
)


class RateChartHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: RateChartRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE / UPDATE / DELETE
    # =========================================================

    async def create(
        self,
        command: CreateRateChartCommand,
    ) -> RateChartDto:
        if not command.chart_name.strip():
            raise ValidationException("Invalid Chart Name")
        await self.ensure_can_edit(command.owner)
        await self._ensure_within_chart_limit(command.owner)

        chart = RateChart(
            id=uuid4(),
            chart_name=command.chart_name.strip(),
            chart_type=command.chart_type,
            milk_type=command.milk_type,
            calculation_type=command.calculation_type,
            effective_from=command.effective_from,
            effective_to=command.effective_to,
            status=command.status,
            created_by=command.created_by,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
            description=command.description,
        )

        async with self._database.transaction():
            await self._repository.create(chart)

        return self._to_dto(chart)

    async def update(
        self,
        command: UpdateRateChartCommand,
    ) -> RateChartDto:
        if not command.chart_name.strip():
            raise ValidationException("Invalid Chart Name")
        await self.ensure_can_edit(command.owner)

        async with self._database.transaction():
            chart = await self._repository.get_by_id(command.id, command.owner)
            if chart is None:
                raise RateChartNotFoundException()

            chart.chart_name = command.chart_name.strip()
            chart.chart_type = command.chart_type
            chart.milk_type = command.milk_type
            chart.calculation_type = command.calculation_type
            chart.effective_from = command.effective_from
            chart.effective_to = command.effective_to
            chart.status = command.status
            chart.description = command.description
            chart.updated_at = now_naive_ist()

            await self._repository.update(chart, command.owner)

        return self._to_dto(chart)

    async def delete(
        self,
        command: DeleteRateChartCommand,
    ) -> None:
        await self.ensure_can_edit(command.owner)
        async with self._database.transaction():
            chart = await self._repository.get_by_id(command.id, command.owner)
            if chart is None:
                raise RateChartNotFoundException()
            await self._repository.delete(chart.id, command.owner)

    async def chart_quota(self, owner: CurrentUser | None) -> tuple[int, int | None]:
        """(charts already created, allowed maximum or None for no limit) for the owner."""
        if owner is None:
            return 0, None
        limit = await rate_chart_limit(self._database.session, owner)
        if limit is None:
            return 0, None
        return await self._repository.count_created_by(owner.id), limit

    async def _ensure_within_chart_limit(self, owner: CurrentUser | None) -> None:
        """An MCC / VLCC may not create more rate charts than its settings allow."""
        used, limit = await self.chart_quota(owner)
        if limit is not None and used >= limit:
            raise RateChartLimitReachedException(
                f"You can create at most {limit} rate chart{'s' if limit != 1 else ''}. "
                f"You already have {used}."
            )

    async def can_edit(self, owner: CurrentUser | None) -> bool:
        """May this user create / modify rate charts at all (rate chart permission)?"""
        return await can_edit_rate_charts(self._database.session, owner)

    async def ensure_can_edit(self, owner: CurrentUser | None) -> None:
        """MCC / VLCC without the rate chart permission can only view charts."""
        if owner is not None and not await self.can_edit(owner):
            raise RateChartPermissionException()

    async def ensure_modifiable(self, chart_id: UUID, owner: CurrentUser) -> None:
        """Needs the rate chart permission, and charts made above the user stay read-only for it."""
        await self.ensure_can_edit(owner)
        if not await self._repository.is_modifiable(chart_id, owner):
            raise RateChartNotFoundException()

    async def get(
        self,
        query: GetRateChartQuery,
    ) -> RateChartDto:
        chart = await self._repository.get_by_id(query.id, query.owner)
        if chart is None:
            raise RateChartNotFoundException()
        return self._to_dto(chart)

    async def list(
        self,
        query: ListRateChartsQuery,
    ) -> list[RateChartListDto]:
        if query.keyword:
            entities = await self._repository.search(
                keyword=query.keyword,
                offset=query.offset,
                limit=query.size,
                owner=query.owner,
            )
        else:
            entities = await self._repository.list(
                offset=query.offset,
                limit=query.size,
                owner=query.owner,
            )

        return [
            RateChartListDto(
                id=e.id,
                chart_name=e.chart_name,
                chart_type=e.chart_type,
                milk_type=e.milk_type,
                effective_from=e.effective_from,
                status=e.status,
                can_modify=e.can_modify,
                owner_name=e.owner_name,
            )
            for e in entities
        ]

    async def count(self, owner: CurrentUser | None = None) -> int:
        return await self._repository.count(owner)

    async def count_search(self, keyword: str, owner: CurrentUser | None = None) -> int:
        return await self._repository.count_search(keyword, owner)

    # =========================================================
    # FORMULA CONFIGURATION
    # =========================================================

    async def save_formula_config(
        self,
        command: SaveFormulaConfigCommand,
        owner: CurrentUser | None = None
    ) -> None:
        async with self._database.transaction():
            chart = await self._repository.get_by_id(command.rate_chart_id, owner)
            if chart is None:
                raise RateChartNotFoundException()
            # Visible is not enough: only the creator or someone above it may change the rows
            if owner is not None and not await self._repository.is_modifiable(command.rate_chart_id, owner):
                raise RateChartNotFoundException()

            existing = await self._repository.get_formula_config(command.rate_chart_id)
            config_id = existing.id if existing else uuid4()

            config = RateFormulaConfig(
                id=config_id,
                rate_chart_id=command.rate_chart_id,
                milk_type=command.milk_type,
                cow_standard_fat=command.cow_standard_fat,
                cow_standard_snf=command.cow_standard_snf,
                cow_standard_rate=command.cow_standard_rate,
                buffalo_standard_fat=command.buffalo_standard_fat,
                buffalo_standard_snf=command.buffalo_standard_snf,
                buffalo_standard_rate=command.buffalo_standard_rate,
                cow_fat_percentage=command.cow_fat_percentage,
                cow_snf_percentage=command.cow_snf_percentage,
                buffalo_fat_percentage=command.buffalo_fat_percentage,
                buffalo_snf_percentage=command.buffalo_snf_percentage,
            )
            await self._repository.save_formula_config(config)

    async def get_formula_config(
        self,
        rate_chart_id: UUID,
    ) -> RateFormulaConfig | None:
        return await self._repository.get_formula_config(rate_chart_id)

    # =========================================================
    # GRID ROWS
    # =========================================================

    async def save_grid_rows(
        self,
        command: SaveGridRowsCommand,
        owner: CurrentUser | None = None
    ) -> None:
        async with self._database.transaction():
            chart = await self._repository.get_by_id(command.rate_chart_id, owner)
            if chart is None:
                raise RateChartNotFoundException()
            # Visible is not enough: only the creator or someone above it may change the rows
            if owner is not None and not await self._repository.is_modifiable(command.rate_chart_id, owner):
                raise RateChartNotFoundException()

            rows = [
                RateGridRow(
                    id=uuid4(),
                    rate_chart_id=command.rate_chart_id,
                    row_number=r.row_number,
                    fat=r.fat,
                    snf=r.snf,
                    rate=r.rate,
                )
                for r in command.rows
            ]
            await self._repository.save_grid_rows(command.rate_chart_id, rows)

    async def get_grid_rows(
        self,
        rate_chart_id: UUID,
    ) -> list[RateGridRow]:
        return await self._repository.get_grid_rows(rate_chart_id)

    # =========================================================
    # PRODATA ROWS
    # =========================================================

    async def save_prodata_rows(
        self,
        command: SaveProdataRowsCommand,
        owner: CurrentUser | None = None
    ) -> None:
        async with self._database.transaction():
            chart = await self._repository.get_by_id(command.rate_chart_id, owner)
            if chart is None:
                raise RateChartNotFoundException()
            # Visible is not enough: only the creator or someone above it may change the rows
            if owner is not None and not await self._repository.is_modifiable(command.rate_chart_id, owner):
                raise RateChartNotFoundException()

            rows = [
                ProdataRateRow(
                    id=uuid4(),
                    rate_chart_id=command.rate_chart_id,
                    row_number=r.row_number,
                    fat_min=r.fat_min,
                    fat_max=r.fat_max,
                    snf_min=r.snf_min,
                    snf_max=r.snf_max,
                    fat_rate_per_kg=r.fat_rate_per_kg,
                    snf_rate_per_kg=r.snf_rate_per_kg,
                    snf_cutoff=r.snf_cutoff,
                    snf_deduction=r.snf_deduction,
                )
                for r in command.rows
            ]
            await self._repository.save_prodata_rows(command.rate_chart_id, rows)

    async def get_prodata_rows(
        self,
        rate_chart_id: UUID,
    ) -> list[ProdataRateRow]:
        return await self._repository.get_prodata_rows(rate_chart_id)

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _to_dto(chart: RateChart) -> RateChartDto:
        return RateChartDto(
            id=chart.id,
            chart_name=chart.chart_name,
            chart_type=chart.chart_type,
            milk_type=chart.milk_type,
            calculation_type=chart.calculation_type,
            effective_from=chart.effective_from,
            effective_to=chart.effective_to,
            status=chart.status,
            description=chart.description,
            can_modify=chart.can_modify,
            owner_name=chart.owner_name,
        )

    # =========================================================
    # ASSIGNMENT METHODS
    # =========================================================

    async def create_assignment(
        self,
        command: CreateRateChartAssignmentCommand,
    ) -> RateChartAssignmentDto:
        assignment = RateChartAssignment(
            id=uuid4(),
            owner_type=command.owner_type,
            owner_id=command.owner_id,
            rate_chart_id=command.rate_chart_id,
            priority=command.priority,
            is_default=command.is_default,
            is_active=True,
            created_by=command.created_by,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )

        async with self._database.transaction():
            await self._repository.create_assignment(assignment)

        return self._to_assignment_dto(assignment)

    async def assign_chart_to_owners(
        self,
        command: AssignChartToOwnersCommand,
    ) -> BulkAssignmentResultDto:
        """Append the chart to every owner's list in one transaction (skip owners that already have it)."""
        owner_ids = list(dict.fromkeys(command.owner_ids))
        if not owner_ids:
            return BulkAssignmentResultDto(assigned=0, skipped=0)

        assigned = 0
        skipped = 0
        async with self._database.transaction():
            existing = await self._repository.get_assignments_by_owners(owner_ids)
            by_owner: dict[UUID, list[RateChartAssignment]] = {}
            for row in existing:
                by_owner.setdefault(row.owner_id, []).append(row)

            now = now_naive_ist()
            for owner_id in owner_ids:
                rows = by_owner.get(owner_id, [])
                if any(r.rate_chart_id == command.rate_chart_id for r in rows):
                    skipped += 1
                    continue
                await self._repository.create_assignment(
                    RateChartAssignment(
                        id=uuid4(),
                        owner_type=command.owner_type,
                        owner_id=owner_id,
                        rate_chart_id=command.rate_chart_id,
                        priority=max((r.priority for r in rows), default=-1) + 1,
                        is_default=not rows,
                        is_active=True,
                        created_by=command.created_by,
                        created_at=now,
                        updated_at=now,
                    )
                )
                assigned += 1

        return BulkAssignmentResultDto(assigned=assigned, skipped=skipped)

    async def update_assignment(
        self,
        command: UpdateRateChartAssignmentCommand,
    ) -> RateChartAssignmentDto:
        async with self._database.transaction():
            assignment = await self._repository.get_assignment_by_id(command.id)
            if assignment is None:
                raise RateChartAssignmentNotFoundException()

            assignment.owner_type = command.owner_type
            assignment.owner_id = command.owner_id
            assignment.rate_chart_id = command.rate_chart_id
            assignment.priority = command.priority
            assignment.is_default = command.is_default
            assignment.is_active = command.is_active
            assignment.updated_at = now_naive_ist()

            await self._repository.update_assignment(assignment)

        return self._to_assignment_dto(assignment)

    async def delete_assignment(
        self,
        command: DeleteRateChartAssignmentCommand,
    ) -> None:
        async with self._database.transaction():
            assignment = await self._repository.get_assignment_by_id(command.id)
            if assignment is None:
                raise RateChartAssignmentNotFoundException()
            await self._repository.delete_assignment(command.id)

    async def get_assignment(
        self,
        query: GetRateChartAssignmentQuery,
    ) -> RateChartAssignmentDto:
        assignment = await self._repository.get_assignment_by_id(query.id)
        if assignment is None:
            raise RateChartAssignmentNotFoundException()
        return self._to_assignment_dto(assignment)

    async def get_assignments_by_owner(
        self,
        query: GetAssignmentsByOwnerQuery,
    ) -> list[RateChartAssignmentDto]:
        assignments = await self._repository.get_assignments_by_owner(query.owner_id)
        return [self._to_assignment_dto(a) for a in assignments]

    async def get_charts_by_owner_id(
        self, query: GetAssignmentsByOwnerQuery
    ) -> list[RateChartListDto]:
        return await self._repository.get_charts_by_owner_id(query.owner_id)

    async def list_assignments(
        self,
        query: ListRateChartAssignmentsQuery,
    ) -> list[RateChartAssignmentListDto]:
        assignments = await self._repository.list_assignments(
            offset=query.offset,
            limit=query.size,
        )
        return [
            RateChartAssignmentListDto(
                id=a.id,
                owner_type=a.owner_type,
                owner_id=a.owner_id,
                rate_chart_id=a.rate_chart_id,
                priority=a.priority,
                is_default=a.is_default,
                is_active=a.is_active,
            )
            for a in assignments
        ]

    @staticmethod
    def _to_assignment_dto(assignment: RateChartAssignment) -> RateChartAssignmentDto:
        return RateChartAssignmentDto(
            id=assignment.id,
            owner_type=assignment.owner_type,
            owner_id=assignment.owner_id,
            rate_chart_id=assignment.rate_chart_id,
            priority=assignment.priority,
            is_default=assignment.is_default,
            is_active=assignment.is_active,
        )

    async def delete_assignments_by_owner(
        self,
        owner_id: UUID,
    ) -> None:
        async with self._database.transaction():
            await self._repository.delete_assignments_by_owner(owner_id)


    async def get_rate_by_chart_id(
        self,
        chart_id: UUID,
        fat_percent: float,
        snf_percent: float,
        milk_type: MilkType | None = None,
    ) -> float:
        chart_type = await self._repository.get_chart_type(chart_id)

        if chart_type is None:
            return 0.0

        if chart_type in (RateChartType.TEXT, RateChartType.CSV):
            return await self._repository.resolve_grid_rate(
                chart_id,
                fat_percent,
                snf_percent,
            )

        if chart_type is RateChartType.PRODATA:
            return await self._repository.resolve_prodata_rate(
                chart_id,
                fat_percent,
                snf_percent,
            )

        if chart_type is RateChartType.FORMULA:
            return await self._repository.resolve_formula_rate(
                chart_id,
                fat_percent,
                snf_percent,
                milk_type,
            )

        return 0.0
