"""
Formula Exchange Handler

Application service for Formula rate chart export and import (REQ-20, REQ-21).
Checks scope permissions and delegates job submission to ExcelJobHandler.

Python 3.13+
"""

import asyncio
from datetime import date
from pathlib import Path
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.dataexchange.application.command import (
    SubmitExportCommand,
    SubmitImportCommand,
)
from app.modules.dataexchange.application.dto import ExcelJobDto
from app.modules.dataexchange.application.handler import ExcelJobHandler
from app.modules.dataexchange.application.uploads import ExcelUploadService
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.infrastructure.ratechart_scope import (
    RateChartOptions,
    RateChartScope,
)
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.ratechart.domain.enums import MilkType, RateChartType


class FormulaExchangeHandler:

    __slots__ = ("_database", "_jobs", "_scope", "_uploads", "_storage")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        jobs: ExcelJobHandler,
        scope: RateChartScope,
        uploads: ExcelUploadService,
        storage: ExchangeStorage,
    ) -> None:
        self._database = database
        self._jobs = jobs
        self._scope = scope
        self._uploads = uploads
        self._storage = storage

    async def template(self) -> Path:
        from app.modules.dataexchange.application.templates import formula_template_path
        return await asyncio.to_thread(formula_template_path, self._storage.root)

    async def chart_options(
        self,
        owner: CurrentUser,
        *,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RateChartOptions:
        async with self._database.transaction():
            return await self._scope.options(
                owner,
                chart_type=RateChartType.FORMULA,
                search=search,
                limit=limit,
                offset=offset,
            )

    async def export(self, owner: CurrentUser, chart_id: UUID | None) -> ExcelJobDto:
        async with self._database.transaction():
            chart = await self._scope.resolve_for_export(
                owner,
                chart_id,
                chart_type=RateChartType.FORMULA,
            )
        return await self._jobs.submit_export(
            SubmitExportCommand(
                kind=ExcelJobKind.FORMULA_EXPORT,
                owner=owner,
                target_id=chart.id,
            )
        )

    async def import_(
        self,
        owner: CurrentUser,
        *,
        upload_id: UUID,
        chart_id: UUID | None = None,
        chart_name: str | None = None,
        milk_type: MilkType | int | str = MilkType.MIXED,
        effective_from: date | None = None,
        mode: ImportMode = ImportMode.UPSERT,
        dry_run: bool = False,
    ) -> ExcelJobDto:
        async with self._database.transaction():
            if chart_id is not None:
                chart = await self._scope.resolve_for_import(
                    owner,
                    chart_id,
                    chart_type=RateChartType.FORMULA,
                )
                target_id = chart.id
            else:
                chart = await self._scope.create_chart_for_import(
                    owner,
                    chart_name=chart_name,
                    chart_type=RateChartType.FORMULA,
                    milk_type=milk_type,
                    effective_from=effective_from,
                    dry_run=dry_run,
                )
                target_id = chart.id if chart is not None else None

        source = self._uploads.take(owner, upload_id)
        dto = await self._jobs.submit_import(
            SubmitImportCommand(
                kind=ExcelJobKind.FORMULA_IMPORT,
                owner=owner,
                source=source,
                target_id=target_id,
                mode=mode,
                dry_run=dry_run,
            )
        )
        self._uploads.discard(upload_id)
        return dto
