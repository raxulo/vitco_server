from sqlalchemy.orm import identity, aliased
from app.modules.collections.mcc_collection.domain.enums import MilkType
from app.modules.ratechart.domain.enums import RateChartType
from app.modules.ratechart.domain.dto import RateChartListDto
from app.modules.ratechart.domain.exceptions import RateChartAssignmentNotFoundException
from sqlalchemy import update
from uuid import UUID

from sqlalchemy import select, delete, func, or_, true, false, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.ratechart.domain.entities import (
    RateChart,
    RateFormulaConfig,
    RateGridRow,
    ProdataRateRow,
    RateChartAssignment,
)
from app.modules.ratechart.domain.irepository import IRateChartRepository
from app.modules.ratechart.infrastructure.mapper import RateChartMapper
from app.modules.ratechart.infrastructure.models import (
    RateChartModel,
    RateFormulaConfigModel,
    RateGridModel,
    ProdataRateRowModel,
    RateChartAssignmentModel,
)
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.middleware.authentication import CurrentUser


# class RateChartAccessScope:

#     @staticmethod
#     def get_condition(owner: CurrentUser):
#         if owner.role_type == Role.SUPER_ADMIN:
#             return true()

#         if owner.role_type == Role.ADMIN:
#             return or_(
#                 RateChartModel.created_by == owner.id,
#                 exists(
#                     select(1)
#                     .select_from(UserModel)
#                     .where(
#                         UserModel.id == RateChartModel.created_by,  
#                         UserModel.created_by == owner.id,
#                     )
#                     .correlate(RateChartModel)
#                 ),
#             )

#         return false()

#     @staticmethod
#     def condition(owner: CurrentUser):
#         if owner.role_type == Role.SUPER_ADMIN:
#             return true()

#         if owner.role_type in {Role.ADMIN, Role.SUB_ADMIN, Role.VLCC, Role.MCC}:
#             return or_(
#                 RateChartModel.created_by == owner.id,
#                 exists(
#                     select(1)
#                     .select_from(UserModel)
#                     .where(
#                         UserModel.id == RateChartModel.created_by,  
#                         UserModel.created_by == owner.id,
#                     )
#                     .correlate(RateChartModel)
#                 ),
#             )

#         return false()


class RateChartAccessScope:

    # =========================================================
    # OWN RATE CHART
    # =========================================================

    @staticmethod
    def own(owner_id: UUID):
        return RateChartModel.created_by == owner_id

    # =========================================================
    # ASSIGNED RATE CHART
    #
    # Used mainly by MCC / VLCC.
    # =========================================================

    @staticmethod
    def assigned(owner_id: UUID):
        return exists(
            select(1)
            .select_from(RateChartAssignmentModel)
            .where(
                RateChartAssignmentModel.rate_chart_id
                == RateChartModel.id,
                RateChartAssignmentModel.owner_id == owner_id,
                RateChartAssignmentModel.is_active.is_(True),
            )
        )

    # =========================================================
    # READ ACCESS
    # =========================================================

    @staticmethod
    def get_condition(owner: CurrentUser):
        """
        View / use / assign (map).

        - Super Admin charts      -> everyone
        - Charts made by the user or anyone below it (see `Hierarchy`)
        - Charts made by anyone above it (its Admin, Sub Admin, MCC creator...)
        Charts from another Admin's tree stay invisible, even if assigned earlier.
        """
        return Hierarchy.shared_visible(owner, RateChartModel.created_by)

    # =========================================================
    # WRITE ACCESS
    #
    # Only writable RateCharts are returned by this condition.
    # Parent/assigned RateCharts are intentionally excluded.
    # =========================================================

    @staticmethod
    def write_condition(owner: CurrentUser):
        """Modify / delete: charts made by the user or anyone below it. Charts from above are read-only."""
        return RateChartAccessScope.can_modify(owner, RateChartModel.created_by)

    @staticmethod
    def can_modify(owner: CurrentUser | None, item_created_by):
        return Hierarchy.shared_modifiable(owner, item_created_by)

    # =========================================================
    # GET INCLUDING ASSIGNED
    # =========================================================

    @staticmethod
    def get_with_assignment_condition(owner: CurrentUser):
        return RateChartAccessScope.get_condition(owner)

