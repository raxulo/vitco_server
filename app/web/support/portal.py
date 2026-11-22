"""
Support portal page helper (Plan 25.2)

Every support screen renders through `SupportPortal.page`: it resolves the signed-in user into a
`SupportContext` on the server, builds the permission-filtered sidebar and the shared page model
(`sp`) that `layouts/support.html` reads.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Request
from starlette.responses import Response

from app.modules.dependencies import GetHandler
from app.modules.support.application.guard import SupportContext
from app.modules.support.domain.exceptions import SupportAccessDeniedException
from app.web.framework.renderer import Renderer
from app.web.support.navigation import NavGroup, build_navigation


@dataclass(slots=True, kw_only=True)
class PortalPage:
    """The shared page model of the support layout."""

    title: str
    active: str
    nav: tuple[NavGroup, ...]
    user_name: str
    initials: str
    role_label: str
    team_name: str | None
    user_id: str
    back_to_dairy: bool
    ctx: SupportContext = field(repr=False)


class SupportPortal:

    __slots__ = ()

    @staticmethod
    async def context(request: Request) -> SupportContext:
        """The acting user's context, or `SupportAccessDeniedException` (callers redirect)."""
        user = getattr(request.state, "user", None)
        return await GetHandler.support_member_handler(request).context(user)

    @staticmethod
    def denied() -> Response:
        """Anyone without portal access goes back to their own home page."""
        return Renderer.redirect("/")

    @classmethod
    async def page(
        cls,
        request: Request,
        *,
        template: str,
        title: str,
        active: str,
        model: dict[str, Any] | None = None,
        ctx: SupportContext | None = None,
        status_code: int = 200,
    ) -> Response:
        try:
            ctx = ctx or await cls.context(request)
        except SupportAccessDeniedException:
            return cls.denied()

        user = request.state.user
        name = (user.name or "").strip() or "Support"
        member = ctx.member
        counts = await GetHandler.ticket_handler(request).queue_counts(ctx)
        page = PortalPage(
            title=title,
            active=active,
            nav=build_navigation(ctx, counts),
            user_name=name,
            initials=name[:1].upper(),
            role_label="Super Admin" if ctx.is_super_admin else (member.role_name or "Member" if member else "Member"),
            team_name=member.team_name if member else None,
            user_id=str(ctx.user_id),
            back_to_dairy=ctx.is_super_admin,
            ctx=ctx,
        )
        context = {"sp": page}
        if model:
            context.update(model)
        return Renderer.page(request=request, template=template, model=context, status_code=status_code)
