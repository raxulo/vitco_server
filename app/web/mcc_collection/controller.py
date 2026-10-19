"""
MCC Collection Web Controller
"""

from app.modules.collections.mcc_collection.application.command import GetCollectionBySampleNumberQuery
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.ratechart.application.command import ListRateChartsQuery
from app.modules.ratechart.domain.dto import RateChartListDto
from app.modules.ratechart.application.command import GetAssignmentsByOwnerQuery
from app.modules.collections.mcc_collection.domain.dto import MccCollectionResult
from app.modules.collections.mcc_collection.domain.dto import MccSampleResult
from app.modules.mcc.domain.enums import MccType
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.application.command import GetNextSampleNumberQuery
from datetime import datetime
from app.modules.mcc.application.command import GetMccQuery
from app.core.database.manager import DatabaseManager
from app.modules.vlcc.application.command import GetVlccQuery
from uuid import UUID
from fastapi import Request
from fastapi.responses import HTMLResponse

from app.modules.dependencies import GetHandler
from app.modules.collections.mcc_collection.application.command import (
    GetMccCollectionQuery,
    ListMccCollectionsQuery,
    DeleteMccCollectionCommand,
)
from app.modules.mcc.application.command import ListMccQuery
from app.modules.vlcc.application.command import ListVlccQuery
from app.web.framework.renderer import Renderer
from app.web.mcc_collection.assembler import MccCollectionAssembler
from app.modules.collections.mcc_collection.presentation.requests import (
    CreateMccCollectionRequest,
    UpdateMccCollectionRequest,
)


