from typing import Any
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.admin.infrastructure import models
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.collections.mcc_collection.domain.dto import MccSampleResult
from app.modules.collections.mcc_collection.application.command import GetCollectionBySampleNumberQuery
from app.modules.collections.mcc_collection.domain.dto import (
    MccCollectionResult,
    MccCollectionListDto,
    MccCollectionSummaryDto,
    MccDetailedCollectionDto,
)
from datetime import datetime, UTC, time, timedelta
from app.core.clock import day_bounds_ist, now_naive_ist

from app.modules.mcc.domain.enums import MccType
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.collections.mcc_collection.application.command import (
    GetNextSampleNumberQuery,
)
from sqlalchemy import func

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.core.numeric import to_fixed_2
from app.modules.collections.mcc_collection.domain.entities import MccCollection
from app.modules.collections.mcc_collection.domain.irepository import IMccCollectionRepository
from app.modules.collections.mcc_collection.infrastructure.mapper import MccCollectionMapper
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel

from sqlalchemy import exists, false, or_, select, true

class MccCollectionAccessScope:

    @staticmethod
    def condition(owner: CurrentUser):

        role = owner.role_type

        # =====================================================
        # SUPER ADMIN / ADMIN / SUB ADMIN / MCC
        # Collections received at the MCCs the user controls
        # (see `Hierarchy`; an MCC user controls its own MCC)
        # =====================================================
        if role in (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC):
            mcc_ids = Hierarchy.mcc_ids(owner)
            return true() if mcc_ids is None else MccCollectionModel.mcc_id.in_(mcc_ids)

        # =====================================================
        # VLCC
        # Only own VLCC collection
        # =====================================================
        if role in (Role.VLCC, Role.VLCC_FARMER):
            return exists(
                select(1)
                .select_from(VlccModel)
                .where(
                    VlccModel.id == MccCollectionModel.vlcc_id,
                    VlccModel.user_id == owner.id,
                )
                .correlate(MccCollectionModel)
            )

        return false()

