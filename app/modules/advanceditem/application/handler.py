from app.modules.advanceditem.application.command import AdvanceListResponseDTO
from typing import List
from app.modules.advanceditem.application.command import AdvanceListDTO
from app.modules.advanceditem.application.command import AdvanceListQuery
from app.modules.advanceditem.application.command import AdvanceItemDetailDTO
from app.modules.advanceditem.application.command import AdvanceDetailDTO
from app.modules.masters.items.infrastructure.repository import ItemMasterRepository
from uuid import UUID
from app.middleware.authentication import CurrentUser
from app.modules.advanceditem.application.command import AdvanceItemCommand
from app.modules.payments.domain.enums import PaymentMethod
from app.modules.payments.domain.enums import PaymentSourceType
from app.modules.payments.application.command import PostPaymentCommand
from app.modules.advanceditem.infrastructure.mapper import AdvanceItemMapper
from app.modules.advanceditem.infrastructure.mapper import AdvanceRecordMapper
from decimal import Decimal
from app.modules.advanceditem.domain.entities import AdvanceRecord
from app.modules.advanceditem.application.command import CreateAdvanceCommand
from app.modules.advanceditem.infrastructure.repository import AdvanceRecordRepository
from app.modules.payments.application.service import PaymentPostingService
class AdvanceService:

    __slots__ = (
        "_advance_record_repository",
        "_advance_item_repository",
        "_item_master_repository",
        "_payment_posting_service",
    )

    def __init__(
        self,
        *,
        advance_record_repository: AdvanceRecordRepository,
        payment_posting_service: PaymentPostingService,
        item_master_repository: ItemMasterRepository,
    ) -> None:
    
        self._advance_record_repository = advance_record_repository
        self._payment_posting_service = payment_posting_service
        self._item_master_repository = item_master_repository
        
    # =========================================================
    # CREATE ADVANCE
    # =========================================================

    async def create(self,command: CreateAdvanceCommand,) -> AdvanceRecord:

        self._validate_command(command)

        # -----------------------------------------------------
        # 1. Fetch all ItemMaster records
        #
        # IMPORTANT:
        # Never query ItemMaster once per item.
        # -----------------------------------------------------

        item_master_ids = frozenset( item.item_master_id for item in command.items )

        item_masters = (
            await self._item_master_repository
            .get_by_ids(
                ids=list(item_master_ids)
            )
        )

        item_master_map = {
            item.id: item
            for item in item_masters
        }

        # -----------------------------------------------------
        # 2. Validate all items before creating anything
        # -----------------------------------------------------

        self._validate_item_masters(
            command.items,
            item_master_map,
        )

        # -----------------------------------------------------
        # 3. Create domain aggregate
        # -----------------------------------------------------

        record = AdvanceRecord.create(
            user_id=command.user_id,
            advance_date=command.advance_date,
            created_by=command.created_by,
            notes=command.notes,
        )

        # -----------------------------------------------------
        # 4. Create items
        #
        # ItemMaster.rate is copied as historical snapshot.
        # -----------------------------------------------------
        total_amount = Decimal("0.00")
        for command_item in command.items:
            item_master = item_master_map[command_item.item_master_id]

            unit_rate = Decimal(str(item_master.rate))

            total_amount += unit_rate * command_item.quantity

            record.add_item(
                item_master_id=command_item.item_master_id,
                quantity=command_item.quantity,
                unit_rate=unit_rate,
            )

        # -----------------------------------------------------
        # 8. Calculate total from domain aggregate
        # -----------------------------------------------------

        if total_amount <= Decimal("0.00"):
            raise ValueError("Advance amount must be greater than zero.")

        # -----------------------------------------------------
        # 5. Convert aggregate to DB models
        # -----------------------------------------------------

        record_model = AdvanceRecordMapper.to_model(record)

        item_models = [AdvanceItemMapper.to_model(item) for item in record.items]

        # -----------------------------------------------------
        # 6. Persist
        #
        # NO commit here.
        # NO flush per item.
        # -----------------------------------------------------

        await self._advance_record_repository.create_record(record_model)

        await self._advance_record_repository.create_items(item_models)

        # -----------------------------------------------------
        # 7. Flush once
        #
        # Required only if PaymentPostingService needs
        # DB-generated state immediately.
        # -----------------------------------------------------

        await self._advance_record_repository.flush()

        
        # -----------------------------------------------------
        # 9. Post payment
        #
        # This must use the SAME AsyncSession / transaction.
        # -----------------------------------------------------

        await self._payment_posting_service.post(
            command=PostPaymentCommand(
                sender_id=command.user_id,
                receiver_id=command.created_by,
                amount=total_amount,
                source_type=PaymentSourceType.ADVANCE,
                payment_method=PaymentMethod.SYSTEM,
                idempotency_key=str(record.id),
                source_id=record.id,
                reference=None,
                description=command.notes,
            )
        )

        return record

    async def get_detail(self, advance_id: UUID, owner: CurrentUser) -> AdvanceDetailDTO | None:
        # None when the record doesn't exist or the user neither gave nor received it
        rows = await self._advance_record_repository.get_detail_rows(advance_id, owner)

        if not rows:
            return None

        first = rows[0]

        items = tuple(
            AdvanceItemDetailDTO(
                id=row.item_id,
                item_master_id=row.item_master_id,
                item_name=row.item_name,
                item_code=row.item_code,
                quantity=row.quantity,
                unit_rate=row.unit_rate,
                amount=row.amount,
            )
            for row in rows
        )

        

        return AdvanceDetailDTO(
            id=first.id,
            user_id=first.user_id,
            user_name=first.user_name,
            user_role=first.user_role,
            advance_date=first.advance_date,
            created_by=first.created_by,
            created_by_name=first.created_by_name,
            created_by_role=first.created_by_role,
            notes=first.notes,
            total_amount=first.total_amount,
            items=items,
        )

    async def list(self, command: AdvanceListQuery) -> AdvanceListResponseDTO:
        count = await self._advance_record_repository.count(owner=command.owner)
        result = await self._advance_record_repository.get_list(
            owner=command.owner, 
            size=command.size, 
            page=command.page
        )
        
        return AdvanceListResponseDTO(
            items = [
                AdvanceListDTO(
                    id=row.id,
                    user_id=row.user_id,
                    user_name=row.user_name,
                    user_role=row.user_role,
                    advance_date=row.advance_date,
                    created_by=row.created_by,
                    created_by_name=row.created_by_name,
                    created_by_role=row.created_by_role,
                    notes=row.notes,
                    total_amount=row.total_amount,
                )
                for row in result
            ],
            page=command.page,
            size=command.size,
            total_page=max(1, -(-count // command.size)),
        )
        

    # =========================================================
    # VALIDATION
    # =========================================================

    @staticmethod
    def _validate_command(
        command: CreateAdvanceCommand,
    ) -> None:

        if command.user_id == command.created_by:
            raise ValueError(
                "User and creator cannot be the same."
            )

        if not command.items:
            raise ValueError(
                "Advance must contain at least one item."
            )

        if len(command.items) > 100:
            raise ValueError(
                "Maximum 100 items are allowed per advance."
            )

    @staticmethod
    def _validate_item_masters(
        items: tuple[AdvanceItemCommand, ...],
        item_master_map: dict[UUID, object],
    ) -> None:

        for item in items:

            if item.quantity <= Decimal("0"):
                raise ValueError(
                    "Item quantity must be greater than zero."
                )

            if item.item_master_id not in item_master_map:
                raise ValueError(
                    f"Item master not found: "
                    f"{item.item_master_id}"
                )

        # -----------------------------------------------------
        # Prevent duplicate ItemMaster in same advance
        # -----------------------------------------------------

        ids = [
            item.item_master_id
            for item in items
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Duplicate item master is not allowed "
                "in the same advance."
            )