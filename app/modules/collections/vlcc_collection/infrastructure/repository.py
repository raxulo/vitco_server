from typing import Any
from datetime import datetime, UTC
from sqlalchemy import func, select, exists, false, or_, true
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.domain.dto import (
    VlccCollectionListDto,
    VlccCollectionSummaryDto,
    VlccDetailedCollectionDto,
)

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.collections.vlcc_collection.domain.entities import VlccCollection
from app.modules.collections.vlcc_collection.domain.irepository import IVlccCollectionRepository
from app.modules.collections.vlcc_collection.infrastructure.mapper import VlccCollectionMapper
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.core.clock import now_naive_ist
from app.core.numeric import to_fixed_2


class VlccCollectionAccessScope:

    @staticmethod
    def condition(owner: CurrentUser):

        role = owner.role_type

        # Collections of the VLCCs the user controls (see `Hierarchy`)
        if role in (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC):
            vlcc_ids = Hierarchy.vlcc_ids(owner)
            return true() if vlcc_ids is None else VlccCollectionModel.vlcc_id.in_(vlcc_ids)

        if role == Role.FARMER:
            return exists(
                select(1)
                .select_from(FarmerModel)
                .join(
                    UserModel,
                    UserModel.id == FarmerModel.user_id,
                )
                .where(
                    FarmerModel.id == VlccCollectionModel.farmer_id,
                    UserModel.id == owner.id,
                )
                .correlate(VlccCollectionModel)
            )

        return false()