class MccCollectionRepository(IMccCollectionRepository):

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
        entity: MccCollection,
    ) -> None:
        model = MccCollectionMapper.to_model(entity)
        self._session.add(model)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(self, entity: MccCollection,owner: CurrentUser) -> None:
        # model = await self._session.get(MccCollectionModel, entity.id)
        stmt = (
            select(MccCollectionModel)
            .where(
                MccCollectionModel.id == entity.id,
                MccCollectionAccessScope.condition(owner),
            )
        )

        model = await self._session.scalar(stmt)

        if model is None:
            return

        model.collection_number = entity.collection_number
        model.mcc_id = entity.mcc_id
        model.vlcc_id = entity.vlcc_id
        model.collected_at = entity.collected_at
        model.shift = entity.shift
        model.milk_type = entity.milk_type
        model.fat_percent = entity.fat_percent
        model.snf_percent = entity.snf_percent
        model.clr_value = entity.clr_value
        model.quantity = entity.quantity
        model.quantity_collection_mode = entity.quantity_collection_mode
        model.measurement_mode = entity.measurement_mode
        model.rate_per_unit = entity.rate_per_unit
        model.total_amount = entity.total_amount
        model.payment_mode = entity.payment_mode
        model.status = entity.status
        model.rank = entity.rank
        model.sample_number = entity.sample_number
        model.can_count = entity.can_count
        model.detection_value = entity.detection_value
        model.calibration_fat = entity.calibration_fat
        model.calibration_snf = entity.calibration_snf
        model.is_deleted = entity.is_deleted
        model.updated_at = entity.updated_at

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(self, id: UUID,owner: CurrentUser) -> None:
        stmt = (
            select(MccCollectionModel)
            .where(
                MccCollectionModel.id == id,
                MccCollectionAccessScope.condition(owner),
            )
        )

        model = await self._session.scalar(stmt)

        if model is None:
            return

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

        stmt = select(MccCollectionModel).where(
            MccCollectionModel.id.in_(ids),
            MccCollectionModel.is_deleted.is_(False),
            MccCollectionAccessScope.condition(owner),
        )
        models = (await self._session.scalars(stmt)).all()
        deleted_ids: list[UUID] = []
        for model in models:
            model.is_deleted = True
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
    ) -> MccCollection | None:

        stmt = (
            select(MccCollectionModel)
            .where(
                MccCollectionModel.id == id,
                MccCollectionAccessScope.condition(owner),
            )
        )

        model = await self._session.scalar(stmt)

        return (
            MccCollectionMapper.to_entity(model)
            if model
            else None
        )

    # =========================================================
    # LIST
    # =========================================================

    @staticmethod
    def _list_conditions(
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list:
        """
        Collection list filters (MccModel joined, VlccModel outer-joined):
        - keyword: MCC name / code or VLCC name / code (any of them, case-insensitive)
        - date_from / date_to: collected_at range (date_to is exclusive)
        """
        conditions = [
            MccCollectionAccessScope.condition(owner),
        ]
        keyword = (keyword or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    MccModel.name.ilike(pattern),
                    MccModel.code.ilike(pattern),
                    VlccModel.name.ilike(pattern),
                    VlccModel.vlcc_code.ilike(pattern),
                )
            )
        if date_from:
            conditions.append(MccCollectionModel.collected_at >= date_from)
        if date_to:
            conditions.append(MccCollectionModel.collected_at < date_to)
        return conditions

    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MccCollectionListDto]:
        stmt = (
            select(
                MccCollectionModel.id,
                MccCollectionModel.mcc_id,
                MccCollectionModel.vlcc_id,
                MccCollectionModel.collected_at,
                MccCollectionModel.shift,
                MccCollectionModel.milk_type,
                MccCollectionModel.quantity,
                MccCollectionModel.total_amount,
                MccCollectionModel.status,
                MccCollectionModel.fat_percent,
                MccCollectionModel.snf_percent,
                MccCollectionModel.clr_value,
                MccCollectionModel.sample_number,
                MccCollectionModel.can_count,
                MccCollectionModel.rate_per_unit,
                MccCollectionModel.payment_mode,
                MccCollectionModel.quantity_collection_mode,
                MccCollectionModel.measurement_mode,
                MccModel.name.label("mcc_name"),
                MccModel.code.label("mcc_code"),
                VlccModel.name.label("vlcc_name"),
                VlccModel.vlcc_code.label("vlcc_uic_code"),
                MccCollectionModel.is_deleted,
            )
            .select_from(MccCollectionModel)
            .join(MccModel, MccModel.id == MccCollectionModel.mcc_id)
            .outerjoin(VlccModel, VlccModel.id == MccCollectionModel.vlcc_id)
            .where(*self._list_conditions(owner, keyword, date_from, date_to))
            .order_by(MccCollectionModel.collected_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            MccCollectionListDto(**row)
            for row in result.mappings()
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
    ) -> list[MccCollectionListDto]:
        """MCC name / code or VLCC name / code search (same rules as `list`)."""
        return await self.list(
            offset=offset, limit=limit, owner=owner,
            keyword=keyword, date_from=date_from, date_to=date_to,
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
        stmt = (
            select(func.count(MccCollectionModel.id))
            .select_from(MccCollectionModel)
            .join(MccModel, MccModel.id == MccCollectionModel.mcc_id)
            .outerjoin(VlccModel, VlccModel.id == MccCollectionModel.vlcc_id)
            .where(*self._list_conditions(owner, keyword, date_from, date_to))
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

    async def genext_sample_number(self, query: GetNextSampleNumberQuery) -> MccSampleResult:
        day_start, day_end = day_bounds_ist(query.collected_at)

        stmt = (
            select(
                MccModel.sample_start,
                MccModel.sample_end,
                func.max(MccCollectionModel.sample_number).label("max_sample_number"),
            )
            .select_from(MccModel)
            .outerjoin(
                MccCollectionModel,
                (
                    (MccCollectionModel.mcc_id == MccModel.id)
                    & (MccCollectionModel.collected_at >= day_start)
                    & (MccCollectionModel.collected_at < day_end)
                    & (MccCollectionModel.shift == query.shift)
                ),
            )
            .where(MccModel.id == query.mcc_id)
            .group_by(
                MccModel.sample_start,
                MccModel.sample_end,
            )
        )

        row = (await self._session.execute(stmt)).one_or_none()

        if row is None:
            return MccSampleResult(
                sample_start=0, sample_end=0, 
                is_mcc_exists=False, next_sample_number=0
            )

        print("MMMMMMM: ", row.max_sample_number, row.sample_start, row.sample_end, day_start, day_end)

        next_sample = (
            row.sample_start
            if row.max_sample_number is None
            else row.max_sample_number + 1
        )

        return MccSampleResult(
            sample_start=row.sample_start,
            sample_end=row.sample_end,
            is_mcc_exists=True,
            next_sample_number=next_sample
        )

    async def get_collection_by_sample_number(
        self,
        query: GetCollectionBySampleNumberQuery,
    ) -> MccCollectionResult | None:

        start, end = day_bounds_ist(query.collected_at)

        stmt = (
            select(
                MccModel.id.label("mcc_id"),
                MccModel.name.label("mcc_name"),
                MccCollectionModel.id.label("collection_id"),
                MccCollectionModel.quantity,
                MccCollectionModel.can_count,
                MccCollectionModel.vlcc_id,
                VlccModel.name.label("vlcc_name"),
                MccCollectionModel.is_deleted,
                MccCollectionModel.quantity_collection_mode
            )
            .select_from(MccCollectionModel)
            .join(
                MccModel,
                MccModel.id == MccCollectionModel.mcc_id,
            )
            .outerjoin(
                VlccModel,
                VlccModel.id == MccCollectionModel.vlcc_id,
            )
            .where(
                MccModel.created_by == (
                    select(MccModel.created_by)
                    .where(MccModel.id == query.mcc_id)
                    .scalar_subquery()
                ),
                MccModel.mcc_type == MccType.WEIGHT,
                MccCollectionModel.sample_number == query.sample_number,
                MccCollectionModel.collected_at >= start,
                MccCollectionModel.collected_at < end,
               MccCollectionModel.shift == query.shift
            )
            .limit(1)
        )

        result = (await self._session.execute(stmt)).mappings().one_or_none()
        
        if result is None:
            return None

        vlcc_id = result.get("vlcc_id")
        mcc_id = result.get("mcc_id")

        return MccCollectionResult(
            mcc_name=result.get("mcc_name"),
            mcc_id=mcc_id,
            collection_id=result.get("collection_id"),
            quantity=result.get("quantity"),
            can_count=result.get("can_count"),
            vlcc_id=vlcc_id,
            vlcc_name=result.get("vlcc_name"),
            is_deleted=result.get("is_deleted"),
            quantity_collection_mode=result.get("quantity_collection_mode"),
        )

    async def sample_number_problem(
        self,
        query: GetCollectionBySampleNumberQuery,
        exclude_collection_id: UUID | None = None,
    ) -> str | None:
        """
        Validate a sample number entered at a non-weight MCC, across every MCC
        of the same owner (creator):

        - "not_exists": outside the sample range of all the owner's weight MCCs
        - "taken": another non-weight MCC of the owner already used it on the
          same date and shift
        - None: usable (also for weight MCCs, which issue the samples)
        """
        mcc = (await self._session.execute(
            select(MccModel.created_by, MccModel.mcc_type).where(MccModel.id == query.mcc_id)
        )).one_or_none()
        if mcc is None or mcc.mcc_type == MccType.WEIGHT or query.sample_number is None:
            return None

        in_range = await self._session.scalar(
            select(exists().where(
                MccModel.created_by == mcc.created_by,
                MccModel.mcc_type == MccType.WEIGHT,
                MccModel.is_deleted.is_(False),
                MccModel.sample_start <= query.sample_number,
                MccModel.sample_end >= query.sample_number,
            ))
        )
        if not in_range:
            return "not_exists"

        day_start, day_end = day_bounds_ist(query.collected_at)
        taken = (
            select(MccCollectionModel.id)
            .join(MccModel, MccModel.id == MccCollectionModel.mcc_id)
            .where(
                MccModel.created_by == mcc.created_by,
                MccModel.mcc_type != MccType.WEIGHT,
                MccCollectionModel.sample_number == query.sample_number,
                MccCollectionModel.shift == query.shift,
                MccCollectionModel.collected_at >= day_start,
                MccCollectionModel.collected_at < day_end,
                MccCollectionModel.is_deleted.is_(False),
            )
        )
        if exclude_collection_id is not None:
            taken = taken.where(MccCollectionModel.id != exclude_collection_id)
        if await self._session.scalar(select(exists(taken))):
            return "taken"
        return None

    async def is_sample_number_collected(
        self,
        query: GetCollectionBySampleNumberQuery,
    ) -> bool:
        """
        Check whether a collection already exists for the given mcc_id, shift, date, and sample_number.
        """
        mcc_id = query.mcc_id
        sample_number = query.sample_number
        shift = query.shift
        collected_at = query.collected_at

        if mcc_id is None or sample_number is None:
            raise ValueError("mcc_id and sample_number are required")

        # Parse date range using central IST helper
        day_start, day_end = day_bounds_ist(collected_at)

        stmt = select(
            exists().where(
                MccCollectionModel.mcc_id == mcc_id,
                MccCollectionModel.sample_number == sample_number,
                MccCollectionModel.shift == shift,
                MccCollectionModel.collected_at >= day_start,
                MccCollectionModel.collected_at < day_end,
                MccCollectionModel.is_deleted == False,
            )
        )

        result = await self._session.scalar(stmt)
        return bool(result)

    # =========================================================
    # USER ID LOOKUPS
    # =========================================================

    async def get_mcc_user_id(self, mcc_id: UUID) -> UUID | None:
        stmt = select(MccModel.user_id).where(MccModel.id == mcc_id)
        res = await self._session.scalar(stmt)
        if not res:
            stmt_alt = select(MccModel.created_by).where(MccModel.id == mcc_id)
            res = await self._session.scalar(stmt_alt)
        return res

    async def get_vlcc_user_id(self, vlcc_id: UUID) -> UUID | None:
        stmt = select(VlccModel.user_id).where(VlccModel.id == vlcc_id)
        res = await self._session.scalar(stmt)
        if not res:
            stmt_alt = select(VlccModel.created_by).where(VlccModel.id == vlcc_id)
            res = await self._session.scalar(stmt_alt)
        return res

    async def get_collection_summary(
        self,
        date_from: datetime,
        date_to: datetime,
        owner: CurrentUser,
        shift: CollectionShift | None = None,
        exclude_zero_quality: bool = False,
    ) -> MccCollectionSummaryDto:
        stmt = select(
            func.coalesce(func.sum(MccCollectionModel.quantity), 0.0).label("total_quantity"),
            func.coalesce(func.sum(MccCollectionModel.fat_percent * MccCollectionModel.quantity), 0.0).label("total_fat_product"),
            func.coalesce(func.sum(MccCollectionModel.snf_percent * MccCollectionModel.quantity), 0.0).label("total_snf_product"),
            func.coalesce(func.sum(MccCollectionModel.total_amount), 0.0).label("total_amount"),
            func.count(func.distinct(MccCollectionModel.vlcc_id)).label("total_vlcc"),
        ).where(
            MccCollectionModel.collected_at >= date_from,
            MccCollectionModel.collected_at <= date_to,
            MccCollectionModel.is_deleted == False,
            # Same visibility as the collection list
            MccCollectionAccessScope.condition(owner),
        )

        if shift is not None:
            stmt = stmt.where(MccCollectionModel.shift == shift)

        if exclude_zero_quality:
            stmt = stmt.where(self._has_quality_reading())

        row = (await self._session.execute(stmt)).one()

        total_quantity = float(row.total_quantity or 0.0)
        total_amount = float(row.total_amount or 0.0)
        total_fat_product = float(row.total_fat_product or 0.0)
        total_snf_product = float(row.total_snf_product or 0.0)
        total_vlcc = int(row.total_vlcc or 0)

        avg_fat = to_fixed_2(total_fat_product / total_quantity) if total_quantity > 0 else 0.0
        avg_snf = to_fixed_2(total_snf_product / total_quantity) if total_quantity > 0 else 0.0
        avg_rate = to_fixed_2(total_amount / total_quantity) if total_quantity > 0 else 0.0

        return MccCollectionSummaryDto(
            total_quantity=total_quantity,
            total_amount=total_amount,
            avg_fat=avg_fat,
            avg_snf=avg_snf,
            avg_rate=avg_rate,
            active_users=total_vlcc,
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
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
        exclude_zero_quality: bool = False,
    ) -> list[MccDetailedCollectionDto]:
        conditions = self._collection_conditions(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            mcc_id=mcc_id,
            vlcc_id=vlcc_id,
            owner=owner,
            is_deleted=is_deleted,
            exclude_zero_quality=exclude_zero_quality,
        )

        stmt = (
            select(
                MccCollectionModel,
                VlccModel.vlcc_code.label("member_code"),
                VlccModel.name.label("member_name"),
            )
            .outerjoin(
                VlccModel,
                VlccModel.id == MccCollectionModel.vlcc_id,
            )
            .where(*conditions)
            .order_by(
                MccCollectionModel.collected_at.desc(),
                MccCollectionModel.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        items = [
            MccDetailedCollectionDto(
                id=row.MccCollectionModel.id,
                collection_by=row.MccCollectionModel.mcc_id,
                collection_to=row.MccCollectionModel.vlcc_id,
                collected_at=row.MccCollectionModel.collected_at,
                member_code=row.member_code,
                member_name=row.member_name,
                role=Role.VLCC,
                shift=row.MccCollectionModel.shift,
                milk_type=row.MccCollectionModel.milk_type,
                quantity=row.MccCollectionModel.quantity,
                quantity_collection_mode=row.MccCollectionModel.quantity_collection_mode,
                measurement_mode=row.MccCollectionModel.measurement_mode,
                fat_percent=row.MccCollectionModel.fat_percent,
                snf_percent=row.MccCollectionModel.snf_percent,
                clr_value=row.MccCollectionModel.clr_value,
                rate_per_unit=row.MccCollectionModel.rate_per_unit,
                total_amount=row.MccCollectionModel.total_amount,
                payment_mode=row.MccCollectionModel.payment_mode,
                status=row.MccCollectionModel.status,
                sample_number=row.MccCollectionModel.sample_number,
                can_count=row.MccCollectionModel.can_count,
                detection_value=row.MccCollectionModel.detection_value,
                mcc_type=None,
                rank=row.MccCollectionModel.rank,
                calibration_fat=row.MccCollectionModel.calibration_fat,
                calibration_snf=row.MccCollectionModel.calibration_snf,
                is_deleted=row.MccCollectionModel.is_deleted,
            )
            for row in result
        ]

        return items

    async def get_total_collection_count(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: CollectionShift | None = None,
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
        exclude_zero_quality: bool = False,
    ) -> int:
        conditions = self._collection_conditions(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            mcc_id=mcc_id,
            vlcc_id=vlcc_id,
            owner=owner,
            is_deleted=is_deleted,
            exclude_zero_quality=exclude_zero_quality,
        )

        total_count = await self._session.scalar(
            select(func.count(MccCollectionModel.id)).where(*conditions)
        ) or 0

        return total_count

    @staticmethod
    def _has_quality_reading():
        """Rows where both FAT and SNF are 0 (or missing) carry no quality reading."""
        return or_(
            func.coalesce(MccCollectionModel.fat_percent, 0) != 0,
            func.coalesce(MccCollectionModel.snf_percent, 0) != 0,
        )

    def _collection_conditions(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: CollectionShift | None = None,
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
        exclude_zero_quality: bool = False,
    ) -> list:
        return [
            *([self._has_quality_reading()] if exclude_zero_quality else []),
            *([MccCollectionModel.is_deleted.is_(is_deleted)] if is_deleted is not None else []),
            *([MccCollectionModel.mcc_id == mcc_id] if mcc_id else []),
            *([MccCollectionModel.vlcc_id == vlcc_id] if vlcc_id else []),
            *([MccCollectionModel.collected_at >= date_from] if date_from else []),
            *([MccCollectionModel.collected_at <= date_to] if date_to else []),
            *([MccCollectionModel.shift == shift] if shift else []),
            *([MccCollectionAccessScope.condition(owner)] if owner else []),
        ]