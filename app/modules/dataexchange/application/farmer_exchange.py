"""
Farmer Exchange Handler

Use cases behind the farmer import / export endpoints: resolve the VLCC on
the server (DECISION-004), check the farmer permission for imports, then
hand over to the generic job handler, which only queues work.

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
from app.modules.dataexchange.domain.exceptions import ExcelExchangeForbiddenException
from app.modules.dataexchange.domain.sheets import FARMER_SHEET
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.vlcc_scope import VlccOptions, VlccScope


class FarmerExchangeHandler:

    __slots__ = ("_database", "_jobs", "_scope", "_uploads", "_storage")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        jobs: ExcelJobHandler,
        scope: VlccScope,
        uploads: ExcelUploadService,
        storage: ExchangeStorage,
    ) -> None:
        self._database = database
        self._jobs = jobs
        self._scope = scope
        self._uploads = uploads
        self._storage = storage

    async def vlcc_options(self, owner: CurrentUser, *, search: str | None, limit: int, offset: int) -> VlccOptions:
        async with self._database.transaction():
            return await self._scope.options(owner, search=search, limit=limit, offset=offset)

    async def export(self, owner: CurrentUser, vlcc_id: UUID | None) -> ExcelJobDto:
        async with self._database.transaction():
            vlcc = await self._scope.resolve(owner, vlcc_id)
        return await self._jobs.submit_export(
            SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner, target_id=vlcc.id)
        )

    async def import_(
        self,
        owner: CurrentUser,
        *,
        vlcc_id: UUID | None,
        upload_id: UUID,
        mode: ImportMode,
        dry_run: bool,
    ) -> ExcelJobDto:
        async with self._database.transaction():
            vlcc = await self._scope.resolve(owner, vlcc_id)
            if not await self._scope.can_manage_farmers(owner):
                raise ExcelExchangeForbiddenException(
                    "Farmer permission is not enabled for this VLCC. Farmers can be exported but not imported."
                )
        source = self._uploads.take(owner, upload_id)
        dto = await self._jobs.submit_import(SubmitImportCommand(
            kind=ExcelJobKind.FARMER_IMPORT, owner=owner, source=source, target_id=vlcc.id, mode=mode, dry_run=dry_run,
        ))
        self._uploads.discard(upload_id)
        return dto

    async def template(self) -> Path:
        return await asyncio.to_thread(template_path, self._storage.root, FARMER_SHEET, "farmers")
