"""
VLCC Collection Web Controller
"""

from datetime import datetime, timedelta
from uuid import UUID
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.exceptions.base import ForbiddenException
from app.modules.administration.domain.enums import Role
from app.modules.dependencies import GetHandler
from app.modules.collections.vlcc_collection.application.command import (
    GetVlccCollectionQuery,
    ListVlccCollectionsQuery,
    DeleteVlccCollectionCommand,
)
from app.modules.vlcc.application.command import ListVlccQuery, GetVlccQuery
from app.modules.farmer.application.command import ListFarmerQuery, GetFarmerQuery
from app.modules.ratechart.application.command import GetAssignmentsByOwnerQuery
from app.modules.common.milk_quality.application.command import GetMilkQualityConfigQuery
from app.web.framework.renderer import Renderer
from app.web.vlcc_collection.assembler import VlccCollectionAssembler
from app.modules.collections.vlcc_collection.presentation.requests import (
    CreateVlccCollectionRequest,
    UpdateVlccCollectionRequest,
)
from app.modules.collections.mcc_collection.domain.enums import CollectionShift, MilkType
from app.core.clock import now_naive_ist


class VlccCollectionController:

    __slots__ = ()

    # =========================================================
    # LIST PAGE
    # =========================================================

    @staticmethod
    async def page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
        date_from: str = "",
        date_to: str = "",
    ):
        user = getattr(request.state, "user", None)
        if getattr(user, "is_farmer_vlcc", False):
            return Renderer.redirect("/mcc-collections/")

        handler = GetHandler.vlcc_collection_handler(request)

        # Search: VLCC name / farmer name / farmer code; dates (yyyy-mm-dd) are whole days
        keyword = search.strip()
        start = VlccCollectionController._parse_day(date_from)
        end = VlccCollectionController._parse_day(date_to)
        if start and end and start > end:
            start, end = end, start
        end_exclusive = end + timedelta(days=1) if end else None

        total_items = await handler.count(owner=user, keyword=keyword, date_from=start, date_to=end_exclusive)
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        result = await handler.list(
            ListVlccCollectionsQuery(
                page=page,
                size=limit,
                keyword=keyword,
                date_from=start,
                date_to=end_exclusive,
            ),
            owner=user
        )

        user = request.state.user
        detailed_items = []
        # for item in result:
        #     vlcc = None
        #     try:
        #         vlcc = await vlcc_handler.get(GetVlccQuery(id=item.vlcc_id, owner=user))
        #     except Exception:
        #         pass

        #     farmer = None
        #     try:
        #         farmer = await farmer_handler.get(GetFarmerQuery(id=item.farmer_id, owner=user))
        #     except Exception:
        #         pass

            # detailed_items.append({
            #     "collection": item,
            #     "vlcc": vlcc,
            #     "farmer": farmer,
            # })

        return Renderer.page(
            request=request,
            template="pages/vlcc_collection/list.html",
            model={
                "items": result,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
                "date_from": start.strftime("%Y-%m-%d") if start else "",
                "date_to": end.strftime("%Y-%m-%d") if end else "",
                "total_items": total_items,
            },
        )

    @staticmethod
    def _parse_day(value: str) -> datetime | None:
        """yyyy-mm-dd (native date input) -> start of that day; None when empty / invalid."""
        try:
            return datetime.strptime((value or "").strip(), "%Y-%m-%d")
        except ValueError:
            return None

    # =========================================================
    # CREATE PAGE
    # =========================================================

    @staticmethod
    def _deny_farmer(request: Request) -> None:
        user = getattr(request.state, "user", None)
        if user and (user.role_type == Role.FARMER or getattr(user, "is_farmer_vlcc", False)):
            raise ForbiddenException("Action not permitted for this account")

    @staticmethod
    async def _form_model(request: Request, vlcc_id: UUID | None) -> dict:
        """
        Everything the collection form needs for one VLCC:
        - a logged-in VLCC gets its own VLCC pre-selected and locked,
        - settings (weight / analyzer modes, cattle type),
        - its rate charts in rank order (index 0 = R1),
        - its farmers,
        - buffalo minimum FAT (milk type is derived from FAT for Cow / Buffalo VLCCs).
        """
        user = request.state.user
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=user))

        lock_vlcc = user.role_type == Role.VLCC
        if lock_vlcc and vlccs:
            vlcc_id = vlccs[0].id  # a VLCC only ever sees its own VLCC

        model = {
            "vlccs": vlccs,
            "selected_vlcc_id": vlcc_id,
            "lock_vlcc": lock_vlcc,
            "setting": None,
            "rate_charts": [],
            "farmers": [],
            "buffalo_min_fat": None,
        }
        if vlcc_id is None:
            return model
        try:
            vlcc = await vlcc_handler.get(GetVlccQuery(id=vlcc_id, owner=user))
        except Exception:
            return model

        model["farmers"] = await GetHandler.farmer_handler(request).list(
            ListFarmerQuery(vlcc_id=vlcc_id, limit=200, owner=user)
        )
        if vlcc.settings_id:
            model["setting"] = await GetHandler.settings_handler(request).get_by_id(settings_id=vlcc.settings_id)
        try:
            model["rate_charts"] = await GetHandler.ratechart_handler(request).get_charts_by_owner_id(
                query=GetAssignmentsByOwnerQuery(owner_id=vlcc.user_id)
            )
        except Exception:
            pass
        if vlcc.milk_quality_config_id:
            try:
                quality = await GetHandler.milk_quality_config_handler(request).get(
                    GetMilkQualityConfigQuery(id=vlcc.milk_quality_config_id)
                )
                model["buffalo_min_fat"] = quality.buffalo_min_fat
            except Exception:
                pass
        return model

    @staticmethod
    async def get_create_page(request: Request):
        VlccCollectionController._deny_farmer(request)
        model = await VlccCollectionController._form_model(request, None)
        model["default_date"] = now_naive_ist().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/vlcc_collection/create_edit.html",
            model=model,
        )

    # =========================================================
    # EDIT PAGE
    # =========================================================

    @staticmethod
    async def get_edit_page(
        request: Request,
        collection_id: UUID,
    ):
        VlccCollectionController._deny_farmer(request)
        handler = GetHandler.vlcc_collection_handler(request)
        owner = request.state.user

        collection = await handler.get(GetVlccCollectionQuery(id=collection_id), owner=owner)
        model = await VlccCollectionController._form_model(request, collection.vlcc_id)

        default_date = collection.collected_at.strftime("%Y-%m-%dT%H:%M") if collection and collection.collected_at else now_naive_ist().strftime("%Y-%m-%dT%H:%M")

        model.update({
            "collection": collection,
            "default_date": default_date,
            "collection_number": collection.collection_number,
            "selected_vlcc_id": collection.vlcc_id,
        })
        return Renderer.page(
            request=request,
            template="pages/vlcc_collection/create_edit.html",
            model=model,
        )

    # =========================================================
    # VIEW PAGE
    # =========================================================

    @staticmethod
    async def view_page(
        request: Request,
        collection_id: UUID,
    ):
        handler = GetHandler.vlcc_collection_handler(request)
        user = request.state.user
        collection = await handler.get(GetVlccCollectionQuery(id=collection_id), owner=user)

        vlcc_handler = GetHandler.vlcc_handler(request)
        farmer_handler = GetHandler.farmer_handler(request)

        vlcc = None
        farmer = None
        try:
            vlcc_detail = await vlcc_handler.get_full_detail(GetVlccQuery(id=collection.vlcc_id, owner=user))
            vlcc = vlcc_detail.vlcc
            if vlcc_detail.address and vlcc_detail.address.city:
                vlcc.city = vlcc_detail.address.city
            if vlcc_detail.user and vlcc_detail.user.mobile:
                vlcc.mobile = vlcc_detail.user.mobile
        except Exception:
            try:
                vlcc = await vlcc_handler.get(GetVlccQuery(id=collection.vlcc_id, owner=user))
            except Exception:
                pass

        try:
            farmer = await farmer_handler.get(GetFarmerQuery(id=collection.farmer_id, owner=user))
        except Exception:
            pass

        return Renderer.page(
            request=request,
            template="pages/vlcc_collection/view.html",
            model={
                "collection": collection,
                "vlcc": vlcc,
                "farmer": farmer,
            },
        )

    # =========================================================
    # POST CREATE
    # =========================================================

    @staticmethod
    async def post_create_page(request: Request):
        VlccCollectionController._deny_farmer(request)
        form_data = dict(await request.form())

        data = CreateVlccCollectionRequest.model_validate(form_data)
        command = VlccCollectionAssembler.create(data=data)
        handler = GetHandler.vlcc_collection_handler(request)
        user = request.state.user

        result = await handler.create(command)
        if result:
            farmer_name = "Farmer"
            if result.farmer_id:
                try:
                    f_ent = await GetHandler.farmer_handler(request).get(GetFarmerQuery(id=result.farmer_id, owner=user))
                    farmer_name = f_ent.name
                except Exception:
                    pass

            # A fresh, empty form for the next entry (the summary box resets with it)
            model = await VlccCollectionController._form_model(request, data.vlcc_id)
            model["default_date"] = data.collection_date.strftime("%Y-%m-%dT%H:%M") if data.collection_date else now_naive_ist().strftime("%Y-%m-%dT%H:%M")
            model["new_item"] = {
                "farmer_name": farmer_name,
                "date": result.collected_at.strftime("%d/%m %H:%M"),
                "qty": result.quantity,
                "fat": result.fat_percent or 0.0,
                "total": result.total_amount,
            }

            return Renderer.partial(
                request=request,
                template="pages/vlcc_collection/collection_form.html",
                model=model,
            ).success("Collection add successfully").build()

        return Renderer.empty().error(
            "Unable to record collection details."
        ).build()

    # =========================================================
    # POST UPDATE
    # =========================================================

    @staticmethod
    async def post_update_page(
        request: Request,
        collection_id: UUID,
    ):
        VlccCollectionController._deny_farmer(request)
        form_data = dict(await request.form())
        user = request.state.user

        handler = GetHandler.vlcc_collection_handler(request)
        existing = await handler.get(GetVlccCollectionQuery(id=collection_id), owner=user)
        form_data["collection_number"] = existing.collection_number

        if "quantity_collection_mode" not in form_data:
            form_data["quantity_collection_mode"] = "MANUAL"
        if "measurement_mode" not in form_data:
            form_data["measurement_mode"] = "MANUAL"
        if "payment_mode" not in form_data or not form_data["payment_mode"]:
            form_data["payment_mode"] = 1

        nullable_fields = ["fat_percent", "snf_percent", "rank"]
        for field in nullable_fields:
            if field in form_data and (form_data[field] == "" or form_data[field] == "None"):
                form_data[field] = None

        data = UpdateVlccCollectionRequest.model_validate(form_data)
        command = VlccCollectionAssembler.update(id=collection_id, data=data)

        result = await handler.update(command, owner=user)
        if result:
            return Renderer.htmx_redirect(f"/vlcc-collections/view/{collection_id}")

        return Renderer.empty().error(
            "Unable to update collection details."
        ).build()

    # =========================================================
    # POST DELETE
    # =========================================================

    @staticmethod
    async def delete_post(
        request: Request,
        collection_id: UUID,
    ):
        VlccCollectionController._deny_farmer(request)
        user = request.state.user
        handler = GetHandler.vlcc_collection_handler(request)
        await handler.delete(DeleteVlccCollectionCommand(id=collection_id), owner=user)
        return HTMLResponse("success")

    @staticmethod
    async def delete_bulk_post(request: Request):
        """Delete the selected rows; ids outside the user's scope are skipped by the repository."""
        VlccCollectionController._deny_farmer(request)
        body = await request.json()
        try:
            ids = [UUID(str(i)) for i in body.get("ids", [])]
        except ValueError:
            return JSONResponse({"detail": "Invalid collection id"}, status_code=400)

        handler = GetHandler.vlcc_collection_handler(request)
        deleted = await handler.delete_bulk(ids, owner=request.state.user)
        return JSONResponse({"deleted": len(deleted)})

    # =========================================================
    # AJAX DYNAMIC LOADING
    # =========================================================

    @staticmethod
    async def load_form(
        request: Request,
        vlcc_id: UUID | None = None,
        collected_at: datetime | None = None,
    ):
        model = await VlccCollectionController._form_model(request, vlcc_id)
        model["default_date"] = collected_at.strftime("%Y-%m-%dT%H:%M") if collected_at else now_naive_ist().strftime("%Y-%m-%dT%H:%M")
        return Renderer.partial(
            request=request,
            template="pages/vlcc_collection/collection_form.html",
            model=model,
        ).build()

    @staticmethod
    async def calculate_rate(
        request: Request,
        fat_percent: float = 0.0,
        snf_percent: float = 0.0,
    ):
        rate = fat_percent * 6.5 + snf_percent * 2.0
        if rate <= 0:
            rate = 45.0
        return HTMLResponse(
            f'<input type="number" step="0.01" name="rate_per_unit" id="cf-rate" class="form-control" value="{rate:.2f}" required oninput="calcTotal()">'
        )

    @staticmethod
    async def search_farmers(
        request: Request,
        vlcc_id: UUID | None = None,
        q: str = "",
    ):
        farmer_handler = GetHandler.farmer_handler(request)
        farmers = []
        if vlcc_id:
            farmers = await farmer_handler.list(
                ListFarmerQuery(
                    vlcc_id=vlcc_id,
                    keyword=q.strip(),
                    limit=20,
                    owner=request.state.user
                )
            )

        html_options = ""
        for f in farmers:
            f_name = f.name or f.farmer_code
            f_rank = f.assigned_chart_rank or 1
            f_mobile = f.mobile or ""
            click_handler = f"selectFarmer('{f.id}', '{f_name}', '{f.farmer_code}', '{f_rank}', '{f_mobile}')"
            html_options += f"""
            <div class="search-result-item" style="padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f1f5f9; background: white; transition: all 0.2s; display: flex; align-items: center; justify-content: space-between;" 
                 onclick="{click_handler}"
                 onmouseover="this.style.background='#f8fafc'" 
                 onmouseout="this.style.background='white'">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid fa-user-tag" style="color: #64748b; font-size: 12px;"></i>
                    <span style="font-weight: 600; color: #1e293b; font-size: 13px;">{f.name or ''}</span>
                </div>
                <span style="background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">{f.farmer_code}</span>
            </div>
            """

        if not html_options:
            html_options = '<div style="padding: 14px 16px; color: #94a3b8; background: white; font-size: 13px; font-weight: 500; text-align: center;">No farmers found</div>'

        html = f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05); background: white; margin-top: 4px; max-height: 250px; overflow-y: auto;">
            {html_options}
        </div>
        """
        return HTMLResponse(html)
