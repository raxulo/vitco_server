from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.masters.advanced.domain.entities import (
    AdvanceMaster,
    AdvancePayItem,
    AdvancePayment,
)
from app.modules.masters.advanced.domain.irepository import IAdvanceRepository
from app.modules.masters.advanced.infrastructure.mapper import AdvanceMapper
from app.modules.masters.advanced.infrastructure.models import (
    AdvanceMasterModel,
    AdvancePayItemModel,
    AdvancePaymentModel,
)


class AdvanceRepository(IAdvanceRepository):

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
    # CREATE / UPDATE / DELETE
    # =========================================================

    async def create(
        self,
        entity: AdvanceMaster,
    ) -> None:
        model = AdvanceMapper.to_master_model(entity)
        self._session.add(model)

    async def update(
        self,
        entity: AdvanceMaster,
    ) -> None:
        model = await self._session.get(AdvanceMasterModel, entity.id)
        if model is None:
            return

        model.advance_number = entity.advance_number
        model.advance_date = entity.advance_date
        model.user_id = entity.user_id
        model.total_amount = entity.total_amount
        model.paid_amount = entity.paid_amount
        model.outstanding_amount = entity.outstanding_amount
        model.status = entity.status
        model.notes = entity.notes
        model.is_active = entity.is_active
        model.updated_at = entity.updated_at

    async def delete(
        self,
        id: UUID,
    ) -> None:
        model = await self._session.get(AdvanceMasterModel, id)
        if model is not None:
            await self._session.delete(model)

    async def get_by_id(
        self,
        id: UUID,
    ) -> AdvanceMaster | None:
        model = await self._session.get(AdvanceMasterModel, id)
        if model is None:
            return None
        return AdvanceMapper.to_master_entity(model)

    async def get_by_number(
        self,
        number: str,
    ) -> AdvanceMaster | None:
        stmt = select(AdvanceMasterModel).where(
            AdvanceMasterModel.advance_number == number
        )
        model = await self._session.scalar(stmt)
        if model is None:
            return None
        return AdvanceMapper.to_master_entity(model)

    async def exists_number(
        self,
        number: str,
    ) -> bool:
        stmt = select(AdvanceMasterModel.id).where(
            AdvanceMasterModel.advance_number == number
        ).limit(1)
        result = await self._session.scalar(stmt)
        return result is not None

    # =========================================================
    # ITEMS
    # =========================================================

    async def get_items(
        self,
        advance_id: UUID,
    ) -> list[AdvancePayItem]:
        stmt = select(AdvancePayItemModel).where(
            AdvancePayItemModel.advance_id == advance_id
        )
        result = await self._session.scalars(stmt)
        return [AdvanceMapper.to_item_entity(m) for m in result]

    async def save_items(
        self,
        advance_id: UUID,
        items: list[AdvancePayItem],
    ) -> None:
        # Clear existing items first
        await self._session.execute(
            delete(AdvancePayItemModel).where(
                AdvancePayItemModel.advance_id == advance_id
            )
        )
        # Bulk add new ones
        for item in items:
            model = AdvanceMapper.to_item_model(item)
            self._session.add(model)

    # =========================================================
    # PAYMENTS
    # =========================================================

    async def get_payments(
        self,
        advance_id: UUID,
    ) -> list[AdvancePayment]:
        stmt = select(AdvancePaymentModel).where(
            AdvancePaymentModel.advance_id == advance_id
        ).order_by(AdvancePaymentModel.payment_date.asc())
        result = await self._session.scalars(stmt)
        return [AdvanceMapper.to_payment_entity(m) for m in result]

    async def save_payment(
        self,
        payment: AdvancePayment,
    ) -> None:
        existing = await self._session.get(AdvancePaymentModel, payment.id)
        if existing is not None:
            existing.payment_date = payment.payment_date
            existing.amount = payment.amount
            existing.payment_mode = payment.payment_mode
            existing.reference_number = payment.reference_number
            existing.notes = payment.notes
            existing.updated_at = payment.updated_at
        else:
            model = AdvanceMapper.to_payment_model(payment)
            self._session.add(model)

    # =========================================================
    # LIST & SEARCH & COUNT
    # =========================================================

    async def list(
        self,
        offset: int,
        limit: int,
    ) -> list[AdvanceMaster]:
        stmt = (
            select(AdvanceMasterModel)
            .order_by(AdvanceMasterModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [AdvanceMapper.to_master_entity(model) for model in result]

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[AdvanceMaster]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(offset=offset, limit=limit)

        pattern = f"%{keyword}%"
        stmt = (
            select(AdvanceMasterModel)
            .where(AdvanceMasterModel.advance_number.ilike(pattern))
            .order_by(AdvanceMasterModel.advance_number.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [AdvanceMapper.to_master_entity(model) for model in result]

    async def count(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count(AdvanceMasterModel.id))
        return await self._session.scalar(stmt) or 0

    async def count_search(
        self,
        keyword: str,
    ) -> int:
        from sqlalchemy import func
        keyword = keyword.strip()
        pattern = f"%{keyword}%"
        stmt = select(func.count(AdvanceMasterModel.id)).where(
            AdvanceMasterModel.advance_number.ilike(pattern)
        )
        return await self._session.scalar(stmt) or 0