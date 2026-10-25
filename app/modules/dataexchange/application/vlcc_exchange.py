"""
VLCC Exchange Handler

Use cases behind the VLCC import / export endpoints: resolve the owner on
the server (REQ-12, DECISION-004), then hand over to the generic job handler,
which only queues work.

Python 3.13+
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.dataexchange.application.command import SubmitExportCommand, SubmitImportCommand
from app.modules.dataexchange.application.dto import ExcelJobDto
from app.modules.dataexchange.application.handler import ExcelJobHandler
from app.modules.dataexchange.application.templates import template_path
from app.modules.dataexchange.application.uploads import ExcelUploadService
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import VLCC_SHEET
from app.modules.dataexchange.infrastructure.owner_scope import OwnerOptions, OwnerScope
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage


class VlccExchangeHandler:

    __slots__ = ("_database", "_jobs", "_scope", "_uploads", "_storage")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        jobs: ExcelJobHandler,
        scope: OwnerScope,
        uploads: ExcelUploadService,
        storage: ExchangeStorage,
    ) -> None:
        self._database = database
        self._jobs = jobs
        self._scope = scope
        self._uploads = uploads
        self._storage = storage

    async def owner_options(self, owner: CurrentUser, *, search: str | None, limit: int, offset: int) -> OwnerOptions:
        async with self._database.transaction():
            return await self._scope.options(owner, search=search, limit=limit, offset=offset)

    async def export(self, owner: CurrentUser, owner_id: UUID | None) -> ExcelJobDto:
        async with self._database.transaction():
            target_owner = await self._scope.resolve(owner, owner_id)
        return await self._jobs.submit_export(
            SubmitExportCommand(kind=ExcelJobKind.VLCC_EXPORT, owner=owner, target_id=target_owner.id)
        )

    async def import_(
        self,
        owner: CurrentUser,
        *,
        owner_id: UUID | None,
        upload_id: UUID,
        mode: ImportMode,
        dry_run: bool,
    ) -> ExcelJobDto:
        async with self._database.transaction():
            target_owner = await self._scope.resolve(owner, owner_id)
        source = self._uploads.take(owner, upload_id)
        dto = await self._jobs.submit_import(SubmitImportCommand(
            kind=ExcelJobKind.VLCC_IMPORT, owner=owner, source=source, target_id=target_owner.id, mode=mode, dry_run=dry_run,
        ))
        self._uploads.discard(upload_id)
        return dto

    async def template(self) -> Path:
        return await asyncio.to_thread(template_path, self._storage.root, VLCC_SHEET, "vlccs")
