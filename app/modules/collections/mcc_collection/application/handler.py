from app.modules.payments.domain.enums import PaymentMethod, PaymentSourceType
from app.modules.payments.application.command import PostPaymentCommand
from app.modules.payments.application.service import PaymentPostingService

from app.middleware.authentication import CurrentUser
from app.modules.mcc.domain.enums import MccType
from app.modules.collections.mcc_collection.domain.dto import MccSampleResult
from app.modules.collections.mcc_collection.domain.dto import MccCollectionResult
from app.modules.collections.mcc_collection.application.command import (
    GetCollectionBySampleNumberQuery,
    GetNextSampleNumberQuery,
)
from datetime import UTC, datetime, date
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.collections.mcc_collection.domain.entities import MccCollection
from app.modules.collections.mcc_collection.domain.exceptions import (
    InvalidMccCollectionException,
    MccCollectionNotFoundException,
    MccCollectionNumberAlreadyExistsException,
)
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.repository import MccCollectionRepository
from app.core.clock import now_naive_ist
from app.modules.collections.mcc_collection.domain.dto import (
    MccCollectionDto,
    MccCollectionListDto,
    MccCollectionSummaryDto,
    MccDetailedCollectionDto,
)

from app.modules.collections.mcc_collection.application.command import (
    CreateMccCollectionCommand,
    UpdateMccCollectionCommand,
    DeleteMccCollectionCommand,
    BulkDeleteMccCollectionCommand,
    GetMccCollectionQuery,
    ListMccCollectionsQuery,
)



