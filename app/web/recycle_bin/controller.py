"""
Recycle Bin web pages — Super Admin only.

Python 3.13+
"""

from uuid import UUID

from fastapi import Request
from starlette.responses import Response

from app.core.exceptions.base import ForbiddenException
from app.modules.administration.domain.enums import Role
from app.modules.dependencies import GetHandler
from app.modules.recyclebin.application.command import (
    GetPurgeImpactQuery,
    ListDeletedRecordsQuery,
    PurgeRecordCommand,
)
from app.modules.recyclebin.domain.enums import DeletedEntityType
from app.web.framework.renderer import Renderer

_PAGE_SIZE = 20


class RecycleBinController:

    __slots__ = ()

    @staticmethod
    async def list_page(
        request: Request,
        type: str = DeletedEntityType.ADMIN.value,
        search: str = "",
        page: int = 1,
    ) -> Response:
        user = RecycleBinController._super_admin(request)
        entity_type = RecycleBinController._entity_type(type)
        page = max(page, 1)
        handler = GetHandler.recycle_bin_handler(request)

        items, total = await handler.list(
            ListDeletedRecordsQuery(
                entity_type=entity_type,
                owner=user,
                search=search or None,
                offset=(page - 1) * _PAGE_SIZE,
                limit=_PAGE_SIZE,
            )
        )

        # Tab badges: how many deleted records each kind holds
        counts = {}
        for kind in DeletedEntityType:
            _, counts[kind.value] = await handler.list(
                ListDeletedRecordsQuery(entity_type=kind, owner=user, limit=1)
            )

        return Renderer.page(
            request=request,
            template="pages/recycle_bin/list.html",
            model={
                "items": items,
                "total": total,
                "page": page,
                "limit": _PAGE_SIZE,
                "total_pages": max((total + _PAGE_SIZE - 1) // _PAGE_SIZE, 1),
                "search": search,
                "active_type": entity_type.value,
                "active_label": entity_type.label,
                "tabs": [(kind.value, kind.label, counts[kind.value]) for kind in DeletedEntityType],
            },
        )

    @staticmethod
    async def impact_partial(request: Request, entity_type: str, record_id: UUID) -> Response:
        user = RecycleBinController._super_admin(request)
        impact = await GetHandler.recycle_bin_handler(request).impact(
            GetPurgeImpactQuery(
                entity_type=RecycleBinController._entity_type(entity_type),
                record_id=record_id,
                owner=user,
            )
        )
        return Renderer.partial(
            request=request,
            template="pages/recycle_bin/partials/confirm.html",
            model={"impact": impact},
        ).build()

    @staticmethod
    async def purge_post(request: Request, entity_type: str, record_id: UUID) -> Response:
        user = RecycleBinController._super_admin(request)
        handler = GetHandler.recycle_bin_handler(request)
        kind = RecycleBinController._entity_type(entity_type)

        # The confirm text is checked on the server too, not only by the button state
        form = await request.form()
        impact = await handler.impact(GetPurgeImpactQuery(entity_type=kind, record_id=record_id, owner=user))
        if str(form.get("confirm_text", "")).strip() != impact.confirm_text:
            return Renderer.empty(status_code=422).error(
                f'Type "{impact.confirm_text}" exactly to confirm the permanent delete.'
            ).build()

        await handler.purge(PurgeRecordCommand(entity_type=kind, record_id=record_id, owner=user))
        # Empty body: HTMX removes the row; the toast confirms
        return Renderer.empty().success(f"{impact.name} was permanently deleted.").build()

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _super_admin(request: Request):
        user = getattr(request.state, "user", None)
        if user is None or user.role_type != Role.SUPER_ADMIN:
            raise ForbiddenException("Only the Super Admin can open the recycle bin")
        return user

    @staticmethod
    def _entity_type(value: str) -> DeletedEntityType:
        try:
            return DeletedEntityType(value)
        except ValueError:
            return DeletedEntityType.ADMIN
