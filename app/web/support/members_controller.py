"""
Support members screens (Plan 25.3, REQ-60): the team Manager (or a member with
`support.member.manage`); Super Admin works inside a team by passing `?team=<id>`.

/support/members                 list with search
/support/members/new             create a member login with a support role
/support/members/{id}/edit       name, mobile, role
/support/members/{id}/status     enable / disable (confirm dialog)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.command import (
    CreateMemberCommand,
    ListMembersQuery,
    SetMemberActiveCommand,
    UpdateMemberCommand,
)
from app.modules.support.domain.exceptions import (
    MemberNotFoundException,
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TeamNotFoundException,
)
from app.modules.support.domain.permissions import SupportPermission
from app.web.framework.renderer import Renderer
from app.web.support.forms import (
    FORM_ERRORS,
    PAGE_SIZE,
    build_page,
    error_message,
    optional_uuid,
    page_number,
)
from app.web.support.portal import SupportPortal

_DENIED = (SupportAccessDeniedException, SupportPermissionDeniedException, TeamNotFoundException)


def _suffix(team_id: UUID | None) -> str:
    return f"?team={team_id}" if team_id else ""


def _list_url(ctx, team_id: UUID | None, notice: str | None = None) -> str:
    """The members list; Super Admin keeps its `team` in the URL."""
    params = []
    if ctx.is_super_admin and team_id:
        params.append(f"team={team_id}")
    if notice:
        params.append(f"notice={notice}")
    return "/support/members" + ("?" + "&".join(params) if params else "")


class SupportMembersController:

    @staticmethod
    async def _context(request: Request):
        """Context of a user allowed to manage members, or None. Super Admin must name a team."""
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return None, None
        if not ctx.has(SupportPermission.MEMBER_MANAGE):
            return None, None
        team_id = optional_uuid(request.query_params.get("team")) if ctx.is_super_admin else ctx.team_id
        if team_id is None:
            return None, None
        return ctx, team_id

    @staticmethod
    def _active(ctx) -> str:
        return "teams" if ctx.is_super_admin else "members"

    # ------------------------------------------------------------ list

    @classmethod
    async def list_page(cls, request: Request, q: str | None = None, page: str | None = None):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        user = request.state.user
        number = page_number(page)
        try:
            team = await GetHandler.support_team_handler(request).get_team(team_id, user)
            members, total = await GetHandler.support_member_handler(request).list_members(
                ListMembersQuery(team_id=team_id, search=q, limit=PAGE_SIZE, offset=(number - 1) * PAGE_SIZE), user,
            )
        except _DENIED:
            return SupportPortal.denied()
        params = {"q": q, "team": str(team_id) if ctx.is_super_admin else None}
        return await SupportPortal.page(
            request, template="support/pages/members/list.html", title="Members", active=cls._active(ctx), ctx=ctx,
            model={
                "team": team, "members": members, "q": q or "", "notice": request.query_params.get("notice"),
                "page": build_page("/support/members", params, number, total),
                "suffix": _suffix(team_id if ctx.is_super_admin else None),
                "me": ctx.user_id,
            },
        )

    # ------------------------------------------------------------ create

    @classmethod
    async def new_page(cls, request: Request):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        return await cls._form(request, ctx, team_id, values={}, error=None)

    @classmethod
    async def create(cls, request: Request):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        values = {key: str(form.get(key) or "").strip() for key in ("name", "email", "mobile", "role_id")}
        try:
            role_id = optional_uuid(values["role_id"])
            if role_id is None:
                raise SupportValidationException("Choose a role for the member.")
            await GetHandler.support_member_handler(request).create_member(
                CreateMemberCommand(
                    team_id=team_id, role_id=role_id, name=values["name"], email=values["email"],
                    mobile=values["mobile"], password=str(form.get("password") or ""),
                ),
                request.state.user,
            )
        except FORM_ERRORS as exc:
            return await cls._form(request, ctx, team_id, values=values, error=error_message(exc), status_code=422)
        return Renderer.redirect(_list_url(ctx, team_id, "created"))

    @staticmethod
    async def _form(request, ctx, team_id, *, values, error, member=None, status_code=200):
        roles = await GetHandler.support_role_handler(request).list_roles(team_id, request.state.user)
        team = await GetHandler.support_team_handler(request).get_team(team_id, request.state.user)
        return await SupportPortal.page(
            request, template="support/pages/members/form.html",
            title="Edit member" if member else "New member",
            active="teams" if ctx.is_super_admin else "members", ctx=ctx, status_code=status_code,
            model={
                "values": values, "error": error, "member": member, "team": team,
                "role_options": [(str(role.id), role.name) for role in roles],
                "roles": roles,
                "suffix": _suffix(team_id if ctx.is_super_admin else None),
            },
        )

    # ------------------------------------------------------------ edit and status

    @classmethod
    async def edit_page(cls, request: Request, member_id: UUID):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        try:
            member = await GetHandler.support_member_handler(request).get_member(member_id, request.state.user)
        except MemberNotFoundException:
            return Renderer.redirect(_list_url(ctx, team_id))
        values = {"name": member.name, "email": member.email, "mobile": member.mobile or "",
                  "role_id": str(member.role_id or "")}
        return await cls._form(request, ctx, member.team_id, values=values, error=None, member=member)

    @classmethod
    async def update(cls, request: Request, member_id: UUID):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        handler = GetHandler.support_member_handler(request)
        user = request.state.user
        try:
            member = await handler.get_member(member_id, user)
        except MemberNotFoundException:
            return Renderer.redirect(_list_url(ctx, team_id))
        form = await request.form()
        values = {key: str(form.get(key) or "").strip() for key in ("name", "mobile", "role_id")}
        values["email"] = member.email
        try:
            await handler.update_member(
                UpdateMemberCommand(
                    member_id=member.id, name=values["name"], mobile=values["mobile"],
                    role_id=None if member.is_manager else optional_uuid(values["role_id"]),
                ),
                user,
            )
        except FORM_ERRORS as exc:
            return await cls._form(
                request, ctx, member.team_id, values=values, error=error_message(exc), member=member, status_code=422,
            )
        return Renderer.redirect(_list_url(ctx, member.team_id, "updated"))

    @classmethod
    async def set_status(cls, request: Request, member_id: UUID):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        active = str(form.get("active")) == "1"
        try:
            await GetHandler.support_member_handler(request).set_active(
                SetMemberActiveCommand(member_id=member_id, is_active=active), request.state.user,
            )
            notice = "enabled" if active else "disabled"
        except MemberNotFoundException:
            notice = "missing"
        except FORM_ERRORS:
            notice = "refused"          # the manager or oneself: explained by the notice on the list
        return Renderer.redirect(_list_url(ctx, team_id, notice))
