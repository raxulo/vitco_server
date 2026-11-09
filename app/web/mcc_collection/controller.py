"""
MCC Collection Web Controller
"""

from app.modules.collections.mcc_collection.application.command import GetCollectionBySampleNumberQuery
from app.core.exceptions.base import ForbiddenException
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.ratechart.application.command import ListRateChartsQuery
from app.modules.ratechart.domain.dto import RateChartListDto
from app.modules.ratechart.domain.enums import RateChartStatus
from app.modules.ratechart.application.command import GetAssignmentsByOwnerQuery
from app.modules.common.milk_quality.application.command import GetMilkQualityConfigQuery
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
from fastapi.responses import HTMLResponse, JSONResponse

from app.modules.dependencies import GetHandler
from app.modules.collections.mcc_collection.application.command import (
    GetMccCollectionQuery,
    ListMccCollectionsQuery,
    DeleteMccCollectionCommand,
)
from app.modules.mcc.application.command import ListMccQuery
from app.modules.vlcc.application.command import ListVlccQuery
from app.modules.collections.mcc_collection.domain.listing import MccCollectionFilters
from app.web.framework.collection_list import (
    clean_limit,
    clean_search,
    filter_query,
    page_window,
    parse_milk_type,
    parse_period,
    parse_uuid,
    period_model,
)
from app.web.framework.renderer import Renderer
from app.web.mcc_collection.assembler import MccCollectionAssembler
from app.core.clock import now_naive_ist
from app.modules.collections.mcc_collection.presentation.requests import (
    CreateMccCollectionRequest,
    UpdateMccCollectionRequest,
)


