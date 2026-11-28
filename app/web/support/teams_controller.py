"""
Support teams screens (Plan 25.3, REQ-59): Super Admin only

/support/teams                  list with search
/support/teams/new              create a team with its single Manager login
/support/teams/{id}             team overview: manager, members, roles
/support/teams/{id}/edit        rename / change code
/support/teams/{id}/status      enable / disable (confirm dialog)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.command import (
    CreateTeamCommand,
    ListMembersQuery,
    ListTeamsQuery,
    SetTeamActiveCommand,
    UpdateTeamCommand,
)
from app.modules.support.domain.exceptions import SupportAccessDeniedException, TeamNotFoundException
from app.web.framework.renderer import Renderer
from app.web.support.forms import FORM_ERRORS, PAGE_SIZE, build_page, error_message, page_number
from app.web.support.portal import SupportPortal

_TEAM_FIELDS = ("name", "code", "manager_name", "manager_email", "manager_mobile")


class SupportTeamsController:

    @staticmethod
    async def _super_admin(request: Request):
        """The context when the user is Super Admin, else None (the caller redirects)."""
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return None
        return ctx if ctx.is_super_admin else None

    # ------------------------------------------------------------ list

    @classmethod
    async def list_page(cls, request: Request, q: str | None = None, page: str | None = None):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        number = page_number(page)
        teams, total = await GetHandler.support_team_handler(request).list_teams(
            ListTeamsQuery(search=q, limit=PAGE_SIZE, offset=(number - 1) * PAGE_SIZE), request.state.user,
        )
        return await SupportPortal.page(
            request, template="support/pages/teams/list.html", title="Support teams", active="teams", ctx=ctx,
            model={
                "teams": teams, "q": q or "", "page": build_page("/support/teams", {"q": q}, number, total),
                "notice": request.query_params.get("notice"),
            },
        )

    # ------------------------------------------------------------ create

    @classmethod
    async def new_page(cls, request: Request):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        return await cls._form(request, ctx, values={}, error=None)

    @classmethod
    async def create(cls, request: Request):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        values = {key: str(form.get(key) or "").strip() for key in _TEAM_FIELDS}
        try:
            team = await GetHandler.support_team_handler(request).create_team(
                CreateTeamCommand(**values, manager_password=str(form.get("manager_password") or "")),
                request.state.user,
            )
        except FORM_ERRORS as exc:
            return await cls._form(request, ctx, values=values, error=error_message(exc), status_code=422)
        return Renderer.redirect(f"/support/teams/{team.id}?notice=created")

    @staticmethod
    async def _form(request, ctx, *, values, error, team=None, status_code=200):
        return await SupportPortal.page(
            request, template="support/pages/teams/form.html",
            title="Edit team" if team else "New support team", active="teams", ctx=ctx, status_code=status_code,
            model={"values": values, "error": error, "team": team},
        )

    # ------------------------------------------------------------ detail

    @classmethod
    async def detail_page(cls, request: Request, team_id: UUID):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        user = request.state.user
        try:
            team = await GetHandler.support_team_handler(request).get_team(team_id, user)
        except TeamNotFoundException:
            return Renderer.redirect("/support/teams")
        members, member_total = await GetHandler.support_member_handler(request).list_members(
            ListMembersQuery(team_id=team.id, limit=8), user,
        )
        roles = await GetHandler.support_role_handler(request).list_roles(team.id, user)
        return await SupportPortal.page(
            request, template="support/pages/teams/detail.html", title=team.name, active="teams", ctx=ctx,
            model={
                "team": team, "members": members, "member_total": member_total, "roles": roles,
                "notice": request.query_params.get("notice"),
            },
        )

    # ------------------------------------------------------------ edit and status

    @classmethod
    async def edit_page(cls, request: Request, team_id: UUID):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        try:
            team = await GetHandler.support_team_handler(request).get_team(team_id, request.state.user)
        except TeamNotFoundException:
            return Renderer.redirect("/support/teams")
        return await cls._form(request, ctx, values={"name": team.name, "code": team.code}, error=None, team=team)

    @classmethod
    async def update(cls, request: Request, team_id: UUID):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        values = {"name": str(form.get("name") or "").strip(), "code": str(form.get("code") or "").strip()}
        handler = GetHandler.support_team_handler(request)
        try:
            await handler.update_team(UpdateTeamCommand(team_id=team_id, **values), request.state.user)
        except TeamNotFoundException:
            return Renderer.redirect("/support/teams")
        except FORM_ERRORS as exc:
            team = await handler.get_team(team_id, request.state.user)
            return await cls._form(request, ctx, values=values, error=error_message(exc), team=team, status_code=422)
        return Renderer.redirect(f"/support/teams/{team_id}?notice=updated")

    @classmethod
    async def set_status(cls, request: Request, team_id: UUID):
        ctx = await cls._super_admin(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        active = str(form.get("active")) == "1"
        try:
            await GetHandler.support_team_handler(request).set_active(
                SetTeamActiveCommand(team_id=team_id, is_active=active), request.state.user,
            )
        except TeamNotFoundException:
            return Renderer.redirect("/support/teams")
        return Renderer.redirect(f"/support/teams/{team_id}?notice={'enabled' if active else 'disabled'}")
