from uuid import UUID
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.modules.dependencies import GetHandler
from app.modules.common.settings.infrastructure.permissions import can_create_masters
from app.modules.masters.units.application.command import (
    CreateUnitMasterCommand,
    UpdateUnitMasterCommand,
    DeleteUnitMasterCommand,
    ListUnitMasterQuery,
)
from app.web.framework.renderer import Renderer


class UnitController:

    __slots__ = ()

    @staticmethod
    async def page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
    ):
        owner = request.state.user
        handler = GetHandler.unit_master_handler(request)

        if search.strip():
            total_items = await handler.count_search(keyword=search.strip(), owner=owner)
        else:
            total_items = await handler.count(owner=owner)

        total_pages = (total_items + limit - 1) // limit

        query = ListUnitMasterQuery(
            page=page,
            size=limit,
            keyword=search.strip() if search.strip() else None,
            owner=owner,
        )
        items = await handler.list(query)
        db = request.app.state.application.container.database

        return Renderer.page(
            request=request,
            template="pages/unit/list.html",
            model={
                "items": items,
                "search": search,
                "page": page,
                "total_pages": total_pages,
                "total": total_items,
                "error": None,
                "can_create": await can_create_masters(db.session, owner),
            },
        )

    @staticmethod
    async def post_create(request: Request):
        form = await request.form()
        name = form.get("name", "").strip()

        owner = request.state.user
        handler = GetHandler.unit_master_handler(request)
        try:
            await handler.create(
                CreateUnitMasterCommand(
                    name=name,
                    created_by=owner.id,
                ),
                owner=owner,
            )
        except Exception as e:
            # Re-render with error
            query = ListUnitMasterQuery(page=1, size=10, owner=owner)
            items = await handler.list(query)
            total_items = await handler.count(owner=owner)
            return Renderer.page(
                request=request,
                template="pages/unit/list.html",
                model={
                    "items": items,
                    "search": "",
                    "page": 1,
                    "total_pages": 1,
                    "total": total_items,
                    "error": str(e),
                    "can_create": await can_create_masters(
                        request.app.state.application.container.database.session, owner
                    ),
                },
            )

        return RedirectResponse("/units/", status_code=303)

    @staticmethod
    async def post_edit(request: Request, id: UUID):
        form = await request.form()
        name = form.get("name", "").strip()
        is_active_str = form.get("is_active", "true")
        is_active = is_active_str.lower() == "true"

        owner = request.state.user
        handler = GetHandler.unit_master_handler(request)
        try:
            await handler.update(
                UpdateUnitMasterCommand(
                    id=id,
                    name=name,
                    is_active=is_active,
                    owner=owner,
                )
            )
        except Exception as e:
            # Re-render with error
            query = ListUnitMasterQuery(page=1, size=10, owner=owner)
            items = await handler.list(query)
            total_items = await handler.count(owner=owner)
            return Renderer.page(
                request=request,
                template="pages/unit/list.html",
                model={
                    "items": items,
                    "search": "",
                    "page": 1,
                    "total_pages": 1,
                    "total": total_items,
                    "error": str(e),
                    "can_create": await can_create_masters(
                        request.app.state.application.container.database.session, owner
                    ),
                },
            )

        return RedirectResponse("/units/", status_code=303)

    @staticmethod
    async def post_delete(request: Request, id: UUID):
        owner = request.state.user
        handler = GetHandler.unit_master_handler(request)
        try:
            await handler.delete(DeleteUnitMasterCommand(id=id, owner=owner))
        except Exception:
            pass

        return RedirectResponse("/units/", status_code=303)
