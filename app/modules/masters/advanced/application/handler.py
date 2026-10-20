from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.masters.advanced.domain.entities import (
    AdvanceMaster,
    AdvancePayItem,
    AdvancePayment,
)
from app.modules.masters.advanced.domain.enums import AdvanceStatus
from app.modules.masters.advanced.domain.exceptions import (
    AdvanceNotFoundException,
    AdvanceNumberAlreadyExistsException,
)
from app.modules.masters.advanced.infrastructure.repository import AdvanceRepository
from app.modules.masters.advanced.domain.dto import AdvanceMasterDto, AdvanceMasterListDto
from app.core.clock import now_naive_ist
from app.modules.masters.advanced.application.command import (
    CreateAdvanceCommand,
    UpdateAdvanceCommand,
    DeleteAdvanceCommand,
    SaveAdvanceItemsCommand,
    RecordAdvancePaymentCommand,
    GetAdvanceQuery,
    ListAdvancesQuery,
)


class AdvanceHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: AdvanceRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateAdvanceCommand,
    ) -> AdvanceMasterDto:
        if not command.advance_number.strip():
            raise ValidationException("Invalid Advance Number")

        await self._ensure_number_available(command.advance_number)

        advance = AdvanceMaster(
            id=uuid4(),
            advance_number=command.advance_number.strip(),
            advance_date=command.advance_date,
            user_id=command.user_id,
            total_amount=Decimal("0.00"),
            paid_amount=Decimal("0.00"),
            outstanding_amount=Decimal("0.00"),
            status=AdvanceStatus.UNPAID,
            notes=command.notes,
            is_active=True,
            created_by=command.created_by,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )

        async with self._database.transaction():
            await self._repository.create(advance)

        return self._to_dto(advance)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateAdvanceCommand,
    ) -> AdvanceMasterDto:
        if not command.advance_number.strip():
            raise ValidationException("Invalid Advance Number")

        async with self._database.transaction():
            advance = await self._repository.get_by_id(command.id)
            if advance is None:
                raise AdvanceNotFoundException()

            if advance.advance_number.lower() != command.advance_number.strip().lower():
                await self._ensure_number_available(command.advance_number)

            advance.advance_number = command.advance_number.strip()
            advance.advance_date = command.advance_date
            advance.user_id = command.user_id
            advance.notes = command.notes
            advance.is_active = command.is_active
            advance.updated_at = now_naive_ist()

            await self._repository.update(advance)

        return self._to_dto(advance)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteAdvanceCommand,
    ) -> None:
        async with self._database.transaction():
            advance = await self._repository.get_by_id(command.id)
            if advance is None:
                raise AdvanceNotFoundException()

            await self._repository.delete(advance.id)

    # =========================================================
    # SAVE ITEMS (RECALCULATES TOTAL & OUTSTANDING)
    # =========================================================

    async def save_items(
        self,
        command: SaveAdvanceItemsCommand,
    ) -> None:
        async with self._database.transaction():
            advance = await self._repository.get_by_id(command.advance_id)
            if advance is None:
                raise AdvanceNotFoundException()

            total_amount = Decimal("0.00")
            items = []
            for r in command.items:
                row_total = r.quantity * r.unit_rate
                total_amount += row_total
                items.append(
                    AdvancePayItem(
                        id=uuid4(),
                        advance_id=command.advance_id,
                        item_id=r.item_id,
                        item_name=r.item_name,
                        quantity=r.quantity,
                        unit_rate=r.unit_rate,
                        total_amount=row_total,
                    )
                )

            await self._repository.save_items(command.advance_id, items)

            advance.total_amount = total_amount
            self._recalculate_status_and_outstanding(advance)
            await self._repository.update(advance)

    # =========================================================
    # RECORD PAYMENT
    # =========================================================

    async def record_payment(
        self,
        command: RecordAdvancePaymentCommand,
    ) -> None:
        if command.amount <= 0:
            raise ValidationException("Payment amount must be positive.")

        async with self._database.transaction():
            advance = await self._repository.get_by_id(command.advance_id)
            if advance is None:
                raise AdvanceNotFoundException()

            payment = AdvancePayment(
                id=uuid4(),
                advance_id=command.advance_id,
                payment_date=command.payment_date,
                amount=command.amount,
                payment_mode=command.payment_mode,
                reference_number=command.reference_number,
                notes=command.notes,
                created_by=command.created_by,
                created_at=now_naive_ist(),
                updated_at=now_naive_ist(),
            )

            await self._repository.save_payment(payment)

            advance.paid_amount += command.amount
            self._recalculate_status_and_outstanding(advance)
            await self._repository.update(advance)

    # =========================================================
    # GET / LIST
    # =========================================================

    async def get(
        self,
        query: GetAdvanceQuery,
    ) -> AdvanceMasterDto:
        advance = await self._repository.get_by_id(query.id)
        if advance is None:
            raise AdvanceNotFoundException()

        return self._to_dto(advance)

    async def list(
        self,
        query: ListAdvancesQuery,
    ) -> list[AdvanceMasterListDto]:
        if query.keyword:
            entities = await self._repository.search(
                keyword=query.keyword,
                offset=query.offset,
                limit=query.size,
            )
        else:
            entities = await self._repository.list(
                offset=query.offset,
                limit=query.size,
            )

        return [
            self._to_list_dto(entity)
            for entity in entities
        ]

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        advance: AdvanceMaster,
    ) -> AdvanceMasterListDto:
        return AdvanceMasterListDto(
            id=advance.id,
            advance_number=advance.advance_number,
            advance_date=advance.advance_date,
            user_id=advance.user_id,
            total_amount=advance.total_amount,
            paid_amount=advance.paid_amount,
            outstanding_amount=advance.outstanding_amount,
            status=advance.status,
        )

    def _recalculate_status_and_outstanding(
        self,
        advance: AdvanceMaster,
    ) -> None:
        outstanding = advance.total_amount - advance.paid_amount
        advance.outstanding_amount = max(Decimal("0.00"), outstanding)

        if advance.paid_amount <= 0:
            advance.status = AdvanceStatus.UNPAID
        elif advance.paid_amount >= advance.total_amount:
            if advance.paid_amount > advance.total_amount:
                advance.status = AdvanceStatus.OVERPAID
            else:
                advance.status = AdvanceStatus.PAID
        else:
            advance.status = AdvanceStatus.PARTIALLY_PAID

    async def _ensure_number_available(self, number: str) -> None:
        if await self._repository.exists_number(number):
            raise AdvanceNumberAlreadyExistsException()

    def _to_dto(self, advance: AdvanceMaster) -> AdvanceMasterDto:
        return AdvanceMasterDto(
            id=advance.id,
            advance_number=advance.advance_number,
            advance_date=advance.advance_date,
            user_id=advance.user_id,
            total_amount=advance.total_amount,
            paid_amount=advance.paid_amount,
            outstanding_amount=advance.outstanding_amount,
            status=advance.status,
            notes=advance.notes,
            is_active=advance.is_active,
        )