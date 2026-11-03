"""
Recycle Bin use cases — Super Admin only.

Python 3.13+
"""

from app.core.database.manager import DatabaseManager
from app.core.exceptions.base import ForbiddenException
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.media.application.services import MediaService
from app.modules.recyclebin.application.command import (
    GetPurgeImpactQuery,
    ListDeletedRecordsQuery,
    PurgeRecordCommand,
)
from app.modules.recyclebin.domain.dto import DeletedRecordDto, PurgeImpactDto
from app.modules.recyclebin.domain.exceptions import DeletedRecordNotFoundException
from app.modules.recyclebin.domain.irepository import IRecycleBinRepository


class RecycleBinHandler:

    __slots__ = ("_database", "_repository", "_media_service")

    def __init__(
        self,
        database: DatabaseManager,
        repository: IRecycleBinRepository,
        media_service: MediaService,
    ) -> None:
        self._database = database
        self._repository = repository
        self._media_service = media_service

    # =========================================================
    # LIST
    # =========================================================

    async def list(self, query: ListDeletedRecordsQuery) -> tuple[list[DeletedRecordDto], int]:
        self._ensure_super_admin(query.owner)
        return await self._repository.list_deleted(
            entity_type=query.entity_type,
            search=query.search,
            offset=query.offset,
            limit=query.limit,
        )

    # =========================================================
    # IMPACT (preview before purge)
    # =========================================================

    async def impact(self, query: GetPurgeImpactQuery) -> PurgeImpactDto:
        self._ensure_super_admin(query.owner)
        found = await self._repository.get_deleted(query.entity_type, query.record_id)
        if found is None:
            raise DeletedRecordNotFoundException()
        record, user_id = found

        scope = await self._repository.resolve_scope(user_id)
        counts = await self._repository.count_impact(scope)
        return PurgeImpactDto(
            entity_type=query.entity_type,
            record_id=record.id,
            name=record.name,
            code=record.code,
            confirm_text=record.code or record.name,
            deleted_at=record.deleted_at,
            deleted_by_label=record.deleted_by_label,
            **counts,
        )

    # =========================================================
    # PURGE
    # =========================================================

    async def purge(self, command: PurgeRecordCommand) -> PurgeImpactDto:
        """Permanently delete the record, its ownership tree and all their data (DECISION-013)."""
        impact = await self.impact(
            GetPurgeImpactQuery(
                entity_type=command.entity_type,
                record_id=command.record_id,
                owner=command.owner,
            )
        )
        found = await self._repository.get_deleted(command.entity_type, command.record_id)
        if found is None:
            raise DeletedRecordNotFoundException()

        async with self._database.transaction():
            scope = await self._repository.resolve_scope(found[1])
            # Profile image files go only after the commit (MediaService defers them)
            for user_id in scope.user_ids:
                await self._media_service.delete_profile_image(user_id)
            await self._repository.purge(scope)
        return impact

    @staticmethod
    def _ensure_super_admin(owner: CurrentUser | None) -> None:
        if owner is None or owner.role_type != Role.SUPER_ADMIN:
            raise ForbiddenException("Only the Super Admin can use the recycle bin")
