from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.authentication import CurrentUser
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.vlcc.infrastructure.models import VlccModel
from sqlalchemy import func
from app.core.database.manager import DatabaseManager
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.domain.dispatch_dto import (
    ShiftComparisonItemDto,
    ComparisonSummaryDto,
)
from app.modules.collections.vlcc_collection.domain.dispatch_entities import Dispatch
from app.modules.collections.vlcc_collection.domain.idispatch_repository import IDispatchRepository
from app.modules.collections.vlcc_collection.infrastructure.dispatch_mapper import DispatchMapper
from app.modules.collections.vlcc_collection.infrastructure.models import DispatchModel, VlccCollectionModel


class DispatchAccessScope:
    """Dispatches of the VLCCs a user controls — rules in `Hierarchy`."""

    @staticmethod
    def condition(owner: CurrentUser):
        vlcc_ids = Hierarchy.vlcc_ids(owner)
        return true() if vlcc_ids is None else DispatchModel.vlcc_id.in_(vlcc_ids)


class DispatchRepository(IDispatchRepository):
    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    async def create(self, entity: Dispatch) -> None:
        model = DispatchMapper.to_model(entity)
        self._session.add(model)

    async def get(self, id: UUID, owner: CurrentUser) -> Dispatch | None:
        model = await self._session.scalar(
            select(DispatchModel).where(DispatchModel.id == id, DispatchAccessScope.condition(owner))
        )
        return DispatchMapper.to_entity(model) if model else None

    async def get_with_vlcc(self, id: UUID, owner: CurrentUser) -> tuple[Dispatch, str] | None:
        stmt = (
            select(DispatchModel, VlccModel.name)
            .join(VlccModel, VlccModel.id == DispatchModel.vlcc_id)
            .where(DispatchModel.id == id, DispatchAccessScope.condition(owner))
        )
        res = (await self._session.execute(stmt)).first()
        if res is None:
            return None
        return (DispatchMapper.to_entity(res[0]), res[1])

    async def vlcc_in_scope(self, vlcc_id: UUID, owner: CurrentUser) -> bool:
        """Whether the user may record / change dispatches for this VLCC."""
        vlcc_ids = Hierarchy.vlcc_ids(owner)
        stmt = select(VlccModel.id).where(VlccModel.id == vlcc_id)
        if vlcc_ids is not None:
            stmt = stmt.where(VlccModel.id.in_(vlcc_ids))
        return await self._session.scalar(stmt) is not None

    async def update(self, entity: Dispatch) -> None:
        model = await self._session.get(DispatchModel, entity.id)
        if model is None:
            return
        model.vlcc_id = entity.vlcc_id
        model.collected_at = entity.collected_at
        model.shift = entity.shift
        model.fat_percent = entity.fat_percent
        model.snf_percent = entity.snf_percent
        model.quantity = entity.quantity
        model.can_count = entity.can_count
        model.quantity_collection_mode = entity.quantity_collection_mode
        model.measurement_mode = entity.measurement_mode
        model.updated_at = entity.updated_at

    async def delete(self, id: UUID) -> None:
        model = await self._session.get(DispatchModel, id)
        if model:
            await self._session.delete(model)

    async def list(
        self,
        owner: CurrentUser,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 1,
        size: int = 20,
    ) -> list[tuple[Dispatch, str]]:
        stmt = (
            select(DispatchModel, VlccModel.name)
            .join(VlccModel, VlccModel.id == DispatchModel.vlcc_id)
            .where(DispatchAccessScope.condition(owner))
        )
        if vlcc_id:
            stmt = stmt.where(DispatchModel.vlcc_id == vlcc_id)
        if shift is not None:
            stmt = stmt.where(DispatchModel.shift == shift)
        if start_date:
            stmt = stmt.where(DispatchModel.collected_at >= start_date)
        if end_date:
            stmt = stmt.where(DispatchModel.collected_at <= end_date)

        stmt = stmt.order_by(DispatchModel.collected_at.desc())
        stmt = stmt.offset((page - 1) * size).limit(size)

        res = await self._session.execute(stmt)
        return [
            (DispatchMapper.to_entity(row[0]), row[1])
            for row in res.all()
        ]

    async def count(
        self,
        owner: CurrentUser,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        stmt = (
            select(func.count(DispatchModel.id))
            .join(VlccModel, VlccModel.id == DispatchModel.vlcc_id)
            .where(DispatchAccessScope.condition(owner))
        )
        if vlcc_id:
            stmt = stmt.where(DispatchModel.vlcc_id == vlcc_id)
        if shift is not None:
            stmt = stmt.where(DispatchModel.shift == shift)
        if start_date:
            stmt = stmt.where(DispatchModel.collected_at >= start_date)
        if end_date:
            stmt = stmt.where(DispatchModel.collected_at <= end_date)
        res = await self._session.scalar(stmt)
        return res or 0

    async def get_detail_with_vlcc(self, vlcc_id: UUID):
        stmt = select(DispatchModel).where(DispatchModel.vlcc_id == vlcc_id)
        res = await self._session.execute(stmt)
        return [DispatchMapper.to_entity(row) for row in res.scalars()]

    @staticmethod
    def _parse_date(val) -> date:
        if isinstance(val, date):
            return val
        return date.fromisoformat(str(val)[:10])

    @staticmethod
    def _normalize_shift(val) -> CollectionShift:
        if isinstance(val, CollectionShift):
            return val
        try:
            return CollectionShift(int(val))
        except (ValueError, TypeError):
            return CollectionShift[str(val).upper()]

    async def get_comparison(
        self,
        owner: CurrentUser,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[ShiftComparisonItemDto], ComparisonSummaryDto]:
        vlcc_ids = Hierarchy.vlcc_ids(owner)

        # 1. Collection Aggregates
        day_c = func.date(VlccCollectionModel.collected_at)
        c_stmt = (
            select(
                day_c.label("day"),
                VlccCollectionModel.shift.label("shift"),
                VlccCollectionModel.vlcc_id.label("vlcc_id"),
                VlccModel.name.label("vlcc_name"),
                func.coalesce(func.sum(VlccCollectionModel.quantity), 0).label("qty"),
                func.coalesce(
                    func.sum(VlccCollectionModel.quantity * func.coalesce(VlccCollectionModel.fat_percent, 0)), 0
                ).label("fat_prod"),
                func.coalesce(
                    func.sum(VlccCollectionModel.quantity * func.coalesce(VlccCollectionModel.snf_percent, 0)), 0
                ).label("snf_prod"),
                func.count(VlccCollectionModel.id).label("c_count"),
                func.count(func.distinct(VlccCollectionModel.farmer_id)).label("f_count"),
            )
            .join(VlccModel, VlccModel.id == VlccCollectionModel.vlcc_id)
            .where(VlccCollectionModel.is_deleted == False)
        )
        if vlcc_ids is not None:
            c_stmt = c_stmt.where(VlccCollectionModel.vlcc_id.in_(vlcc_ids))
        if vlcc_id:
            c_stmt = c_stmt.where(VlccCollectionModel.vlcc_id == vlcc_id)
        if shift is not None:
            c_stmt = c_stmt.where(VlccCollectionModel.shift == shift)
        if start_date:
            c_stmt = c_stmt.where(VlccCollectionModel.collected_at >= start_date)
        if end_date:
            c_stmt = c_stmt.where(VlccCollectionModel.collected_at <= end_date)

        c_stmt = c_stmt.group_by(day_c, VlccCollectionModel.shift, VlccCollectionModel.vlcc_id, VlccModel.name)
        c_rows = (await self._session.execute(c_stmt)).all()

        # 2. Dispatch Aggregates
        day_d = func.date(DispatchModel.collected_at)
        d_stmt = (
            select(
                day_d.label("day"),
                DispatchModel.shift.label("shift"),
                DispatchModel.vlcc_id.label("vlcc_id"),
                VlccModel.name.label("vlcc_name"),
                func.coalesce(func.sum(DispatchModel.quantity), 0).label("qty"),
                func.coalesce(
                    func.sum(DispatchModel.quantity * func.coalesce(DispatchModel.fat_percent, 0)), 0
                ).label("fat_prod"),
                func.coalesce(
                    func.sum(DispatchModel.quantity * func.coalesce(DispatchModel.snf_percent, 0)), 0
                ).label("snf_prod"),
                func.coalesce(func.sum(DispatchModel.can_count), 0).label("can_count"),
                func.count(DispatchModel.id).label("d_count"),
            )
            .join(VlccModel, VlccModel.id == DispatchModel.vlcc_id)
            .where(DispatchAccessScope.condition(owner))
        )
        if vlcc_id:
            d_stmt = d_stmt.where(DispatchModel.vlcc_id == vlcc_id)
        if shift is not None:
            d_stmt = d_stmt.where(DispatchModel.shift == shift)
        if start_date:
            d_stmt = d_stmt.where(DispatchModel.collected_at >= start_date)
        if end_date:
            d_stmt = d_stmt.where(DispatchModel.collected_at <= end_date)

        d_stmt = d_stmt.group_by(day_d, DispatchModel.shift, DispatchModel.vlcc_id, VlccModel.name)
        d_rows = (await self._session.execute(d_stmt)).all()

        collection_map: dict[tuple, dict] = {}
        for row in c_rows:
            d_val = self._parse_date(row.day)
            s_val = self._normalize_shift(row.shift)
            key = (d_val, s_val, row.vlcc_id)
            collection_map[key] = {
                "vlcc_name": row.vlcc_name,
                "qty": Decimal(str(row.qty or 0)),
                "fat_prod": Decimal(str(row.fat_prod or 0)),
                "snf_prod": Decimal(str(row.snf_prod or 0)),
                "c_count": int(row.c_count or 0),
                "f_count": int(row.f_count or 0),
            }

        dispatch_map: dict[tuple, dict] = {}
        for row in d_rows:
            d_val = self._parse_date(row.day)
            s_val = self._normalize_shift(row.shift)
            key = (d_val, s_val, row.vlcc_id)
            dispatch_map[key] = {
                "vlcc_name": row.vlcc_name,
                "qty": Decimal(str(row.qty or 0)),
                "fat_prod": Decimal(str(row.fat_prod or 0)),
                "snf_prod": Decimal(str(row.snf_prod or 0)),
                "can_count": int(row.can_count or 0),
                "d_count": int(row.d_count or 0),
            }

        all_keys = list(set(collection_map.keys()) | set(dispatch_map.keys()))
        all_keys.sort(
            key=lambda k: (k[0], k[1].value if isinstance(k[1], CollectionShift) else int(k[1])),
            reverse=True,
        )

        items: list[ShiftComparisonItemDto] = []
        tot_c_qty = Decimal("0.00")
        tot_d_qty = Decimal("0.00")
        tot_c_fat_prod = Decimal("0.00")
        tot_c_snf_prod = Decimal("0.00")
        tot_d_fat_prod = Decimal("0.00")
        tot_d_snf_prod = Decimal("0.00")
        tot_cans = 0
        tot_c_count = 0

        for key in all_keys:
            d_val, s_val, v_id = key
            c_data = collection_map.get(key)
            d_data = dispatch_map.get(key)

            v_name = (c_data["vlcc_name"] if c_data else None) or (d_data["vlcc_name"] if d_data else "")
            c_qty = c_data["qty"] if c_data else Decimal("0.00")
            c_fat = round(c_data["fat_prod"] / c_qty, 1) if (c_data and c_qty > 0) else Decimal("0.0")
            c_snf = round(c_data["snf_prod"] / c_qty, 1) if (c_data and c_qty > 0) else Decimal("0.0")
            c_cnt = c_data["c_count"] if c_data else 0
            f_cnt = c_data["f_count"] if c_data else 0

            d_qty = d_data["qty"] if d_data else Decimal("0.00")
            d_fat = round(d_data["fat_prod"] / d_qty, 1) if (d_data and d_qty > 0) else Decimal("0.0")
            d_snf = round(d_data["snf_prod"] / d_qty, 1) if (d_data and d_qty > 0) else Decimal("0.0")
            can_cnt = d_data["can_count"] if d_data else 0
            d_cnt = d_data["d_count"] if d_data else 0

            qty_diff = round(d_qty - c_qty, 2)
            fat_diff = round(d_fat - c_fat, 1) if (c_qty > 0 and d_qty > 0) else None
            snf_diff = round(d_snf - c_snf, 1) if (c_qty > 0 and d_qty > 0) else None

            if d_qty == Decimal("0.00") and c_qty > Decimal("0.00"):
                status = "PENDING_DISPATCH"
            elif c_qty == Decimal("0.00") and d_qty > Decimal("0.00"):
                status = "DIRECT_DISPATCH"
            elif abs(qty_diff) <= Decimal("0.05"):
                status = "BALANCED"
            elif qty_diff < Decimal("-0.05"):
                status = "SHORTAGE"
            else:
                status = "EXCESS"

            items.append(
                ShiftComparisonItemDto(
                    date=d_val,
                    shift=s_val,
                    vlcc_id=v_id,
                    vlcc_name=v_name,
                    collection_quantity=c_qty,
                    collection_fat=c_fat,
                    collection_snf=c_snf,
                    collection_count=c_cnt,
                    farmer_count=f_cnt,
                    dispatch_quantity=d_qty,
                    dispatch_fat=d_fat,
                    dispatch_snf=d_snf,
                    dispatch_can_count=can_cnt,
                    dispatch_count=d_cnt,
                    quantity_diff=qty_diff,
                    fat_diff=fat_diff,
                    snf_diff=snf_diff,
                    status=status,
                )
            )

            tot_c_qty += c_qty
            tot_d_qty += d_qty
            if c_data:
                tot_c_fat_prod += c_data["fat_prod"]
                tot_c_snf_prod += c_data["snf_prod"]
                tot_c_count += c_cnt
            if d_data:
                tot_d_fat_prod += d_data["fat_prod"]
                tot_d_snf_prod += d_data["snf_prod"]
                tot_cans += can_cnt

        net_variance = round(tot_d_qty - tot_c_qty, 2)
        avg_c_fat = round(tot_c_fat_prod / tot_c_qty, 1) if tot_c_qty > 0 else Decimal("0.0")
        avg_c_snf = round(tot_c_snf_prod / tot_c_qty, 1) if tot_c_qty > 0 else Decimal("0.0")
        avg_d_fat = round(tot_d_fat_prod / tot_d_qty, 1) if tot_d_qty > 0 else Decimal("0.0")
        avg_d_snf = round(tot_d_snf_prod / tot_d_qty, 1) if tot_d_qty > 0 else Decimal("0.0")
        ratio = round(float((tot_d_qty / tot_c_qty) * 100), 1) if tot_c_qty > 0 else 0.0

        summary = ComparisonSummaryDto(
            total_collected_qty=tot_c_qty,
            total_dispatched_qty=tot_d_qty,
            net_variance_qty=net_variance,
            total_cans=tot_cans,
            total_collections_count=tot_c_count,
            avg_collection_fat=avg_c_fat,
            avg_collection_snf=avg_c_snf,
            avg_dispatch_fat=avg_d_fat,
            avg_dispatch_snf=avg_d_snf,
            dispatch_ratio=ratio,
        )

        return items, summary

