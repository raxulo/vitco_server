from uuid import UUID
from decimal import Decimal
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

from app.modules.dependencies import GetHandler
from app.modules.common.settings.infrastructure.permissions import can_create_masters
from app.modules.masters.items.application.command import (
    CreateItemMasterCommand,
    UpdateItemMasterCommand,
    DeleteItemMasterCommand,
    ListItemMasterQuery,
)
from app.modules.masters.units.application.command import ListUnitMasterQuery
from app.web.framework.renderer import Renderer


class ItemController:

    __slots__ = ()

    @staticmethod
    async def page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
    ):
        owner = request.state.user
        handler = GetHandler.item_master_handler(request)
        unit_handler = GetHandler.unit_master_handler(request)

        # Get count
        if search.strip():
            total_items = await handler.count_search(keyword=search.strip(), owner=owner)
        else:
            total_items = await handler.count(owner=owner)

        total_pages = (total_items + limit - 1) // limit

        query = ListItemMasterQuery(
            page=page,
            size=limit,
            keyword=search.strip() if search.strip() else None,
            owner=owner,
        )
        items = await handler.list(query)

        # Fetch units for dropdown
        units = await unit_handler.list(ListUnitMasterQuery(size=500))

        # Build a unit name lookup
        unit_names = {u.id: u.name for u in units}
        db = request.app.state.application.container.database

        return Renderer.page(
            request=request,
            template="pages/item/list.html",
            model={
                "items": items,
                "units": units,
                "unit_names": unit_names,
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
        code_str = form.get("code", "0")
        name = form.get("name", "").strip()
        unit_id_str = form.get("unit_id", "")
        rate_str = form.get("rate", "0.00")

        owner = request.state.user
        handler = GetHandler.item_master_handler(request)
        try:
            item_code = int(code_str)
            unit_id = UUID(unit_id_str)
            rate = Decimal(rate_str)

            await handler.create(
                CreateItemMasterCommand(
                    item_code=item_code,
                    item_name=name,
                    unit_id=unit_id,
                    rate=rate,
                    created_by=owner.id,
                ), owner=owner
            )
        except Exception as e:
            # Re-render list with error
            unit_handler = GetHandler.unit_master_handler(request)
            query = ListItemMasterQuery(page=1, size=10, owner=owner)
            items = await handler.list(query)
            units = await unit_handler.list(ListUnitMasterQuery(size=500))
            unit_names = {u.id: u.name for u in units}
            total_items = await handler.count(owner=owner)

            return Renderer.page(
                request=request,
                template="pages/item/list.html",
                model={
                    "items": items,
                    "units": units,
                    "unit_names": unit_names,
                    "search": "",
                    "page": 1,
                    "total_pages": 1,
                    "total": total_items,
                    "error": str(e),
                },
            )

        return RedirectResponse("/items/", status_code=303)

    @staticmethod
    async def post_edit(request: Request, id: UUID):
        form = await request.form()
        code_str = form.get("code", "0")
        name = form.get("name", "").strip()
        unit_id_str = form.get("unit_id", "")
        rate_str = form.get("rate", "0.00")
        is_active_str = form.get("is_active", "true")
        is_active = is_active_str.lower() == "true"

        owner = request.state.user
        handler = GetHandler.item_master_handler(request)
        try:
            item_code = int(code_str)
            unit_id = UUID(unit_id_str)
            rate = Decimal(rate_str)

            await handler.update(
                UpdateItemMasterCommand(
                    id=id,
                    item_code=item_code,
                    item_name=name,
                    unit_id=unit_id,
                    rate=rate,
                    is_active=is_active,
                    owner=owner,
                )
            )
        except Exception as e:
            # Re-render list with error
            unit_handler = GetHandler.unit_master_handler(request)
            query = ListItemMasterQuery(page=1, size=10, owner=owner)
            items = await handler.list(query)
            units = await unit_handler.list(ListUnitMasterQuery(size=500))
            unit_names = {u.id: u.name for u in units}
            total_items = await handler.count(owner=owner)

            return Renderer.page(
                request=request,
                template="pages/item/list.html",
                model={
                    "items": items,
                    "units": units,
                    "unit_names": unit_names,
                    "search": "",
                    "page": 1,
                    "total_pages": 1,
                    "total": total_items,
                    "error": str(e),
                },
            )

        return RedirectResponse("/items/", status_code=303)

    @staticmethod
    async def post_delete(request: Request, id: UUID):
        owner = request.state.user
        handler = GetHandler.item_master_handler(request)
        try:
            await handler.delete(DeleteItemMasterCommand(id=id, owner=owner))
        except Exception:
            pass

        return RedirectResponse("/items/", status_code=303)

    @staticmethod
    async def validate_code(request: Request, code: int | None = None):
        if code is None:
            return PlainTextResponse("")

        handler = GetHandler.item_master_handler(request)
        exists = await handler._repository.exists_code(code)
        if exists:
            return PlainTextResponse('<span style="color:#ef4444; font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> Code already in use</span>')
        else:
            return PlainTextResponse('<span style="color:#10b981; font-weight:700;"><i class="fa-solid fa-circle-check"></i> Code available</span>')
