from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from datetime import datetime, UTC
from uuid import UUID, uuid4

from app.core.database.manager import DatabaseManager
from app.modules.collections.vlcc_collection.domain.dispatch_entities import Dispatch
from app.modules.collections.vlcc_collection.domain.dispatch_dto import DispatchDto, DispatchListDto
from app.modules.collections.vlcc_collection.domain.dispatch_exceptions import DispatchNotFoundException
from app.modules.collections.vlcc_collection.infrastructure.dispatch_repository import DispatchRepository
from app.modules.collections.vlcc_collection.application.dispatch_command import (
    CreateDispatchCommand,
    UpdateDispatchCommand,
    DeleteDispatchCommand,
    GetDispatchQuery,
    ListDispatchesQuery,
)


class DispatchHandler:
    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self,
        database: DatabaseManager,
        repository: DispatchRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    async def create(self, command: CreateDispatchCommand) -> DispatchDto:
        now = datetime.now(UTC)
        entity = Dispatch(
            id=uuid4(),
            vlcc_id=command.vlcc_id,
            collected_at=command.collected_at,
            shift=command.shift,
            fat_percent=command.fat_percent,
            snf_percent=command.snf_percent,
            quantity=command.quantity,
            can_count=command.can_count,
            quantity_collection_mode=command.quantity_collection_mode,
            measurement_mode=command.measurement_mode,
            created_at=now,
            updated_at=None,
        )
        async with self._database.transaction():
            await self._repository.create(entity)
        return self._to_dto(entity)

    async def update(self, command: UpdateDispatchCommand) -> DispatchDto:
        entity = await self._repository.get(command.id)
        if entity is None:
            raise DispatchNotFoundException()

        entity.collected_at = command.collected_at
        entity.shift = command.shift
        entity.fat_percent = command.fat_percent
        entity.snf_percent = command.snf_percent
        entity.quantity = command.quantity
        entity.can_count = command.can_count
        entity.quantity_collection_mode = command.quantity_collection_mode
        entity.measurement_mode = command.measurement_mode
        entity.updated_at = datetime.now(UTC)

        async with self._database.transaction():
            await self._repository.update(entity)
        return self._to_dto(entity)

    async def delete(self, command: DeleteDispatchCommand) -> None:
        entity = await self._repository.get(command.id)
        if entity is None:
            raise DispatchNotFoundException()
        async with self._database.transaction():
            await self._repository.delete(command.id)

    async def get(self, query: GetDispatchQuery) -> DispatchDto:
        entity = await self._repository.get(query.id)
        if entity is None:
            raise DispatchNotFoundException()
        return self._to_dto(entity)

    async def get_with_vlcc(self, id: UUID) -> DispatchDto:
        res = await self._repository.get_with_vlcc(id)
        if res is None:
            raise DispatchNotFoundException()
        dto = self._to_dto(res[0], vlcc_name=res[1])
        return dto

    async def get_vlcc_name(self, vlcc_id: UUID) -> str | None:
        from app.modules.vlcc.infrastructure.models import VlccModel
        model = await self._repository._session.get(VlccModel, vlcc_id)
        return model.name if model else None

    async def list(self, query: ListDispatchesQuery) -> list[DispatchListDto]:
        results = await self._repository.list(
            vlcc_id=query.vlcc_id,
            shift=query.shift,
            start_date=query.start_date,
            end_date=query.end_date,
            page=query.page,
            size=query.size,
        )
        return [
            DispatchListDto(
                id=item[0].id,
                vlcc_id=item[0].vlcc_id,
                vlcc_name=item[1],
                collected_at=item[0].collected_at,
                shift=item[0].shift,
                fat_percent=item[0].fat_percent,
                snf_percent=item[0].snf_percent,
                quantity=item[0].quantity,
                can_count=item[0].can_count,
                quantity_collection_mode=item[0].quantity_collection_mode,
                measurement_mode=item[0].measurement_mode,
            )
            for item in results
        ]

    async def count(
        self,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        return await self._repository.count(
            vlcc_id=vlcc_id,
            shift=shift,
            start_date=start_date,
            end_date=end_date,
        )

    def _to_dto(self, entity: Dispatch, vlcc_name: str | None = None) -> DispatchDto:
        return DispatchDto(
            id=entity.id,
            vlcc_id=entity.vlcc_id,
            collected_at=entity.collected_at,
            shift=entity.shift,
            fat_percent=entity.fat_percent,
            snf_percent=entity.snf_percent,
            quantity=entity.quantity,
            can_count=entity.can_count,
            quantity_collection_mode=entity.quantity_collection_mode,
            measurement_mode=entity.measurement_mode,
            vlcc_name=vlcc_name,
        )
