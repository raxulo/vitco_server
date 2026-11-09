from app.modules.payments.domain.enums import PaymentMethod
from app.modules.payments.domain.enums import PaymentSourceType
from app.modules.payments.application.command import PostPaymentCommand
from app.modules.payments.application.service import PaymentPostingService

from app.middleware.authentication import CurrentUser
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.collections.mcc_collection.domain.listing import CollectionTotals, VlccCollectionFilters
from app.modules.collections.vlcc_collection.domain.entities import VlccCollection
from app.modules.collections.vlcc_collection.domain.exceptions import (
    InvalidVlccCollectionException,
    VlccCollectionNotFoundException,
    VlccCollectionNumberAlreadyExistsException,
)
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.infrastructure.repository import VlccCollectionRepository
from app.core.clock import now_naive_ist
from app.modules.collections.vlcc_collection.domain.dto import (
    VlccCollectionDto,
    VlccCollectionListDto,
    VlccCollectionSummaryDto,
    VlccDetailedCollectionDto,
)

from app.modules.collections.vlcc_collection.application.command import (
    CreateVlccCollectionCommand,
    UpdateVlccCollectionCommand,
    DeleteVlccCollectionCommand,
    BulkDeleteVlccCollectionCommand,
    GetVlccCollectionQuery,
    ListVlccCollectionsQuery,
)



