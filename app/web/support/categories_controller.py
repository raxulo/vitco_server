"""
Support categories screens (Plan 26.3, REQ-66): Super Admin only.

/support/categories                 list with default team and priority
/support/categories/new             create
/support/categories/{id}/edit       name, default team, default priority
/support/categories/{id}/status     switch on / off (an off category is hidden from the app)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.command import ListTeamsQuery
from app.modules.support.application.ticket_command import CreateCategoryCommand, UpdateCategoryCommand
from app.modules.support.domain.enums import TicketPriority
from app.modules.support.domain.exceptions import CategoryNotFoundException, SupportAccessDeniedException
from app.web.framework.renderer import Renderer
from app.web.support.forms import FORM_ERRORS, error_message, optional_uuid
from app.web.support.portal import SupportPortal

_LIST = "/support/categories"


class SupportCategoriesController:

    @staticmethod
    async def _context(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return None
        return ctx if ctx.is_super_admin else None

    @staticmethod
    async def _form(request: Request, ctx, *, values: dict, error: str | None, category=None, status_code: int = 200):
        teams, _total = await GetHandler.support_team_handler(request).list_teams(
            ListTeamsQuery(limit=100), request.state.user,
        )
        return await SupportPortal.page(
            request, template="support/pages/categories/form.html",
            title="Edit category" if category else "New category", active="categories", ctx=ctx,
            status_code=status_code,
            model={
                "values": values, "error": error, "category": category,
                "team_options": [("", "No default team (unassigned pool)")] + [
                    (str(team.id), team.name + ("" if team.is_active else " (disabled)")) for team in teams
                ],
                "priority_options": [(item.value, item.label) for item in TicketPriority],
            },
        )

    # ------------------------------------------------------------ list

    @classmethod
    async def list_page(cls, request: Request):
        ctx = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        categories = await GetHandler.ticket_handler(request).list_categories(request.state.user, active_only=False)
        return await SupportPortal.page(
            request, template="support/pages/categories/list.html", title="Categories", active="categories", ctx=ctx,
            model={"categories": categories, "notice": request.query_params.get("notice")},
        )

    # ------------------------------------------------------------ create

    @classmethod
    async def new_page(cls, request: Request):
        ctx = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        return await cls._form(
            request, ctx, values={"name": "", "team": "", "priority": TicketPriority.MEDIUM.value}, error=None,
        )

    @classmethod
    async def create(cls, request: Request):
        ctx = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        values = {key: str(form.get(key) or "").strip() for key in ("name", "team", "priority")}
        try:
            await GetHandler.ticket_handler(request).create_category(
                CreateCategoryCommand(
                    name=values["name"],
                    default_team_id=optional_uuid(values["team"]),
                    default_priority=TicketPriority(values["priority"] or TicketPriority.MEDIUM.value),
                ),
                request.state.user,
            )
        except ValueError:
            return await cls._form(request, ctx, values=values, error="Choose a priority.", status_code=422)
        except FORM_ERRORS as exc:
            return await cls._form(request, ctx, values=values, error=error_message(exc), status_code=422)
        return Renderer.redirect(f"{_LIST}?notice=created")

    # ------------------------------------------------------------ edit

    @classmethod
    async def edit_page(cls, request: Request, category_id: UUID):
        ctx = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        try:
            category = await GetHandler.ticket_handler(request).get_category(category_id, request.state.user)
        except CategoryNotFoundException:
            return Renderer.redirect(f"{_LIST}?notice=missing")
        values = {
            "name": category.name,
            "team": str(category.default_team_id or ""),
            "priority": category.default_priority.value,
        }
        return await cls._form(request, ctx, values=values, error=None, category=category)

    @classmethod
    async def update(cls, request: Request, category_id: UUID):
        ctx = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        handler = GetHandler.ticket_handler(request)
        try:
            category = await handler.get_category(category_id, request.state.user)
        except CategoryNotFoundException:
            return Renderer.redirect(f"{_LIST}?notice=missing")
        form = await request.form()
        values = {key: str(form.get(key) or "").strip() for key in ("name", "team", "priority")}
        try:
            await handler.update_category(
                UpdateCategoryCommand(
                    category_id=category.id,
                    name=values["name"],
                    default_team_id=optional_uuid(values["team"]),
                    set_team=True,
                    default_priority=TicketPriority(values["priority"] or category.default_priority.value),
                ),
                request.state.user,
            )
        except ValueError:
            return await cls._form(
                request, ctx, values=values, error="Choose a priority.", category=category, status_code=422,
            )
        except FORM_ERRORS as exc:
            return await cls._form(
                request, ctx, values=values, error=error_message(exc), category=category, status_code=422,
            )
        return Renderer.redirect(f"{_LIST}?notice=updated")

    @classmethod
    async def set_status(cls, request: Request, category_id: UUID):
        ctx = await cls._context(request)
        if ctx is None:
            return SupportPortal.denied()
        form = await request.form()
        active = str(form.get("active")) == "1"
        try:
            await GetHandler.ticket_handler(request).update_category(
                UpdateCategoryCommand(category_id=category_id, is_active=active), request.state.user,
            )
        except CategoryNotFoundException:
            return Renderer.redirect(f"{_LIST}?notice=missing")
        return Renderer.redirect(f"{_LIST}?notice={'enabled' if active else 'disabled'}")
