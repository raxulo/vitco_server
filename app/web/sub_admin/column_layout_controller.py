"""
"Excel Column Order" page (Plan 24.3, REQ-55, REQ-57, DECISION-030)

Super Admin, Admin and Sub Admin arrange the columns of their collection Excel
exports: order (drag and drop or up / down) and show / hide. `?user_id=` opens
another user's order: Super Admin -> any Admin / Sub Admin, Admin -> its own Sub
Admins. The permission rules live in ColumnLayoutHandler, shared with the API.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request
from starlette.responses import Response

from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.command import (
    GetColumnLayoutQuery,
    ResetColumnLayoutCommand,
    UpdateColumnLayoutCommand,
)
from app.modules.dependencies import GetHandler
from app.web.framework.helpers import WebHelper
from app.web.framework.renderer import Renderer

_PAGE = "/sub-admins/column-layout"
_ROLE_LABELS = {Role.SUPER_ADMIN: "Super Admin", Role.ADMIN: "Admin", Role.SUB_ADMIN: "Sub Admin"}


class ColumnLayoutController:

    @staticmethod
    async def page(request: Request, user_id: UUID | None = None):
        user = request.state.user
        layout = await GetHandler.column_layout_handler(request).get(
            GetColumnLayoutQuery(owner=user, user_id=user_id)
        )
        is_self = layout.user_id == user.id
        return Renderer.page(
            request=request,
            template="pages/sub_admin/column_layout.html",
            model={
                "layout": layout,
                "is_self": is_self,
                "target_role": _ROLE_LABELS.get(Role(layout.user_role), "User"),
                "action_url": _url(None if is_self else layout.user_id),
                # Own order is a sidebar page (System Setup -> Excel Maps); another user's goes back to that user
                "back_url": None if is_self else f"/sub-admins/view/{layout.user_id}",
                "shown": sum(1 for item in layout.items if item.visible),
            },
        )

    @staticmethod
    async def save(request: Request, user_id: UUID | None = None):
        form = await request.form()
        visible = set(form.getlist("visible"))
        columns = [(str(key), key in visible) for key in form.getlist("key")]
        await GetHandler.column_layout_handler(request).update(
            UpdateColumnLayoutCommand(owner=request.state.user, user_id=user_id, columns=columns)
        )
        if WebHelper.is_htmx(request):
            return Renderer.empty().success("Excel column order saved").build()
        return Renderer.redirect(_url(user_id), status_code=303)

    @staticmethod
    async def reset(request: Request, user_id: UUID | None = None) -> Response:
        await GetHandler.column_layout_handler(request).reset(
            ResetColumnLayoutCommand(owner=request.state.user, user_id=user_id)
        )
        if WebHelper.is_htmx(request):
            return Renderer.htmx_redirect(url=_url(user_id))
        return Renderer.redirect(_url(user_id), status_code=303)


def _url(user_id: UUID | None) -> str:
    return f"{_PAGE}?user_id={user_id}" if user_id else _PAGE
