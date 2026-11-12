"""
Collection Exchange Handler (REQ-48, REQ-49, DECISION-028)

Use cases behind the collection export endpoints: check the role, store the
list's filters with the job and queue it. Which rows the file holds is decided
by the worker through the list's own access scope, so nothing here can widen it.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import replace

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.collection_export import CollectionExportFilters
from app.modules.dataexchange.application.command import SubmitExportCommand
from app.modules.dataexchange.application.dto import ExcelJobDto
from app.modules.dataexchange.application.handler import ExcelJobHandler
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.exceptions import ExcelExchangeForbiddenException

# Who may open each list (the web list pages apply the same rule)
_MCC_COLLECTION_ROLES = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC})
_VLCC_COLLECTION_ROLES = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER})


class CollectionExchangeHandler:

    __slots__ = ("_jobs",)

    def __init__(self, *, jobs: ExcelJobHandler) -> None:
        self._jobs = jobs

    # =========================================================
    # EXPORT
    # =========================================================

    async def export_mcc_collections(self, owner: CurrentUser, filters: CollectionExportFilters) -> ExcelJobDto:
        self._ensure_role(owner, _MCC_COLLECTION_ROLES, "MCC collections")
        return await self._jobs.submit_export(SubmitExportCommand(
            kind=ExcelJobKind.MCC_COLLECTION_EXPORT, owner=owner, params=filters.to_params(),
        ))

    async def export_vlcc_collections(self, owner: CurrentUser, filters: CollectionExportFilters) -> ExcelJobDto:
        self._ensure_role(owner, _VLCC_COLLECTION_ROLES, "VLCC collections")
        filters = replace(filters, mcc_id=None)        # the VLCC list has no MCC filter
        return await self._jobs.submit_export(SubmitExportCommand(
            kind=ExcelJobKind.VLCC_COLLECTION_EXPORT, owner=owner, params=filters.to_params(),
        ))

    # ---------------------------------------------------------

    @staticmethod
    def _ensure_role(owner: CurrentUser, allowed: frozenset[Role], what: str) -> None:
        if owner.role_type not in allowed or getattr(owner, "is_farmer_vlcc", False):
            raise ExcelExchangeForbiddenException(f"Your account cannot export {what}")