class MccCollectionHandler:

    __slots__ = (
        "_database",
        "_repository",
        "_payment_service",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: MccCollectionRepository,
        payment_service: PaymentPostingService,
    ) -> None:
        self._database = database
        self._repository = repository
        self._payment_service = payment_service

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateMccCollectionCommand,
    ) -> MccCollectionDto:
        self._validate(command)

        mcc_user_id = await self._repository.get_mcc_user_id(command.mcc_id)
        vlcc_user_id = await self._repository.get_vlcc_user_id(command.vlcc_id)

        if not mcc_user_id:
            raise InvalidMccCollectionException(message="MCC user account not found.")
        if not vlcc_user_id:
            raise InvalidMccCollectionException(message="VLCC user account not found.")
        await self._ensure_sample_usable(command)

        collection_id = uuid4()
        collection = MccCollection(
            id=collection_id,
            mcc_id=command.mcc_id,
            vlcc_id=command.vlcc_id,
            collected_at=command.collected_at,
            shift=command.shift,
            milk_type=command.milk_type,
            fat_percent=command.fat_percent,
            snf_percent=command.snf_percent,
            clr_value=command.clr_value,
            quantity=command.quantity,
            quantity_collection_mode=command.quantity_collection_mode,
            measurement_mode=command.measurement_mode,
            rate_per_unit=command.rate_per_unit,
            total_amount=command.total_amount,
            payment_mode=command.payment_mode,
            status=command.status,
            rank=command.rank,
            sample_number=command.sample_number,
            can_count=command.can_count,
            detection_value=command.detection_value,
            calibration_fat=command.calibration_fat,
            calibration_snf=command.calibration_snf,
            is_deleted=False,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )

        payment_cmd = PostPaymentCommand(
            sender_id=mcc_user_id,
            receiver_id=vlcc_user_id,
            amount=command.total_amount,
            source_type=PaymentSourceType.MILK_COLLECTION,
            payment_method=PaymentMethod.SYSTEM,
            idempotency_key=str(collection_id),
            source_id=collection_id,
            description=f"Milk collection from {command.vlcc_id} to {command.mcc_id}",
        )

        async with self._database.transaction():
            await self._repository.create(collection)
            await self._database.session.flush()
            if command.total_amount > 0:
                await self._payment_service.post(payment_cmd)

        return self._to_dto(collection)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateMccCollectionCommand,
        owner: CurrentUser,
    ) -> MccCollectionDto:
        self._validate(command)

        async with self._database.transaction():
            collection = await self._repository.get_by_id(command.id, owner)
            if collection is None:
                raise MccCollectionNotFoundException()
            await self._ensure_sample_usable(command, exclude_collection_id=command.id)

            collection.collection_number = command.collection_number.strip()
            collection.mcc_id = command.mcc_id
            collection.vlcc_id = command.vlcc_id
            collection.collected_at = command.collected_at
            collection.shift = command.shift
            collection.milk_type = command.milk_type
            collection.fat_percent = command.fat_percent
            collection.snf_percent = command.snf_percent
            collection.clr_value = command.clr_value
            collection.quantity = command.quantity
            collection.quantity_collection_mode = command.quantity_collection_mode
            collection.measurement_mode = command.measurement_mode
            collection.rate_per_unit = command.rate_per_unit
            collection.total_amount = command.total_amount
            collection.payment_mode = command.payment_mode
            collection.status = command.status
            collection.rank = command.rank
            collection.sample_number = command.sample_number
            collection.can_count = command.can_count
            collection.detection_value = command.detection_value
            collection.calibration_fat = command.calibration_fat
            collection.calibration_snf = command.calibration_snf
            collection.updated_at = now_naive_ist()

            await self._repository.update(collection, owner)

        return self._to_dto(collection)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteMccCollectionCommand,
        owner: CurrentUser,
    ) -> None:
        async with self._database.transaction():
            await self._repository.delete(command.id, owner)

    async def delete_bulk(
        self,
        command_or_ids: BulkDeleteMccCollectionCommand | list[UUID],
        owner: CurrentUser,
    ) -> list[UUID]:
        ids = command_or_ids.ids if isinstance(command_or_ids, BulkDeleteMccCollectionCommand) else command_or_ids
        async with self._database.transaction():
            return await self._repository.delete_bulk(ids, owner)


    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetMccCollectionQuery,
        owner: CurrentUser,
    ) -> MccCollectionDto:
        collection = await self._repository.get_by_id(query.id, owner)
        if collection is None:
            raise MccCollectionNotFoundException()

        return self._to_dto(collection)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListMccCollectionsQuery,
        owner: CurrentUser,
    ) -> list[MccCollectionListDto]:
        return await self._repository.list(
            offset=query.offset,
            limit=query.size,
            owner=owner,
            keyword=query.keyword,
            date_from=query.date_from,
            date_to=query.date_to,
        )

    async def count(
        self,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        """Rows matching the same filters as `list` (for pagination)."""
        return await self._repository.count(owner, keyword=keyword, date_from=date_from, date_to=date_to)

    async def count_search(self, keyword: str, owner: CurrentUser) -> int:
        return await self._repository.count_search(keyword, owner)

    async def genext_sample_number(self, query: GetNextSampleNumberQuery) -> MccSampleResult:
        return await self._repository.genext_sample_number(query)

    async def collection_by_sample_result(
        self,
        query: GetCollectionBySampleNumberQuery,
    ) -> MccCollectionResult | None:
        return await self._repository.get_collection_by_sample_number(query)

    SAMPLE_MESSAGES = {
        "not_exists": "sample not exists",
        "taken": "already taken",
    }

    async def sample_number_error(
        self,
        query: GetCollectionBySampleNumberQuery,
        exclude_collection_id: UUID | None = None,
    ) -> str | None:
        """User-facing reason a sample number can't be used here, or None."""
        problem = await self._repository.sample_number_problem(query, exclude_collection_id)
        return self.SAMPLE_MESSAGES.get(problem) if problem else None

    async def _ensure_sample_usable(self, command, exclude_collection_id: UUID | None = None) -> None:
        if not command.sample_number:
            return
        error = await self.sample_number_error(
            GetCollectionBySampleNumberQuery(
                mcc_id=command.mcc_id,
                sample_number=command.sample_number,
                shift=command.shift,
                collected_at=command.collected_at,
            ),
            exclude_collection_id,
        )
        if error:
            raise InvalidMccCollectionException(message=f"Sample {command.sample_number}: {error}")

    async def is_sample_number_collected(
        self,query: GetCollectionBySampleNumberQuery,
    ) -> bool:
        """
        Check whether a milk collection already exists for the same mcc_id, shift, date, and sample_number.
        """
        return await self._repository.is_sample_number_collected(query)

    async def get_collection_summary(
        self,
        date_from: datetime,
        date_to: datetime,
        owner: CurrentUser,
        shift: CollectionShift | None = None,
    ) -> MccCollectionSummaryDto:
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
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
    ) -> list[MccDetailedCollectionDto]:
        return await self._repository.get_detailed_collection_list(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            offset=offset,
            limit=limit,
            mcc_id=mcc_id,
            vlcc_id=vlcc_id,
            owner=owner,
            is_deleted=is_deleted,
        )

    async def get_total_collection_count(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: CollectionShift | None = None,
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
    ) -> int:
        return await self._repository.get_total_collection_count(
            date_from=date_from,
            date_to=date_to,
            shift=shift,
            mcc_id=mcc_id,
            vlcc_id=vlcc_id,
            owner=owner,
            is_deleted=is_deleted,
        )


    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        collection: MccCollection,
    ) -> MccCollectionListDto:
        return MccCollectionListDto(
            id=collection.id,
            mcc_id=collection.mcc_id,
            vlcc_id=collection.vlcc_id,
            collected_at=collection.collected_at,
            shift=collection.shift,
            milk_type=collection.milk_type,
            quantity=collection.quantity,
            total_amount=collection.total_amount,
            status=collection.status,
        )

    def _validate(
        self,
        command: CreateMccCollectionCommand | UpdateMccCollectionCommand,
    ) -> None:
        if command.quantity <= 0:
            raise ValidationException("Quantity must be positive.")
        if command.mcc_type != MccType.WEIGHT and command.rate_per_unit < 0:
            raise ValidationException("Rate cannot be negative.")

    async def _ensure_number_available(self, number: str) -> None:
        if await self._repository.exists_number(number):
            raise MccCollectionNumberAlreadyExistsException()

    def _to_dto(self, collection: MccCollection) -> MccCollectionDto:
        return MccCollectionDto(
            id=collection.id,
            mcc_id=collection.mcc_id,
            vlcc_id=collection.vlcc_id,
            collected_at=collection.collected_at,
            shift=collection.shift,
            milk_type=collection.milk_type,
            fat_percent=collection.fat_percent,
            snf_percent=collection.snf_percent,
            clr_value=collection.clr_value,
            quantity=collection.quantity,
            quantity_collection_mode=collection.quantity_collection_mode,
            measurement_mode=collection.measurement_mode,
            rate_per_unit=collection.rate_per_unit,
            total_amount=collection.total_amount,
            payment_mode=collection.payment_mode,
            status=collection.status,
            sample_number=collection.sample_number,
            can_count=collection.can_count,
        )