class MccCollectionController:

    __slots__ = ()

    @staticmethod
    def _deny_vlcc(request: Request) -> None:
        user = getattr(request.state, "user", None)
        if user and (user.role_type in (Role.VLCC, Role.VLCC_FARMER) or getattr(user, "is_farmer_vlcc", False)):
            raise ForbiddenException("Action not permitted for VLCC accounts")

    # =========================================================
    # LIST
    # =========================================================

    @staticmethod
    async def page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
        mcc_id: str = "",
        vlcc_id: str = "",
        milk_type: str = "",
        date_from: str = "",
        date_to: str = "",
        start_shift: str = "",
        end_shift: str = "",
    ):
        handler = GetHandler.mcc_collection_handler(request)
        user = request.state.user

        page, limit = max(page, 1), clean_limit(limit)
        search = clean_search(search)
        selected_mcc = parse_uuid(mcc_id)
        selected_vlcc = parse_uuid(vlcc_id)
        selected_milk = parse_milk_type(milk_type)
        period = parse_period(date_from, date_to, start_shift, end_shift)
        filters = MccCollectionFilters(
            vlcc_search=search or None, mcc_id=selected_mcc, vlcc_id=selected_vlcc, milk_type=selected_milk, period=period,
        )

        total_items = await handler.count(owner=user, filters=filters)
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
        totals = await handler.totals(owner=user, filters=filters)

        result = await handler.list(
            ListMccCollectionsQuery(page=page, size=limit, filters=filters),
            owner=user,
        )

        # A VLCC sees only its own supply, and an MCC only its own center, so they don't choose those
        is_vlcc = user.role_type in (Role.VLCC, Role.VLCC_FARMER)
        can_pick_mcc = not is_vlcc and user.role_type != Role.MCC
        mccs = await GetHandler.mcc_handler(request).list(ListMccQuery(size=1000, owner=user)) if can_pick_mcc else []
        vlccs = [] if is_vlcc else await GetHandler.vlcc_handler(request).list(ListVlccQuery(size=1000, owner=user))
        chosen = period_model(period)

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/list.html",
            model={
                "items": result,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "page_numbers": page_window(page, total_pages),
                "total_items": total_items,
                "totals": totals,
                "search": search,
                "mcc_options": list({mcc.id: mcc.name for mcc in mccs}.items()),
                "vlcc_options": list({vlcc.id: vlcc.name for vlcc in vlccs}.items()),
                "can_pick_mcc": can_pick_mcc,
                "can_pick_vlcc": not is_vlcc,
                "selected_mcc": str(selected_mcc) if selected_mcc else "",
                "selected_vlcc": str(selected_vlcc) if selected_vlcc else "",
                "selected_milk": "" if selected_milk is None else int(selected_milk),
                "has_filters": bool(
                    search or selected_mcc or selected_vlcc or selected_milk is not None
                    or any(value != "" for value in chosen.values())
                ),
                "query": filter_query(
                    limit=limit if limit != 10 else None, search=search, mcc_id=selected_mcc, vlcc_id=selected_vlcc,
                    milk_type=None if selected_milk is None else int(selected_milk), **chosen,
                ),
                **chosen,
            },
        )

    # =========================================================
    # CREATE PAGE
    # =========================================================

    @staticmethod
    async def _form_model(
        request: Request,
        mcc_id: UUID | None,
        shift: CollectionShift | None = None,
        collected_at: datetime | None = None,
    ) -> dict:
        """
        Everything the MCC collection form needs for one MCC:
        - a logged-in MCC gets its own MCC pre-selected and locked,
        - settings (weight / analyzer modes, cattle type),
        - its assigned rate charts in rank order (index 0 = R1; a VLCC's rank selects one),
        - its supplying VLCCs, the next sample number (weight MCCs),
        - buffalo minimum FAT (milk type is derived from FAT for Cow / Buffalo MCCs).
        """
        user = request.state.user
        mcc_handler = GetHandler.mcc_handler(request)
        mccs = await mcc_handler.list(ListMccQuery(size=200, owner=user))

        lock_mcc = user.role_type == Role.MCC
        if lock_mcc and mccs:
            mcc_id = mccs[0].id  # an MCC only ever sees its own MCC

        model = {
            "mccs": mccs,
            "mcc": None,
            "mcc_id": mcc_id,
            "lock_mcc": lock_mcc,
            "vlccs": [],
            "setting": {},
            "rate_charts": [],
            "next_sample_number": None,
            "buffalo_min_fat": None,
            "hide_member_names": False,
        }
        if mcc_id is None:
            return model
        try:
            mcc = await mcc_handler.get(GetMccQuery(id=mcc_id, owner=user))
        except Exception:
            return model
        model["mcc"] = mcc
        model["hide_member_names"] = not mcc.shows_member_name

        if mcc.settings_id:
            model["setting"] = await GetHandler.settings_handler(request).get_by_id(settings_id=mcc.settings_id) or {}
        if mcc.mcc_type == MccType.WEIGHT:
            sample_result: MccSampleResult = await GetHandler.mcc_collection_handler(request).genext_sample_number(
                query=GetNextSampleNumberQuery(
                    mcc_id=mcc.id,
                    collected_at=collected_at or now_naive_ist(),
                    shift=shift or CollectionShift.MORNING,
                )
            )
            model["next_sample_number"] = sample_result.next_sample_number
        else:
            ratechart_handler = GetHandler.ratechart_handler(request)
            model["rate_charts"] = await ratechart_handler.get_charts_by_owner_id(
                query=GetAssignmentsByOwnerQuery(owner_id=mcc.user_id)
            )
            if not model["rate_charts"]:
                # No chart mapped to this MCC yet: offer the active charts its user can see
                visible = await ratechart_handler.list(
                    ListRateChartsQuery(
                        size=100,
                        owner=CurrentUser(id=mcc.user_id, role=str(int(Role.MCC)), name=mcc.name, permissions=frozenset()),
                    )
                )
                model["rate_charts"] = [chart for chart in visible if chart.status == RateChartStatus.ACTIVE]
        try:
            model["vlccs"] = await GetHandler.vlcc_handler(request).get_vlccs_by_mcc(mcc_id=mcc.id, owner=user)
        except Exception:
            pass
        if mcc.milk_quality_config_id:
            try:
                quality = await GetHandler.milk_quality_config_handler(request).get(
                    GetMilkQualityConfigQuery(id=mcc.milk_quality_config_id)
                )
                model["buffalo_min_fat"] = quality.buffalo_min_fat
            except Exception:
                pass
        return model

    @staticmethod
    async def get_create_page(request: Request):
        MccCollectionController._deny_vlcc(request)
        model = await MccCollectionController._form_model(request, None)
        model["default_date"] = now_naive_ist().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/create_edit.html",
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
        MccCollectionController._deny_vlcc(request)
        handler = GetHandler.mcc_collection_handler(request)
        user = request.state.user

        collection = await handler.get(GetMccCollectionQuery(id=collection_id), owner=user)
        model = await MccCollectionController._form_model(request, collection.mcc_id)
        model["collection"] = collection
        model["default_date"] = collection.collected_at.strftime("%Y-%m-%dT%H:%M") if collection and collection.collected_at else now_naive_ist().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/create_edit.html",
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
                # A supplier VLCC made by the MCC's creator is outside an MCC user's own VLCCs
                vlcc = await MccCollectionController._supplier_vlcc(request, collection.mcc_id, collection.vlcc_id)

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
        MccCollectionController._deny_vlcc(request)
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
            vlcc_name = "VLCC"
            if result.vlcc_id:
                try:
                    vlcc = await GetHandler.vlcc_handler(request).get(GetVlccQuery(id=result.vlcc_id, owner=request.state.user))
                    vlcc_name = vlcc.name
                except Exception:
                    supplier = await MccCollectionController._supplier_vlcc(request, data.mcc_id, result.vlcc_id)
                    if supplier:
                        vlcc_name = supplier.name

            # A fresh, empty form for the next entry (the summary box resets with it)
            model = await MccCollectionController._form_model(
                request, data.mcc_id, shift=data.shift, collected_at=data.collection_date
            )
            model["default_date"] = data.collection_date.strftime("%Y-%m-%dT%H:%M") if data.collection_date else now_naive_ist().strftime("%Y-%m-%dT%H:%M")
            model["new_item"] = {
                "vlcc_name": "VLCC" if model["hide_member_names"] else vlcc_name,
                "date": result.collected_at.strftime("%d/%m %H:%M"),
                "qty": result.quantity,
                "fat": result.fat_percent or 0.0,
                "total": MccCollectionAssembler.get_total_amount(data),
            }

            return Renderer.partial(
                request=request,
                template="pages/mcc_collection/collection_form.html",
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
        MccCollectionController._deny_vlcc(request)
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
        MccCollectionController._deny_vlcc(request)
        user = request.state.user
        handler = GetHandler.mcc_collection_handler(request)
        await handler.delete(DeleteMccCollectionCommand(id=collection_id), owner=user)
        return HTMLResponse("success")

    @staticmethod
    async def delete_bulk_post(request: Request):
        MccCollectionController._deny_vlcc(request)
        """Delete the selected rows; ids outside the user's scope are skipped by the repository."""
        body = await request.json()
        try:
            ids = [UUID(str(i)) for i in body.get("ids", [])]
        except ValueError:
            return JSONResponse({"detail": "Invalid collection id"}, status_code=400)

        handler = GetHandler.mcc_collection_handler(request)
        deleted = await handler.delete_bulk(ids, owner=request.state.user)
        return JSONResponse({"deleted": len(deleted)})

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
        model = await MccCollectionController._form_model(request, mcc_id, shift=shift, collected_at=collected_at)
        model["default_date"] = collected_at.strftime("%Y-%m-%dT%H:%M") if collected_at else now_naive_ist().strftime("%Y-%m-%dT%H:%M")

        return Renderer.page(
            request=request,
            template="pages/mcc_collection/collection_form.html",
            model=model,
        )

    @staticmethod
    async def get_sample_result(
        request: Request,
        shift: CollectionShift,
        mcc_id: str | None = None,
        sample_number: str | None = None,
        collection_date: str | None = None,
    ):
        from app.modules.collections.mcc_collection.application.command import GetCollectionBySampleNumberQuery

        # A cleared / partly typed sample box (or no MCC yet) is not a lookup: just hide the error
        sample_text = (sample_number or "").strip()
        try:
            mcc_id = UUID((mcc_id or "").strip())
        except ValueError:
            mcc_id = None
        if mcc_id is None or not sample_text.isdigit():
            return HTMLResponse('<div id="cf-sample-error" style="display: none;" hx-swap-oob="true"></div>')
        sample_number = int(sample_text)

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
                    dt = now_naive_ist()
        else:
            dt = now_naive_ist()

        sample_query = GetCollectionBySampleNumberQuery(
            mcc_id=mcc_id,
            sample_number=sample_number,
            shift=shift,
            collected_at=dt or now_naive_ist(),
        )

        # Owner-wide checks: within a weight MCC's range, and not used by a sibling MCC this shift
        sample_error = await handler.sample_number_error(sample_query)
        if sample_error:
            return MccCollectionController._sample_error_response(sample_error)

        result: MccCollectionResult | None = await handler.collection_by_sample_result(query=sample_query)

        vlccs = await vlcc_handler.get_vlccs_by_mcc(mcc_id=mcc_id, owner=request.state.user)

        assigned_chart_rank = 1
        matched_vlcc_code = ""
        matched_vlcc_route = ""
        matched_vlcc_mobile = ""
        matched_vlcc_owner = ""
        if result and result.vlcc_id:
            for v in vlccs:
                if str(v.vlcc_id) == str(result.vlcc_id):
                    assigned_chart_rank = v.assigned_chart_rank
                    matched_vlcc_code = getattr(v, "vlcc_code", "") or getattr(v, "uic_code", "") or ""
                    matched_vlcc_route = getattr(v, "route_code", "") or ""
                    matched_vlcc_mobile = getattr(v, "mobile", "") or ""
                    matched_vlcc_owner = getattr(v, "owner_name", "") or ""
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
                    "owner_name": matched_vlcc_owner,
                    "assigned_chart_rank": assigned_chart_rank,
                }
            }
            headers = {"HX-Trigger": json.dumps(trigger_data)}
            html = '<div id="cf-sample-error" style="display: none;" hx-swap-oob="true"></div>'
            return HTMLResponse(html, headers=headers)
        else:
            return MccCollectionController._sample_error_response("sample not exists")

    @staticmethod
    async def _supplier_vlcc(request: Request, mcc_id: UUID | None, vlcc_id: UUID | None):
        """Name / code / mobile / route of one of the MCC's supplying VLCCs (receipt fields), or None."""
        if not mcc_id or not vlcc_id:
            return None
        from types import SimpleNamespace
        try:
            suppliers = await GetHandler.vlcc_handler(request).get_vlccs_by_mcc(mcc_id=mcc_id, owner=request.state.user)
        except Exception:
            return None
        for v in suppliers:
            if str(v.vlcc_id) == str(vlcc_id):
                return SimpleNamespace(
                    id=v.vlcc_id, name=v.vlcc_name, vlcc_code=v.vlcc_code, uic_code=v.uic_code,
                    mobile=v.mobile, contact_person=None, route_code=v.route_code, city=None,
                )
        return None

    @staticmethod
    def _sample_error_response(message: str) -> HTMLResponse:
        """Clear the auto-filled fields and show the sample error under the input."""
        import json

        trigger_data = {
            "populate-fields": {
                "quantity": "",
                "can_count": "",
                "vlcc_id": "",
            }
        }
        headers = {"HX-Trigger": json.dumps(trigger_data)}
        html = f"""
            <div id="cf-sample-error" style="color: #ef4444; font-size: 11px; margin-top: 4px; display: block; font-weight: 600;" hx-swap-oob="true">
                <i class="fa-solid fa-circle-exclamation"></i> {message}
            </div>
            """
        return HTMLResponse(html, headers=headers)