class MccCollectionController:

    __slots__ = ()

    # =========================================================
    # LIST
    # =========================================================

    @staticmethod
    async def page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
    ):
        handler = GetHandler.mcc_collection_handler(request)
        user = request.state.user

        if search.strip():
            total_items = await handler.count_search(keyword=search.strip(), owner=user)
        else:
            total_items = await handler.count(owner=user)

        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        result = await handler.list(
            ListMccCollectionsQuery(
                page=page,
                size=limit,
                keyword=search.strip(),
            ),
            owner=user
        )

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/list.html",
            model={
                "items": result,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
                "total_items": total_items,
            },
        )

    # =========================================================
    # CREATE PAGE
    # =========================================================

    @staticmethod
    async def get_create_page(request: Request):
        mcc_handler = GetHandler.mcc_handler(request)

        mccs = await mcc_handler.list(ListMccQuery(size=200, owner=request.state.user))
        default_date = datetime.now().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/create_edit.html",
            model={
                "mccs": mccs,
                "vlccs": [],
                "default_date": default_date,
            },
        )

    # =========================================================
    # EDIT PAGE
    # =========================================================

    @staticmethod
    async def get_edit_page(
        request: Request,
        collection_id: UUID,
    ):
        handler = GetHandler.mcc_collection_handler(request)
        mcc_handler = GetHandler.mcc_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)
        user = request.state.user

        collection = await handler.get(GetMccCollectionQuery(id=collection_id), owner=user)
        mccs = await mcc_handler.list(ListMccQuery(size=200))
        vlccs = await vlcc_handler.get_vlccs_by_mcc(mcc_id=collection.mcc_id)
        
        mcc = await mcc_handler.get(GetMccQuery(id=collection.mcc_id, owner=user))
        setting = await GetHandler.settings_handler(request).get_by_id(settings_id=mcc.settings_id)
        default_date = collection.collected_at.strftime("%Y-%m-%dT%H:%M") if collection and collection.collected_at else datetime.now().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/create_edit.html",
            model={
                "collection": collection,
                "mccs": mccs,
                "vlccs": vlccs,
                "setting": setting,
                "default_date": default_date,
            },
        )

    # =========================================================
    # VIEW PAGE
    # =========================================================

    @staticmethod
    async def view_page(
        request: Request,
        collection_id: UUID,
    ):
        handler = GetHandler.mcc_collection_handler(request)
        user = request.state.user
        collection = await handler.get(GetMccCollectionQuery(id=collection_id), owner=user)

        mcc_handler = GetHandler.mcc_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)
        
        mcc = None
        vlcc = None
        
        try:
            mcc_detail = await mcc_handler.get_full_detail(GetMccQuery(id=collection.mcc_id, owner=user))
            mcc = mcc_detail.mcc
            if mcc_detail.address and mcc_detail.address.city:
                mcc.city = mcc_detail.address.city
        except Exception:
            try:
                mcc = await mcc_handler.get(GetMccQuery(id=collection.mcc_id, owner=user))
            except Exception:
                pass

        try:
            vlcc_detail = await vlcc_handler.get_full_detail(GetVlccQuery(id=collection.vlcc_id, owner=user))
            vlcc = vlcc_detail.vlcc
            if vlcc_detail.user and vlcc_detail.user.mobile:
                vlcc.mobile = vlcc_detail.user.mobile
            if vlcc_detail.address and vlcc_detail.address.city and not vlcc.city:
                vlcc.city = vlcc_detail.address.city
        except Exception:
            try:
                vlcc = await vlcc_handler.get(GetVlccQuery(id=collection.vlcc_id, owner=user))
            except Exception:
                pass

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/view.html",
            model={
                "collection": collection,
                "mcc": mcc,
                "vlcc": vlcc,
            },
        )

    # =========================================================
    # POST CREATE
    # =========================================================

    @staticmethod
    async def post_create_page(request: Request):
        form_data = dict(await request.form())
        
        # Populate defaults for missing/empty parameters
        if "sample_number" not in form_data or not form_data["sample_number"]:
            form_data["sample_number"] = 0
        if "can_count" not in form_data or not form_data["can_count"]:
            form_data["can_count"] = 0
        if "mcc_type" not in form_data or not form_data["mcc_type"]:
            form_data["mcc_type"] = 0 # NORMAL
            
        nullable_fields = ["fat_percent", "snf_percent", "clr_value", "rate_chart_id"]
        for field in nullable_fields:
            if field in form_data and (form_data[field] == "" or form_data[field] == "None"):
                form_data[field] = None

        if "rate_per_unit" in form_data and form_data["rate_per_unit"] == "":
            form_data["rate_per_unit"] = 0.0
        if "total_amount" in form_data and form_data["total_amount"] == "":
            form_data["total_amount"] = 0.0

        data = CreateMccCollectionRequest.model_validate(form_data)

        command = MccCollectionAssembler.create(data=data)
        handler = GetHandler.mcc_collection_handler(request)
        
        result = await handler.create(command)

        if result:
            
            next_sample_number = None
            mcc_handler = GetHandler.mcc_handler(request)
            vlcc_handler = GetHandler.vlcc_handler(request)

            mccs = await mcc_handler.list(ListMccQuery(size=200))
            mcc = await mcc_handler.get(GetMccQuery(id=data.mcc_id, owner=request.state.user))
            settings = await GetHandler.settings_handler(request).get_by_id(settings_id=mcc.settings_id)
            if mcc.mcc_type == MccType.WEIGHT:
                sample_result: MccSampleResult = await GetHandler.mcc_collection_handler(request).genext_sample_number(
                    query=GetNextSampleNumberQuery(mcc_id=mcc.id,
                    collected_at=data.collection_date,
                    shift=data.shift)
                )
                next_sample_number = sample_result.next_sample_number
            assigned_rate_charts = []
            if mcc.mcc_type != MccType.WEIGHT:
                assigned_rate_charts = await GetHandler.ratechart_handler(request).get_charts_by_owner_id(query= GetAssignmentsByOwnerQuery(owner_id=mcc.user_id))
            vlccs = []
            if data.mcc_id and mcc.mcc_type == MccType.WEIGHT:
                try:
                    vlccs = await vlcc_handler.get_vlccs_by_mcc(mcc_id=data.mcc_id)
                except Exception:
                    pass

            default_date = data.collection_date.strftime("%Y-%m-%dT%H:%M") if data.collection_date else datetime.now().strftime("%Y-%m-%dT%H:%M")

            vlcc_name = "VLCC"
            if result.vlcc_id:
                try:
                    vlcc = await GetHandler.vlcc_handler(request).get(GetVlccQuery(id=result.vlcc_id, owner=request.state.user))
                    vlcc_name = vlcc.name
                except Exception:
                    pass

            formatted_date = result.collected_at.strftime("%d/%m %H:%M")

            return Renderer.partial(
                request=request,
                template="pages/mcc_collection/collection_form.html",
                model={
                    "mcc": mcc,
                    "mccs": mccs,
                    "vlccs": vlccs,
                    "mcc_id": data.mcc_id,
                    "setting": settings or {},
                    "default_date": default_date,
                    "next_sample_number" : next_sample_number,
                    "rate_charts": assigned_rate_charts,
                    "new_item": {
                        "vlcc_name": vlcc_name,
                        "date": formatted_date,
                        "qty": result.quantity,
                        "fat": result.fat_percent or 0.0,
                        "total": MccCollectionAssembler.get_total_amount(data)
                    }
                },
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
        form_data = dict(await request.form())
        user = request.state.user
        handler = GetHandler.mcc_collection_handler(request)

        existing = await handler.get(GetMccCollectionQuery(id=collection_id), owner=user)
        form_data["collection_number"] = existing.collection_number

        if "sample_number" not in form_data or not form_data["sample_number"]:
            form_data["sample_number"] = 0
        if "can_count" not in form_data or not form_data["can_count"]:
            form_data["can_count"] = 0

        data = UpdateMccCollectionRequest.model_validate(form_data)

        command = MccCollectionAssembler.update(
            collection_id=collection_id,
            data=data,
        )
        
        result = await handler.update(command, owner=user)

        if result:
            return Renderer.htmx_redirect(
                f"/mcc-collections/view/{collection_id}"
            )

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
        user = request.state.user
        handler = GetHandler.mcc_collection_handler(request)
        await handler.delete(DeleteMccCollectionCommand(id=collection_id), owner=user)
        return HTMLResponse("success")

    # =========================================================
    # CODE VALIDATION
    # =========================================================

    @staticmethod
    async def validate_number(request: Request, collection_number: str):
        return HTMLResponse(
            '<h6 style="color:green">Collection number available</h6>'
        )

    # =========================================================
    # API ENDPOINTS FOR CREATE_EDIT PAGE
    # =========================================================

    @staticmethod
    async def get_next_sample(
        request: Request,
        mcc_id: UUID,
        collected_at: datetime,
        shift: CollectionShift,
    ):
        sample = await GetHandler.mcc_collection_handler(request).get_next_sample_number(
            query=GetNextSampleNumberQuery(
                mcc_id=mcc_id,
                collected_at=collected_at,
                shift=shift,
            )
        )
        return {"next_sample": sample, "sample_start": 1, "sample_end": 1000}

    @staticmethod
    async def search_sample(
        request: Request,
        mcc_id: UUID,
        date: str,
        shift: int,
        sample_number: int,
    ):
        collected_at = datetime.strptime(date, "%Y-%m-%d")
        is_taken = await GetHandler.mcc_collection_handler(request).is_sample_number_collected(
            query=GetCollectionBySampleNumberQuery(
                mcc_id=mcc_id,
                sample_number=sample_number,
                shift=CollectionShift.MORNING if shift == 0 else CollectionShift.EVENING,
                collected_at=collected_at,
            )
        )
        return {"found": is_taken, "is_duplicate": is_taken, "already_taken": is_taken}

    @staticmethod
    async def get_mcc_ratecharts(request: Request, mcc_id: UUID):
        return []

    @staticmethod
    async def calculate_rate(
        request: Request,
        rate_chart_id: str | None = None,
        fat_percent: float = 0.0,
        snf_percent: float = 0.0,
        milk_type: int = 0,
    ):
        rate = fat_percent * 6.5 + snf_percent * 2.0
        if rate <= 0:
            rate = 45.0
        return HTMLResponse(
            f'<input type="number" step="0.01" name="rate_per_unit" id="cf-rate" class="form-control" value="{rate:.2f}" required oninput="calcTotal()">'
        )

    @staticmethod
    async def load_form(
        request: Request,
        mcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        collected_at: datetime | None = None,
    ):
        next_sample_number = None
        mcc_handler = GetHandler.mcc_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)

        mccs = await mcc_handler.list(ListMccQuery(size=200, owner=request.state.user))
        mcc = await mcc_handler.get(GetMccQuery(id=mcc_id, owner=request.state.user))
        settings = await GetHandler.settings_handler(request).get_by_id(settings_id=mcc.settings_id)
        if mcc.mcc_type == MccType.WEIGHT:
            sample_result: MccSampleResult = await GetHandler.mcc_collection_handler(request).genext_sample_number(
                query=GetNextSampleNumberQuery(mcc_id=mcc.id,
                collected_at=collected_at or datetime.now(),
                shift=shift or CollectionShift.MORNING)
            )
            next_sample_number = sample_result.next_sample_number
        assigned_rate_charts = []
        if mcc.mcc_type != MccType.WEIGHT:
            user = request.state.user
            assigned_rate_charts = await GetHandler.ratechart_handler(request).list(
                    ListRateChartsQuery(owner=CurrentUser(id=user.id, role=user.role))
                )
        vlccs = []
        if mcc_id and mcc.mcc_type == MccType.WEIGHT:
            try:
                vlccs = await vlcc_handler.get_vlccs_by_mcc(mcc_id=mcc_id)
            except Exception:
                pass

        default_date = collected_at.strftime("%Y-%m-%dT%H:%M") if collected_at else datetime.now().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/collection_form.html",
            model={
                "mcc": mcc,
                "mccs": mccs,
                "vlccs": vlccs,
                "mcc_id": mcc_id,
                "setting": settings or {},
                "default_date": default_date,
                "next_sample_number" : next_sample_number,
                "rate_charts": assigned_rate_charts
            },
        )

    @staticmethod
    async def get_sample_result(
        request: Request,
        mcc_id: UUID,
        sample_number: int,
        shift: CollectionShift,
        collection_date: str | None = None,
    ):
        from app.modules.collections.mcc_collection.application.command import GetCollectionBySampleNumberQuery
        handler = GetHandler.mcc_collection_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)

        # Parse datetime from collection_date
        dt = None
        if collection_date:
            try:
                dt = datetime.strptime(collection_date.split(".")[0], "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    dt = datetime.strptime(collection_date.split(".")[0], "%Y-%m-%d")
                except ValueError:
                    dt = datetime.now()
        else:
            dt = datetime.now()

        result: MccCollectionResult | None = await handler.collection_by_sample_result(
            query=GetCollectionBySampleNumberQuery(
                mcc_id=mcc_id,
                sample_number=sample_number,
                shift=shift,
                collected_at=dt or datetime.now(),
            )
        )

        vlccs = await vlcc_handler.get_vlccs_by_mcc(mcc_id=mcc_id)

        assigned_chart_rank = 1
        matched_vlcc_code = ""
        matched_vlcc_route = ""
        matched_vlcc_mobile = ""
        if result and result.vlcc_id:
            for v in vlccs:
                if str(v.vlcc_id) == str(result.vlcc_id):
                    assigned_chart_rank = v.assigned_chart_rank
                    matched_vlcc_code = getattr(v, "vlcc_code", "") or getattr(v, "uic_code", "") or ""
                    matched_vlcc_route = getattr(v, "route_code", "") or ""
                    matched_vlcc_mobile = getattr(v, "mobile", "") or ""
                    break

        import json
        if result:
            trigger_data = {
                "populate-fields": {
                    "quantity": str(result.quantity) if result.quantity else "0.0",
                    "can_count": result.can_count or 0,
                    "vlcc_id": str(result.vlcc_id) if result.vlcc_id else "",
                    "vlcc_name": result.vlcc_name if result.vlcc_name else "",
                    "vlcc_code": matched_vlcc_code,
                    "route_code": matched_vlcc_route,
                    "mobile": matched_vlcc_mobile,
                    "assigned_chart_rank": assigned_chart_rank,
                }
            }
            print("TTTTTT", trigger_data)
            headers = {"HX-Trigger": json.dumps(trigger_data)}
            html = '<div id="cf-sample-error" style="display: none;" hx-swap-oob="true"></div>'
            return HTMLResponse(html, headers=headers)
        else:
            trigger_data = {
                "populate-fields": {
                    "quantity": "",
                    "can_count": "",
                    "vlcc_id": "",
                }
            }
            headers = {"HX-Trigger": json.dumps(trigger_data)}
            html = """
            <div id="cf-sample-error" style="color: #ef4444; font-size: 11px; margin-top: 4px; display: block; font-weight: 600;" hx-swap-oob="true">
                <i class="fa-solid fa-circle-exclamation"></i> sample not exists
            </div>
            """
            return HTMLResponse(html, headers=headers)
