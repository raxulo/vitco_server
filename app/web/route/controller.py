from uuid import UUID
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

from app.modules.dependencies import GetHandler
from app.modules.masters.route.application.command import (
    CreateRouteMasterCommand,
    UpdateRouteMasterCommand,
    DeleteRouteMasterCommand,
    ListRouteMasterQuery,
)
from app.web.framework.renderer import Renderer


class RouteController:

    __slots__ = ()

    @staticmethod
    async def page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
    ):
        owner = request.state.user
        handler = GetHandler.route_master_handler(request)

        # Get count
        if search.strip():
            total_items = await handler.count_search(keyword=search.strip(), owner=owner)
        else:
            total_items = await handler.count(owner=owner)

        total_pages = (total_items + limit - 1) // limit

        query = ListRouteMasterQuery(
            page=page,
            size=limit,
            keyword=search.strip() if search.strip() else None,
            owner=owner,
        )
        items = await handler.list(query)

        return Renderer.page(
            request=request,
            template="pages/route/list.html",
            model={
                "items": items,
                "search": search,
                "page": page,
                "total_pages": total_pages,
                "total": total_items,
                "error": None,
            },
        )

    @staticmethod
    async def post_create(request: Request):
        form = await request.form()
        code_str = form.get("code", "0")
        name = form.get("name", "").strip()

        owner = request.state.user
        handler = GetHandler.route_master_handler(request)
        try:
            route_code = int(code_str)
            await handler.create(
                CreateRouteMasterCommand(
                    route_code=route_code,
                    route_name=name,
                    created_by=owner.id,
                    owner=owner,
                )
            )
        except Exception as e:
            # Re-render with error
            query = ListRouteMasterQuery(page=1, size=10, owner=owner)
            items = await handler.list(query)
            total_items = await handler.count(owner=owner)
            return Renderer.page(
                request=request,
                template="pages/route/list.html",
                model={
                    "items": items,
                    "search": "",
                    "page": 1,
                    "total_pages": 1,
                    "total": total_items,
                    "error": str(e),
                },
            )

        return RedirectResponse("/routes/", status_code=303)

    @staticmethod
    async def post_edit(request: Request, id: UUID):
        form = await request.form()
        code_str = form.get("code", "0")
        name = form.get("name", "").strip()
        is_active_str = form.get("is_active", "true")
        is_active = is_active_str.lower() == "true"

        owner = request.state.user
        handler = GetHandler.route_master_handler(request)
        try:
            route_code = int(code_str)
            await handler.update(
                UpdateRouteMasterCommand(
                    id=id,
                    route_code=route_code,
                    route_name=name,
                    is_active=is_active,
                    owner=owner,
                )
            )
        except Exception as e:
            # Re-render with error
            query = ListRouteMasterQuery(page=1, size=10, owner=owner)
            items = await handler.list(query)
            total_items = await handler.count(owner=owner)
            return Renderer.page(
                request=request,
                template="pages/route/list.html",
                model={
                    "items": items,
                    "search": "",
                    "page": 1,
                    "total_pages": 1,
                    "total": total_items,
                    "error": str(e),
                },
            )

        return RedirectResponse("/routes/", status_code=303)

    @staticmethod
    async def post_delete(request: Request, id: UUID):
        owner = request.state.user
        handler = GetHandler.route_master_handler(request)
        try:
            await handler.delete(DeleteRouteMasterCommand(id=id, owner=owner))
        except Exception:
            pass

        return RedirectResponse("/routes/", status_code=303)

    @staticmethod
    async def validate_code(request: Request, code: int | None = None):
        if code is None:
            return PlainTextResponse("")

        owner = request.state.user
        handler = GetHandler.route_master_handler(request)
        exists = await handler._repository.exists_code(code, owner)
        if exists:
            return PlainTextResponse('<span style="color:#ef4444; font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> Code already in use</span>')
        else:
            return PlainTextResponse('<span style="color:#10b981; font-weight:700;"><i class="fa-solid fa-circle-check"></i> Code available</span>')
