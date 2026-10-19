from uuid import UUID
from decimal import Decimal
from datetime import datetime
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.modules.dependencies import GetHandler
from app.modules.advanceditem.application.command import (
    CreateAdvanceCommand,
    AdvanceItemCommand,
    AdvanceListQuery,
)
from app.modules.farmer.application.command import ListFarmerQuery
from app.modules.masters.items.application.command import ListItemMasterQuery
from app.web.framework.renderer import Renderer


class AdvancedItemController:

    __slots__ = ()

    @staticmethod
    async def list_page(
        request: Request,
        page: int = 1,
        limit: int = 10,
    ):
        owner = request.state.user
        advance_service = GetHandler.advance_item_service(request)

        query = AdvanceListQuery(
            owner=owner,
            page=page,
            size=limit,
        )
        response = await advance_service.list(query)

        return Renderer.page(
            request=request,
            template="pages/advance_item/list.html",
            model={
                "items": response.items,
                "page": response.page,
                "limit": response.size,
                "total_pages": response.total_page,
            }
        )

    @staticmethod
    async def create_page(request: Request):
        owner = request.state.user
        farmer_handler = GetHandler.farmer_handler(request)
        item_handler = GetHandler.item_master_handler(request)

        # Fetch farmers and item masters
        farmers = await farmer_handler.list(ListFarmerQuery(limit=500, owner=owner))
        items = await item_handler.list(ListItemMasterQuery(page=1, size=500, owner=owner))

        # Filter active items
        active_items = [item for item in items if item.is_active]

        return Renderer.page(
            request=request,
            template="pages/advance_item/create.html",
            model={
                "farmers": farmers,
                "items": active_items,
                "error": None,
            }
        )

    @staticmethod
    async def post_create(request: Request):
        owner = request.state.user
        advance_service = GetHandler.advance_item_service(request)
        farmer_handler = GetHandler.farmer_handler(request)
        item_handler = GetHandler.item_master_handler(request)

        form_data = await request.form()
        user_id_str = form_data.get("user_id")
        advance_date_str = form_data.get("advance_date")
        notes = form_data.get("notes") or ""

        # Parse selected items
        item_ids = form_data.getlist("item_ids[]")
        quantities = form_data.getlist("quantities[]")

        # Basic validation
        if not user_id_str or not item_ids:
            selected_user = None
            if user_id_str:
                try:
                    db_manager = request.app.state.application.container.database
                    from app.modules.administration.infrastructure.models import UserModel
                    from sqlalchemy import select
                    stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == UUID(user_id_str))
                    res = await db_manager.session.execute(stmt)
                    selected_user = res.one_or_none()
                except Exception:
                    pass
            farmers = await farmer_handler.list(ListFarmerQuery(limit=500, owner=owner))
            items = await item_handler.list(ListItemMasterQuery(page=1, size=500, owner=owner))
            active_items = [item for item in items if item.is_active]
            return Renderer.page(
                request=request,
                template="pages/advance_item/create.html",
                model={
                    "farmers": farmers,
                    "items": active_items,
                    "selected_user": selected_user,
                    "error": "Please select a counterparty and at least one item.",
                }
            )

        try:
            user_id = UUID(user_id_str)
            advance_date = datetime.fromisoformat(advance_date_str) if advance_date_str else datetime.utcnow()

            # Build item commands list
            item_commands = []
            for item_id, qty in zip(item_ids, quantities):
                if item_id and qty:
                    qty_val = Decimal(qty)
                    if qty_val > 0:
                        item_commands.append(
                            AdvanceItemCommand(
                                item_master_id=UUID(item_id),
                                quantity=qty_val,
                             )
                        )

            if not item_commands:
                raise ValueError("Must select at least one item with quantity greater than zero.")

            command = CreateAdvanceCommand(
                user_id=user_id,
                advance_date=advance_date,
                created_by=owner.id,
                items=tuple(item_commands),
                notes=notes,
            )

            await advance_service.create(command)
            return RedirectResponse(url="/advance-items/", status_code=303)

        except Exception as e:
            selected_user = None
            if user_id_str:
                try:
                    db_manager = request.app.state.application.container.database
                    from app.modules.administration.infrastructure.models import UserModel
                    from sqlalchemy import select
                    stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == UUID(user_id_str))
                    res = await db_manager.session.execute(stmt)
                    selected_user = res.one_or_none()
                except Exception:
                    pass
            farmers = await farmer_handler.list(ListFarmerQuery(limit=500, owner=owner))
            items = await item_handler.list(ListItemMasterQuery(page=1, size=500, owner=owner))
            active_items = [item for item in items if item.is_active]
            return Renderer.page(
                request=request,
                template="pages/advance_item/create.html",
                model={
                    "farmers": farmers,
                    "items": active_items,
                    "selected_user": selected_user,
                    "error": f"Failed to create advance item: {str(e)}",
                }
            )

    @staticmethod
    async def view_page(request: Request, id: UUID):
        advance_service = GetHandler.advance_item_service(request)
        detail = await advance_service.get_detail(id)

        if not detail:
            return RedirectResponse(url="/advance-items/", status_code=303)

        return Renderer.page(
            request=request,
            template="pages/advance_item/view.html",
            model={
                "advance": detail,
            }
        )
