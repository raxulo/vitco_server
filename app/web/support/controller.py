"""
Support portal home and design kit (Plan 25.2)

`/support`      : the member's start page (team, role, what they may do).
`/support/_kit` : every component of the design system on one page, Super Admin only (visual review aid).
"""

from __future__ import annotations

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.command import ListTeamsQuery
from app.modules.support.domain.exceptions import SupportAccessDeniedException
from app.modules.support.domain.permissions import PERMISSION_GROUPS
from app.web.support.portal import SupportPortal


class SupportHomeController:

    @staticmethod
    async def home(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()

        user = request.state.user
        model: dict = {"is_super_admin": ctx.is_super_admin}
        if ctx.is_super_admin:
            _, total = await GetHandler.support_team_handler(request).list_teams(ListTeamsQuery(limit=1), user)
            model["team_total"] = total
        else:
            model["team"] = await GetHandler.support_team_handler(request).get_team(ctx.team_id, user)
            model["member"] = ctx.member
            model["permission_groups"] = [
                (label, [(permission, help_text) for permission, help_text in entries if ctx.has(permission)])
                for label, entries in PERMISSION_GROUPS
            ]

        return await SupportPortal.page(
            request, template="support/pages/dashboard.html", title="Dashboard", active="dashboard", model=model, ctx=ctx,
        )

    @staticmethod
    async def kit(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        if not ctx.is_super_admin:
            return SupportPortal.denied()
        return await SupportPortal.page(
            request, template="support/pages/kit.html", title="Design kit", active="", ctx=ctx,
        )