class VlccCollectionHandler:

    __slots__ = (
        "_database",
        "_repository",
        "_payment_service",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: VlccCollectionRepository,
        payment_service: PaymentPostingService
    ) -> None:
        self._database = database
        self._repository = repository
        self._payment_service = payment_service

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateVlccCollectionCommand,
    ) -> VlccCollectionDto:
        self._validate(command)
        
        vlcc_user_id = await self._repository.get_vlcc_user_id(command.vlcc_id)
        farmer_user_id = await self._repository.get_farmer_user_id(command.farmer_id)

        if not vlcc_user_id:
            raise InvalidVlccCollectionException(message="VLCC user account not found.")
        if not farmer_user_id:
            raise InvalidVlccCollectionException(message="Farmer user account not found.")
        await self._ensure_farmer_of_vlcc(command.farmer_id, command.vlcc_id)

        collection_id = uuid4()
        collection = VlccCollection(
            id=collection_id,
            vlcc_id=command.vlcc_id,
            farmer_id=command.farmer_id,
            collected_at=command.collected_at,
            shift=command.shift,
            milk_type=command.milk_type,
            fat_percent=command.fat_percent,
            snf_percent=command.snf_percent,
            quantity=command.quantity,
            quantity_collection_mode=command.quantity_collection_mode,
            measurement_mode=command.measurement_mode,
            rate_per_unit=command.rate_per_unit,
            total_amount=command.total_amount,
            payment_mode=command.payment_mode,
            status=command.status,
            rank=command.rank,
            calibration_fat=command.calibration_fat,
            calibration_snf=command.calibration_snf,
            is_deleted=False,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )

        payment_cmd = PostPaymentCommand(
            sender_id=vlcc_user_id,
            receiver_id=farmer_user_id,
            amount=command.total_amount,
            source_type=PaymentSourceType.MILK_COLLECTION,
            payment_method=PaymentMethod.SYSTEM,
            idempotency_key=str(collection_id),
            source_id=collection_id,
            description=f"Milk collection from {command.farmer_id} to {command.vlcc_id}",
        )

        async with self._database.transaction():
            await self._repository.create(collection)
            await self._database.session.flush()
            await self._payment_service.post(payment_cmd)

        return self._to_dto(collection)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateVlccCollectionCommand,
        owner: CurrentUser,
    ) -> VlccCollectionDto:
        self._validate(command)
        await self._ensure_farmer_of_vlcc(command.farmer_id, command.vlcc_id)

        async with self._database.transaction():
            collection = await self._repository.get_by_id(command.id, owner)
            if collection is None:
                raise VlccCollectionNotFoundException()

            collection.collection_number = command.collection_number.strip()
            collection.vlcc_id = command.vlcc_id
            collection.farmer_id = command.farmer_id
            collection.collected_at = command.collected_at
            collection.shift = command.shift
            collection.milk_type = command.milk_type
            collection.fat_percent = command.fat_percent
            collection.snf_percent = command.snf_percent
            collection.quantity = command.quantity
            collection.quantity_collection_mode = command.quantity_collection_mode
            collection.measurement_mode = command.measurement_mode
            collection.rate_per_unit = command.rate_per_unit
            collection.total_amount = command.total_amount
            collection.payment_mode = command.payment_mode
            collection.status = command.status
            collection.rank = command.rank
            collection.calibration_fat = command.calibration_fat
            collection.calibration_snf = command.calibration_snf
            collection.updated_at = now_naive_ist()

            await self._repository.update(collection, owner)

        return self._to_dto(collection)

    async def _ensure_farmer_of_vlcc(self, farmer_id, vlcc_id) -> None:
        # A collection must be recorded under the farmer's own VLCC, otherwise it
        # shows up (and is paid) under the wrong VLCC
        if not await self._repository.farmer_belongs_to_vlcc(farmer_id, vlcc_id):
            raise InvalidVlccCollectionException(message="This farmer does not belong to the selected VLCC.")

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteVlccCollectionCommand,
        owner: CurrentUser,
    ) -> None:
        async with self._database.transaction():
            await self._repository.delete(command.id, owner)

    async def delete_bulk(
        self,
        command_or_ids: BulkDeleteVlccCollectionCommand | list[UUID],
        owner: CurrentUser,
    ) -> list[UUID]:
        ids = command_or_ids.ids if isinstance(command_or_ids, BulkDeleteVlccCollectionCommand) else command_or_ids
        async with self._database.transaction():
            return await self._repository.delete_bulk(ids, owner)


    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetVlccCollectionQuery,
        owner: CurrentUser,
    ) -> VlccCollectionDto:
        collection = await self._repository.get_by_id(query.id, owner)
        if collection is None:
            raise VlccCollectionNotFoundException()

        return self._to_dto(collection)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListVlccCollectionsQuery,
        owner: CurrentUser,
    ) -> list[VlccCollectionListDto]:
        return await self._repository.list(
            offset=query.offset,
            limit=query.size,
            owner=owner,
            keyword=query.keyword,
            date_from=query.date_from,
            date_to=query.date_to,
            filters=query.filters,
        )

    async def count(
        self,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        filters: VlccCollectionFilters | None = None,
    ) -> int:
        """Rows matching the same filters as `list` (for pagination)."""
        return await self._repository.count(owner, keyword=keyword, date_from=date_from, date_to=date_to, filters=filters)

    async def totals(self, owner: CurrentUser, filters: VlccCollectionFilters | None = None) -> CollectionTotals:
        return await self._repository.totals(owner, filters=filters)

    async def count_search(self, keyword: str, owner: CurrentUser) -> int:
        return await self._repository.count_search(keyword, owner)

    async def get_collection_summary(
        self,
        date_from: datetime,
        date_to: datetime,
        owner: CurrentUser,
        shift: CollectionShift | None = None,
    ) -> VlccCollectionSummaryDto:
        return await self._repository.get_collection_summary(
            date_from=date_from,
            date_to=date_to,
            owner=owner,
            shift=shift,
        )

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
        return await self._repository.get_detailed_collection_list(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            offset=offset,
            limit=limit,
            vlcc_id=vlcc_id,
            farmer_id=farmer_id,
            owner=owner,
            is_deleted=is_deleted,
        )

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
        return await self._repository.get_total_collection_count(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            vlcc_id=vlcc_id,
            farmer_id=farmer_id,
            owner=owner,
            is_deleted=is_deleted,
        )

    
    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        collection: VlccCollection,
    ) -> VlccCollectionListDto:
        return VlccCollectionListDto(
            id=collection.id,
            vlcc_id=collection.vlcc_id,
            farmer_id=collection.farmer_id,
            collected_at=collection.collected_at,
            shift=collection.shift,
            milk_type=collection.milk_type,
            fat_percent=collection.fat_percent,
            snf_percent=collection.snf_percent,
            quantity=collection.quantity,
            rate_per_unit=collection.rate_per_unit,
            total_amount=collection.total_amount,
            status=collection.status,
        )

    def _validate(
        self,
        command: CreateVlccCollectionCommand | UpdateVlccCollectionCommand,
    ) -> None:
        if command.quantity <= 0:
            raise ValidationException("Quantity must be positive.")
        if command.rate_per_unit < 0:
            raise ValidationException("Rate cannot be negative.")

    async def _ensure_number_available(self, number: str) -> None:
        if await self._repository.exists_number(number):
            raise VlccCollectionNumberAlreadyExistsException()

    def _to_dto(self, collection: VlccCollection) -> VlccCollectionDto:
        return VlccCollectionDto(
            id=collection.id,
            vlcc_id=collection.vlcc_id,
            farmer_id=collection.farmer_id,
            collected_at=collection.collected_at,
            shift=collection.shift,
            milk_type=collection.milk_type,
            fat_percent=collection.fat_percent,
            snf_percent=collection.snf_percent,
            quantity=collection.quantity,
            quantity_collection_mode=collection.quantity_collection_mode,
            measurement_mode=collection.measurement_mode,
            rate_per_unit=collection.rate_per_unit,
            total_amount=collection.total_amount,
            payment_mode=collection.payment_mode,
            status=collection.status,
            rank=collection.rank,
            is_deleted=collection.is_deleted,
        )