class VlccCollectionRepository(IVlccCollectionRepository):

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        entity: VlccCollection,
    ) -> None:
        model = VlccCollectionMapper.to_model(entity)
        self._session.add(model)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        entity: VlccCollection,
        owner: CurrentUser,
    ) -> None:
        stmt = (
            select(VlccCollectionModel)
            .where(
                VlccCollectionModel.id == entity.id,
                VlccCollectionAccessScope.condition(owner),
            )
        )
        model = await self._session.scalar(stmt)
        if model is None:
            return

        model.collection_number = entity.collection_number
        model.vlcc_id = entity.vlcc_id
        model.farmer_id = entity.farmer_id
        model.collected_at = entity.collected_at
        model.shift = entity.shift
        model.milk_type = entity.milk_type
        model.fat_percent = entity.fat_percent
        model.snf_percent = entity.snf_percent
        model.quantity = entity.quantity
        model.quantity_collection_mode = entity.quantity_collection_mode
        model.measurement_mode = entity.measurement_mode
        model.rate_per_unit = entity.rate_per_unit
        model.total_amount = entity.total_amount
        model.payment_mode = entity.payment_mode
        model.status = entity.status
        model.rank = entity.rank
        model.calibration_fat = entity.calibration_fat
        model.calibration_snf = entity.calibration_snf
        model.is_deleted = entity.is_deleted
        model.updated_at = entity.updated_at

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> None:
        stmt = (
            select(VlccCollectionModel)
            .where(
                VlccCollectionModel.id == id,
                VlccCollectionAccessScope.condition(owner),
            )
        )
        model = await self._session.scalar(stmt)
        if model is not None:
            model.is_deleted = True
            model.updated_at = now_naive_ist()
            await self._session.commit()

    async def delete_bulk(
        self,
        ids: list[UUID],
        owner: CurrentUser,
    ) -> list[UUID]:
        if not ids:
            return []

        stmt = select(VlccCollectionModel).where(
            VlccCollectionModel.id.in_(ids),
            VlccCollectionModel.is_deleted.is_(False),
            VlccCollectionAccessScope.condition(owner),
        )
        models = (await self._session.scalars(stmt)).all()
        deleted_ids: list[UUID] = []
        for model in models:
            model.is_deleted = True
            model.updated_at = now_naive_ist()
            model.updated_at = now_naive_ist()
            deleted_ids.append(model.id)

        if deleted_ids:
            await self._session.commit()

        return deleted_ids


    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> VlccCollection | None:
        stmt = select(VlccCollectionModel).where(
            VlccCollectionModel.id == id,
            VlccCollectionAccessScope.condition(owner),
        )
        model = await self._session.scalar(stmt)
        if model is None:
            return None
        return VlccCollectionMapper.to_entity(model)

    # =========================================================
    # LIST
    # =========================================================

    @staticmethod
    def _with_list_joins(stmt):
        """VLCC name, farmer code and farmer name (the farmer's user) for list / search / count."""
        return (
            stmt.join(VlccModel, VlccModel.id == VlccCollectionModel.vlcc_id)
            .join(FarmerModel, FarmerModel.id == VlccCollectionModel.farmer_id)
            .join(UserModel, UserModel.id == FarmerModel.user_id)
        )

    @staticmethod
    def _list_conditions(
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list:
        """
        Collection list filters:
        - keyword: VLCC name, farmer name or farmer code (any of them, case-insensitive)
        - date_from / date_to: collected_at range (date_to is exclusive)
        """
        conditions = [
            VlccCollectionAccessScope.condition(owner),
        ]
        keyword = (keyword or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    VlccModel.name.ilike(pattern),
                    UserModel.name.ilike(pattern),
                    FarmerModel.farmer_code.ilike(pattern),
                )
            )
        if date_from:
            conditions.append(VlccCollectionModel.collected_at >= date_from)
        if date_to:
            conditions.append(VlccCollectionModel.collected_at < date_to)
        return conditions

    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[VlccCollectionListDto]:

        stmt = (
            self._with_list_joins(
                select(
                    VlccCollectionModel,
                    VlccModel.name.label("vlcc_name"),
                    UserModel.name.label("farmer_name"),
                    FarmerModel.farmer_code.label("farmer_code"),
                )
            )
            .where(*self._list_conditions(owner, keyword, date_from, date_to))
            .order_by(
                VlccCollectionModel.collected_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return [
            VlccCollectionListDto(
                id=row.VlccCollectionModel.id,
                vlcc_id=row.VlccCollectionModel.vlcc_id,
                farmer_id=row.VlccCollectionModel.farmer_id,
                collected_at=row.VlccCollectionModel.collected_at,
                shift=row.VlccCollectionModel.shift,
                milk_type=row.VlccCollectionModel.milk_type,
                fat_percent=row.VlccCollectionModel.fat_percent,
                snf_percent=row.VlccCollectionModel.snf_percent,
                quantity=row.VlccCollectionModel.quantity,
                rate_per_unit=row.VlccCollectionModel.rate_per_unit,
                total_amount=row.VlccCollectionModel.total_amount,
                status=row.VlccCollectionModel.status,
                vlcc_name=row.vlcc_name,
                farmer_name=row.farmer_name,
                farmer_code=row.farmer_code,
                is_deleted=bool(row.VlccCollectionModel.is_deleted),
            )
            for row in result
        ]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[VlccCollectionListDto]:
        """VLCC name / farmer name / farmer code search (same rules as `list`)."""
        return await self.list(
            offset=offset,
            limit=limit,
            owner=owner,
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
        )

    # =========================================================
    # COUNT
    # =========================================================

    async def count(
        self,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        stmt = self._with_list_joins(select(func.count(VlccCollectionModel.id))).where(
            *self._list_conditions(owner, keyword, date_from, date_to)
        )
        return await self._session.scalar(stmt) or 0

    # =========================================================
    # COUNT SEARCH
    # =========================================================

    async def count_search(
        self,
        keyword: str,
        owner: CurrentUser,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        return await self.count(owner, keyword=keyword, date_from=date_from, date_to=date_to)

    # =========================================================
    # USER ID LOOKUPS
    # =========================================================

    async def get_vlcc_user_id(self, vlcc_id: UUID) -> UUID | None:
        stmt = select(VlccModel.user_id).where(VlccModel.id == vlcc_id)
        res = await self._session.scalar(stmt)
        if not res:
            stmt_alt = select(VlccModel.created_by).where(VlccModel.id == vlcc_id)
            res = await self._session.scalar(stmt_alt)
        return res

    async def farmer_belongs_to_vlcc(self, farmer_id: UUID, vlcc_id: UUID) -> bool:
        found = await self._session.scalar(
            select(FarmerModel.id).where(FarmerModel.id == farmer_id, FarmerModel.vlcc_id == vlcc_id)
        )
        return found is not None

    async def get_farmer_user_id(self, farmer_id: UUID) -> UUID | None:
        stmt = select(FarmerModel.user_id).where(FarmerModel.id == farmer_id)
        res = await self._session.scalar(stmt)
        if not res:
            stmt_alt = select(FarmerModel.created_by).where(FarmerModel.id == farmer_id)
            res = await self._session.scalar(stmt_alt)
        return res

    async def get_collection_summary(
        self,
        date_from: datetime,
        date_to: datetime,
        owner: CurrentUser,
        shift: CollectionShift | None = None,
    ) -> VlccCollectionSummaryDto:
        stmt = select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_quantity"),
            func.coalesce(func.sum(VlccCollectionModel.fat_percent * VlccCollectionModel.quantity), 0.0).label("total_fat_product"),
            func.coalesce(func.sum(VlccCollectionModel.snf_percent * VlccCollectionModel.quantity), 0.0).label("total_snf_product"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amount"),
            func.count(func.distinct(VlccCollectionModel.farmer_id)).label("total_farmer"),
        ).where(
            VlccCollectionModel.collected_at >= date_from,
            VlccCollectionModel.collected_at <= date_to,
            VlccCollectionModel.is_deleted == False,
            # Same visibility as the collection list
            VlccCollectionAccessScope.condition(owner),
        )

        if shift is not None:
            stmt = stmt.where(VlccCollectionModel.shift == shift)

        row = (await self._session.execute(stmt)).one()

        total_quantity = float(row.total_quantity or 0.0)
        total_amount = float(row.total_amount or 0.0)
        total_fat_product = float(row.total_fat_product or 0.0)
        total_snf_product = float(row.total_snf_product or 0.0)
        total_farmer = int(row.total_farmer or 0)

        avg_fat = to_fixed_2(total_fat_product / total_quantity) if total_quantity > 0 else 0.0
        avg_snf = to_fixed_2(total_snf_product / total_quantity) if total_quantity > 0 else 0.0
        avg_rate = to_fixed_2(total_amount / total_quantity) if total_quantity > 0 else 0.0

        return VlccCollectionSummaryDto(
            total_quantity=total_quantity,
            total_amount=total_amount,
            avg_fat=avg_fat,
            avg_snf=avg_snf,
            avg_rate=avg_rate,
            active_users=total_farmer,
        )

    # =========================================================
    # GET DETAILED COLLECTION LIST
    # =========================================================

    async def get_detailed_collection_list(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: CollectionShift | None = None,
        offset: int = 0,
        limit: int = 50,
        vlcc_id: UUID | None = None,
        farmer_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
    ) -> list[VlccDetailedCollectionDto]:
        conditions = self._collection_conditions(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            vlcc_id=vlcc_id,
            farmer_id=farmer_id,
            owner=owner,
            is_deleted=is_deleted,
        )

        stmt = (
            select(
                VlccCollectionModel,
                FarmerModel.farmer_code.label("member_code"),
                UserModel.name.label("member_name"),
            )
            .outerjoin(FarmerModel, FarmerModel.id == VlccCollectionModel.farmer_id)
            .outerjoin(UserModel, UserModel.id == FarmerModel.user_id)
            .where(*conditions)
            .order_by(
                VlccCollectionModel.collected_at.desc(),
                VlccCollectionModel.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        items = [
            VlccDetailedCollectionDto(
                id=row.VlccCollectionModel.id,
                collection_by=row.VlccCollectionModel.vlcc_id,
                collection_to=row.VlccCollectionModel.farmer_id,
                collected_at=row.VlccCollectionModel.collected_at,
                member_code=row.member_code,
                member_name=row.member_name,
                role=Role.FARMER,
                shift=row.VlccCollectionModel.shift,
                milk_type=row.VlccCollectionModel.milk_type,
                quantity=row.VlccCollectionModel.quantity,
                quantity_collection_mode=row.VlccCollectionModel.quantity_collection_mode,
                measurement_mode=row.VlccCollectionModel.measurement_mode,
                fat_percent=row.VlccCollectionModel.fat_percent,
                snf_percent=row.VlccCollectionModel.snf_percent,
                clr_value=None,
                rate_per_unit=row.VlccCollectionModel.rate_per_unit,
                total_amount=row.VlccCollectionModel.total_amount,
                payment_mode=row.VlccCollectionModel.payment_mode,
                status=row.VlccCollectionModel.status,
                sample_number=None,
                can_count=None,
                detection_value=None,
                mcc_type=None,
                rank=row.VlccCollectionModel.rank,
                calibration_fat=row.VlccCollectionModel.calibration_fat,
                calibration_snf=row.VlccCollectionModel.calibration_snf,
                is_deleted=row.VlccCollectionModel.is_deleted,
            )
            for row in result
        ]

        return items

    async def get_total_collection_count(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: CollectionShift | None = None,
        vlcc_id: UUID | None = None,
        farmer_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
    ) -> int:
        conditions = self._collection_conditions(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            vlcc_id=vlcc_id,
            farmer_id=farmer_id,
            owner=owner,
            is_deleted=is_deleted,
        )

        total_count = await self._session.scalar(
            select(func.count(VlccCollectionModel.id)).where(*conditions)
        ) or 0

        return total_count

    def _collection_conditions(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: CollectionShift | None = None,
        vlcc_id: UUID | None = None,
        farmer_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
    ) -> list:
        return [
            *([VlccCollectionModel.is_deleted.is_(is_deleted)] if is_deleted is not None else []),
            *([VlccCollectionModel.vlcc_id == vlcc_id] if vlcc_id else []),
            *([VlccCollectionModel.farmer_id == farmer_id] if farmer_id else []),
            *([VlccCollectionModel.collected_at >= date_from] if date_from else []),
            *([VlccCollectionModel.collected_at <= date_to] if date_to else []),
            *([VlccCollectionModel.shift == shift] if shift else []),
            *([VlccCollectionAccessScope.condition(owner)] if owner else []),
        ]