class RateChartRepository(IRateChartRepository):

    __slots__ = ("_database",)
    _GRID_TOLERANCE = 0.005

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # CREATE / UPDATE / DELETE
    # =========================================================

    async def create(
        self,
        entity: RateChart,
    ) -> None:
        model = RateChartMapper.to_model(entity)
        self._session.add(model)

    async def count_created_by(self, user_id: UUID) -> int:
        """Rate charts a user created (for the MCC / VLCC chart limit)."""
        return await self._session.scalar(
            select(func.count(RateChartModel.id)).where(RateChartModel.created_by == user_id)
        ) or 0


    async def update(
        self,
        entity: RateChart,
        owner: CurrentUser,
    ) -> None:

        stmt = (
            select(RateChartModel)
            .where(
                RateChartModel.id == entity.id,
                RateChartAccessScope.write_condition(owner),
            )
        )

        model = await self._session.scalar(stmt)

        if model is None:
            return

        model.chart_name = entity.chart_name
        model.chart_type = entity.chart_type
        model.milk_type = entity.milk_type
        model.calculation_type = entity.calculation_type
        model.effective_from = entity.effective_from
        model.effective_to = entity.effective_to
        model.status = entity.status
        model.description = entity.description
        model.updated_at = entity.updated_at

    # async def update(
    #     self,
    #     entity: RateChart,
    #     owner: CurrentUser | None = None,
    # ) -> None:
    #     stmt = select(RateChartModel).where(RateChartModel.id == entity.id)
    #     if owner is not None:
    #         stmt = stmt.where(RateChartModel.created_by == owner.id)
    #     model = await self._session.scalar(stmt)
    #     if model is None:
    #         return

    #     model.chart_name = entity.chart_name
    #     model.chart_type = entity.chart_type
    #     model.milk_type = entity.milk_type
    #     model.calculation_type = entity.calculation_type
    #     model.effective_from = entity.effective_from
    #     model.effective_to = entity.effective_to
    #     model.status = entity.status
    #     model.description = entity.description
    #     model.updated_at = entity.updated_at

    async def delete(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> None:

        stmt = (
            select(RateChartModel)
            .where(
                RateChartModel.id == id,
                RateChartAccessScope.write_condition(owner),
            )
        )

        model = await self._session.scalar(stmt)

        if model is not None:
            await self._session.delete(model)

    async def is_modifiable(self, id: UUID, owner: CurrentUser) -> bool:
        """Whether the user may edit this chart (creator or someone above it)."""
        found = await self._session.scalar(
            select(RateChartModel.id).where(
                RateChartModel.id == id,
                RateChartAccessScope.write_condition(owner),
            )
        )
        return found is not None

    async def get_by_id(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> RateChart | None:

        Creator = aliased(UserModel, name="creator")
        can_modify = RateChartAccessScope.can_modify(owner, RateChartModel.created_by)
        stmt = (
            select(RateChartModel, can_modify.label("can_modify"), Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == RateChartModel.created_by)
            .where(
                RateChartModel.id == id,
                RateChartAccessScope.get_condition(owner),
            )
        )

        row = (await self._session.execute(stmt)).one_or_none()

        return (
            RateChartMapper.to_entity(row.RateChartModel, row.can_modify, row.owner_name)
            if row
            else None
        )

    # =========================================================
    # FORMULA CONFIG
    # =========================================================

    async def get_formula_config(
        self,
        rate_chart_id: UUID,
    ) -> RateFormulaConfig | None:
        stmt = select(RateFormulaConfigModel).where(
            RateFormulaConfigModel.rate_chart_id == rate_chart_id
        )
        model = await self._session.scalar(stmt)
        if model is None:
            return None
        return RateChartMapper.to_formula_entity(model)

    async def save_formula_config(
        self,
        config: RateFormulaConfig,
    ) -> None:
        existing = await self._session.get(RateFormulaConfigModel, config.id)
        if existing is not None:
            existing.cow_standard_fat = config.cow_standard_fat
            existing.cow_standard_snf = config.cow_standard_snf
            existing.cow_standard_rate = config.cow_standard_rate
            existing.buffalo_standard_fat = config.buffalo_standard_fat
            existing.buffalo_standard_snf = config.buffalo_standard_snf
            existing.buffalo_standard_rate = config.buffalo_standard_rate
            existing.cow_fat_percentage = config.cow_fat_percentage
            existing.cow_snf_percentage = config.cow_snf_percentage
            existing.buffalo_fat_percentage = config.buffalo_fat_percentage
            existing.buffalo_snf_percentage = config.buffalo_snf_percentage
        else:
            model = RateChartMapper.to_formula_model(config)
            self._session.add(model)

    # =========================================================
    # GRID ROWS
    # =========================================================

    async def get_grid_rows(
        self,
        rate_chart_id: UUID,
    ) -> list[RateGridRow]:
        stmt = (
            select(RateGridModel)
            .where(RateGridModel.rate_chart_id == rate_chart_id)
            .order_by(RateGridModel.row_number.asc())
        )
        result = await self._session.scalars(stmt)
        return [RateChartMapper.to_grid_entity(m) for m in result]

    async def save_grid_rows(
        self,
        rate_chart_id: UUID,
        rows: list[RateGridRow],
    ) -> None:
        # Clear existing rows first
        await self._session.execute(
            delete(RateGridModel).where(RateGridModel.rate_chart_id == rate_chart_id)
        )
        # Bulk add new ones
        for row in rows:
            model = RateChartMapper.to_grid_model(row)
            self._session.add(model)

    # =========================================================
    # PRODATA ROWS
    # =========================================================

    async def get_prodata_rows(
        self,
        rate_chart_id: UUID,
    ) -> list[ProdataRateRow]:
        stmt = (
            select(ProdataRateRowModel)
            .where(ProdataRateRowModel.rate_chart_id == rate_chart_id)
            .order_by(ProdataRateRowModel.row_number.asc())
        )
        result = await self._session.scalars(stmt)
        return [RateChartMapper.to_prodata_entity(m) for m in result]

    async def save_prodata_rows(
        self,
        rate_chart_id: UUID,
        rows: list[ProdataRateRow],
    ) -> None:
        # Clear existing rows first
        await self._session.execute(
            delete(ProdataRateRowModel).where(
                ProdataRateRowModel.rate_chart_id == rate_chart_id
            )
        )
        # Bulk add new ones
        for row in rows:
            model = RateChartMapper.to_prodata_model(row)
            self._session.add(model)

    # =========================================================
    # PAGINATION & SEARCH
    # =========================================================
    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser,
    ) -> list[RateChart]:
        Creator = aliased(UserModel, name="creator")
        can_modify = RateChartAccessScope.can_modify(owner, RateChartModel.created_by)
        stmt = (
            select(RateChartModel, can_modify.label("can_modify"), Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == RateChartModel.created_by)
            .where(
                RateChartAccessScope.get_condition(owner),
            )
            .order_by(
                RateChartModel.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return [
            RateChartMapper.to_entity(row.RateChartModel, row.can_modify, row.owner_name)
            for row in result
        ]
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser | None = None,
    ) -> list[RateChart]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(offset=offset, limit=limit, owner=owner)

        pattern = f"%{keyword}%"
        Creator = aliased(UserModel, name="creator")
        can_modify = RateChartAccessScope.can_modify(owner, RateChartModel.created_by)
        stmt = (
            select(RateChartModel, can_modify.label("can_modify"), Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == RateChartModel.created_by)
            .where(RateChartModel.chart_name.ilike(pattern))
            .order_by(RateChartModel.chart_name.asc())
            .offset(offset)
            .limit(limit)
        )
        if owner is not None:
            stmt = stmt.where(RateChartAccessScope.get_condition(owner))
        result = await self._session.execute(stmt)
        return [RateChartMapper.to_entity(row.RateChartModel, getattr(row, 'can_modify', False), row.owner_name) for row in result]

    async def count(self, owner: CurrentUser | None = None) -> int:
        from sqlalchemy import func
        stmt = select(func.count(RateChartModel.id))
        if owner is not None:
            stmt = stmt.where(RateChartAccessScope.get_condition(owner))
        return await self._session.scalar(stmt) or 0

    async def count_search(
        self,
        keyword: str,
        owner: CurrentUser | None = None,
    ) -> int:
        from sqlalchemy import func
        keyword = keyword.strip()
        pattern = f"%{keyword}%"
        stmt = select(func.count(RateChartModel.id)).where(
            RateChartModel.chart_name.ilike(pattern)
        )
        if owner is not None:
            stmt = stmt.where(RateChartAccessScope.get_condition(owner))
        return await self._session.scalar(stmt) or 0

    async def create_assignment(
        self,
        entity: RateChartAssignment,
    ) -> None:
        model = RateChartMapper.to_assignment_model(entity)
        self._session.add(model)

    async def update_assignment(
        self,
        entity: RateChartAssignment,
    ) -> None:
        model = await self._session.get(RateChartAssignmentModel, entity.id)
        if model is None:
            return

        model.owner_type = entity.owner_type
        model.owner_id = entity.owner_id
        model.rate_chart_id = entity.rate_chart_id
        model.priority = entity.priority
        model.is_default = entity.is_default
        model.is_active = entity.is_active
        model.updated_at = entity.updated_at

    async def delete_assignment(
        self,
        id: UUID,
    ) -> None:
        model = await self._session.get(RateChartAssignmentModel, id)
        if model is not None:
            await self._session.delete(model)

    async def get_assignment_by_id(
        self,
        id: UUID,
    ) -> RateChartAssignment | None:
        model = await self._session.get(RateChartAssignmentModel, id)
        if model is None:
            return None
        return RateChartMapper.to_assignment_entity(model)

    async def get_assignments_by_owner(
        self,
        owner_id: UUID,
    ) -> list[RateChartAssignment]:
        stmt = (
            select(RateChartAssignmentModel)
            .where(
                RateChartAssignmentModel.owner_id == owner_id,
                RateChartAssignmentModel.is_active == True,
            )
            .order_by(RateChartAssignmentModel.priority.desc())
        )
        result = await self._session.scalars(stmt)
        return [RateChartMapper.to_assignment_entity(model) for model in result]

    async def get_charts_by_owner_id(self, owner_id: UUID) -> list[RateChartListDto]:
        stmt = (
            select(
                RateChartModel.id,
                RateChartModel.chart_name,
                RateChartModel.chart_type,
                RateChartModel.effective_from,
                RateChartModel.milk_type,
                RateChartModel.status,
                RateChartAssignmentModel.is_default,
            )
            .select_from(RateChartAssignmentModel)
            .join(
                RateChartModel,
                RateChartModel.id == RateChartAssignmentModel.rate_chart_id,
            )
            .where(
                RateChartAssignmentModel.owner_id == owner_id,
                RateChartAssignmentModel.is_active.is_(True),
            )
            # Rank order: index 0 is R1 (a farmer's / VLCC's assigned_chart_rank picks R<n>)
            .order_by(
                RateChartAssignmentModel.priority.asc(),
                RateChartAssignmentModel.created_at.asc(),
            )
        )

        rows = (await self._session.execute(stmt)).mappings().all()

        return [RateChartListDto(**row) for row in rows]

    async def list_assignments(self,offset: int,limit: int) -> list[RateChartAssignment]:
        stmt = (
            select(RateChartAssignmentModel)
            .where(RateChartAssignmentModel.is_active == True)
            .order_by(RateChartAssignmentModel.priority.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [RateChartMapper.to_assignment_entity(model) for model in result]

    async def count_assignments(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count(RateChartAssignmentModel.id)).where(
            RateChartAssignmentModel.is_active == True
        )
        return await self._session.scalar(stmt) or 0

    async def set_default(self, owner_id: UUID, rate_chart_id: UUID) -> None:

        # 1. Remove current default
        await self._session.execute(
            update(RateChartAssignmentModel)
            .where(RateChartAssignmentModel.owner_id == owner_id)
            .values(is_default=False)
        )

        # 2. Make selected chart default
        result = await self._session.execute(
            update(RateChartAssignmentModel)
            .where(
                RateChartAssignmentModel.owner_id == owner_id,
                RateChartAssignmentModel.rate_chart_id == rate_chart_id,
            )
            .values(
                is_default=True,
            )
        )

        if result.rowcount != 1:
            raise RateChartAssignmentNotFoundException()

        await self._session.flush()

    async def delete_assignments_by_owner(
        self,
        owner_id: UUID,
    ) -> None:
        stmt = delete(RateChartAssignmentModel).where(RateChartAssignmentModel.owner_id == owner_id)
        await self._session.execute(stmt)

    # =========================================================
    # Chart Type
    # =========================================================

    async def get_chart_type(
        self,
        chart_id: UUID,
    ) -> RateChartType | None:
        return await self._session.scalar(
            select(RateChartModel.chart_type)
            .where(RateChartModel.id == chart_id)
        )

    # =========================================================
    # Grid (TEXT / CSV)
    # =========================================================

    async def resolve_grid_rate(
        self,
        chart_id: UUID,
        fat: float,
        snf: float,
    ) -> float:
        tolerance = self._GRID_TOLERANCE

        rate = await self._session.scalar(
            select(RateGridModel.rate)
            .where(
                RateGridModel.rate_chart_id == chart_id,
                RateGridModel.fat.between(
                    fat - tolerance,
                    fat + tolerance,
                ),
                RateGridModel.snf.between(
                    snf - tolerance,
                    snf + tolerance,
                ),
            )
            .order_by(RateGridModel.row_number)
            .limit(1)
        )

        return float(rate or 0.0)

    # =========================================================
    # Prodata
    # =========================================================

    async def resolve_prodata_rate(
        self,
        chart_id: UUID,
        fat: float,
        snf: float,
    ) -> float:
        row = (
            await self._session.execute(
                select(
                    ProdataRateRowModel.fat_rate_per_kg,
                    ProdataRateRowModel.snf_rate_per_kg,
                    ProdataRateRowModel.snf_cutoff,
                    ProdataRateRowModel.snf_deduction,
                )
                .where(
                    ProdataRateRowModel.rate_chart_id == chart_id,
                    ProdataRateRowModel.fat_min <= fat,
                    ProdataRateRowModel.fat_max >= fat,
                )
                .order_by(ProdataRateRowModel.row_number)
                .limit(1)
            )
        ).mappings().one_or_none()

        if row is None:
            return 0.0

        rate = (
            fat * float(row["fat_rate_per_kg"] or 0) / 100
            + snf * float(row["snf_rate_per_kg"] or 0) / 100
        )

        cutoff = row["snf_cutoff"]
        if cutoff is not None and snf < float(cutoff):
            rate -= (
                (float(cutoff) - snf)
                * float(row["snf_deduction"] or 0)
                * 10
            )

        return max(rate, 0.0)

    # =========================================================
    # Formula
    # =========================================================

    async def resolve_formula_rate(
        self,
        chart_id: UUID,
        fat: float,
        snf: float,
        milk_type: MilkType | None,
    ) -> float:
        config = await self._session.scalar(
            select(RateFormulaConfigModel)
            .where(RateFormulaConfigModel.rate_chart_id == chart_id)
            .limit(1)
        )

        if config is None:
            return 0.0

        if milk_type is MilkType.COW:
            std_fat = config.cow_standard_fat or 0
            std_snf = config.cow_standard_snf or 0
            std_rate = config.cow_standard_rate or 0
            fat_pct = config.cow_fat_percentage or 0
            snf_pct = config.cow_snf_percentage or 0
        else:
            std_fat = config.buffalo_standard_fat or 0
            std_snf = config.buffalo_standard_snf or 0
            std_rate = config.buffalo_standard_rate or 0
            fat_pct = config.buffalo_fat_percentage or 0
            snf_pct = config.buffalo_snf_percentage or 0

        if std_rate <= 0:
            return 0.0

        fat_component = (
            std_rate * fat_pct * fat / (std_fat * 100)
            if std_fat > 0
            else 0.0
        )

        snf_component = (
            std_rate * snf_pct * snf / (std_snf * 100)
            if std_snf > 0
            else 0.0
        )

        return fat_component + snf_component