"""
Support roles screens (Plan 25.3, REQ-61): the team Manager (or a member with
`support.role.manage`); Super Admin works inside a team by passing `?team=<id>`.

/support/roles                 the team's roles with member counts
/support/roles/new             a new role with a grouped permission checklist
/support/roles/{id}/edit       rename and change permissions
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.command import CreateRoleCommand, UpdateRoleCommand
from app.modules.support.domain.exceptions import (
    RoleNotFoundException,
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    TeamNotFoundException,
)
from app.modules.support.domain.permissions import (
    ASSIGNABLE_PERMISSIONS,
    PERMISSION_GROUPS,
    SupportPermission,
)
from app.web.framework.renderer import Renderer
from app.web.support.forms import FORM_ERRORS, error_message, optional_uuid
from app.web.support.portal import SupportPortal

_DENIED = (SupportAccessDeniedException, SupportPermissionDeniedException, TeamNotFoundException)

# The checklist offers only what a team role may hold
_GROUPS = [
    (label, [(str(permission), text) for permission, text in entries if permission in ASSIGNABLE_PERMISSIONS])
    for label, entries in PERMISSION_GROUPS
]


def _list_url(ctx, team_id: UUID | None, notice: str | None = None) -> str:
    params = []
    if ctx.is_super_admin and team_id:
        params.append(f"team={team_id}")
    if notice:
        params.append(f"notice={notice}")
    return "/support/roles" + ("?" + "&".join(params) if params else "")


class SupportRolesController:

    @staticmethod
    async def _context(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return None, None
        if not ctx.has(SupportPermission.ROLE_MANAGE):
            return None, None
        team_id = optional_uuid(request.query_params.get("team")) if ctx.is_super_admin else ctx.team_id
        if team_id is None:
            return None, None
        return ctx, team_id

    @classmethod
    async def list_page(cls, request: Request):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        user = request.state.user
        try:
            team = await GetHandler.support_team_handler(request).get_team(team_id, user)
            roles = await GetHandler.support_role_handler(request).list_roles(team_id, user)
        except _DENIED:
            return SupportPortal.denied()
        return await SupportPortal.page(
            request, template="support/pages/roles/list.html", title="Roles and permissions",
            active="teams" if ctx.is_super_admin else "roles", ctx=ctx,
            model={
                "team": team, "roles": roles, "notice": request.query_params.get("notice"),
                "suffix": f"?team={team_id}" if ctx.is_super_admin else "",
                "total_permissions": len(ASSIGNABLE_PERMISSIONS),
            },
        )

    @classmethod
    async def new_page(cls, request: Request):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        return await cls._form(request, ctx, team_id, name="", chosen=set(), error=None)

    @classmethod
    async def create(cls, request: Request):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        name = str(form.get("name") or "").strip()
        chosen = [str(value) for value in form.getlist("permissions")]
        try:
            await GetHandler.support_role_handler(request).create_role(
                CreateRoleCommand(team_id=team_id, name=name, permissions=chosen), request.state.user,
            )
        except FORM_ERRORS as exc:
            return await cls._form(
                request, ctx, team_id, name=name, chosen=set(chosen), error=error_message(exc), status_code=422,
            )
        return Renderer.redirect(_list_url(ctx, team_id, "created"))

    @classmethod
    async def edit_page(cls, request: Request, role_id: UUID):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        try:
            role = await GetHandler.support_role_handler(request).get_role(role_id, request.state.user)
        except RoleNotFoundException:
            return Renderer.redirect(_list_url(ctx, team_id))
        return await cls._form(
            request, ctx, role.team_id, name=role.name, chosen={str(value) for value in role.permissions},
            error=None, role=role,
        )

    @classmethod
    async def update(cls, request: Request, role_id: UUID):
        ctx, team_id = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        handler = GetHandler.support_role_handler(request)
        try:
            role = await handler.get_role(role_id, request.state.user)
        except RoleNotFoundException:
            return Renderer.redirect(_list_url(ctx, team_id))
        form = await request.form()
        name = str(form.get("name") or "").strip()
        chosen = [str(value) for value in form.getlist("permissions")]
        try:
            await handler.update_role(UpdateRoleCommand(role_id=role.id, name=name, permissions=chosen), request.state.user)
        except FORM_ERRORS as exc:
            return await cls._form(
                request, ctx, role.team_id, name=name, chosen=set(chosen), error=error_message(exc), role=role,
                status_code=422,
            )
        return Renderer.redirect(_list_url(ctx, role.team_id, "updated"))

    @staticmethod
    async def _form(request, ctx, team_id, *, name, chosen, error, role=None, status_code=200):
        team = await GetHandler.support_team_handler(request).get_team(team_id, request.state.user)
        return await SupportPortal.page(
            request, template="support/pages/roles/form.html", title="Edit role" if role else "New role",
            active="teams" if ctx.is_super_admin else "roles", ctx=ctx, status_code=status_code,
            model={
                "team": team, "role": role, "name": name, "chosen": chosen, "error": error, "groups": _GROUPS,
                "suffix": f"?team={team_id}" if ctx.is_super_admin else "",
            },
        )
