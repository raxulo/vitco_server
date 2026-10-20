from datetime import datetime
from uuid import UUID
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.authentication import CurrentUser
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.vlcc.infrastructure.models import VlccModel
from sqlalchemy import func
from app.core.database.manager import DatabaseManager
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.domain.dispatch_entities import Dispatch
from app.modules.collections.vlcc_collection.domain.idispatch_repository import IDispatchRepository
from app.modules.collections.vlcc_collection.infrastructure.dispatch_mapper import DispatchMapper
from app.modules.collections.vlcc_collection.infrastructure.models import DispatchModel


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
