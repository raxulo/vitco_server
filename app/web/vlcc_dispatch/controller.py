from datetime import datetime
from uuid import UUID
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.modules.dependencies import GetHandler
from app.modules.collections.vlcc_collection.application.dispatch_command import (
    CreateDispatchCommand,
    UpdateDispatchCommand,
    DeleteDispatchCommand,
    GetDispatchQuery,
    ListDispatchesQuery,
)
from app.modules.vlcc.application.command import ListVlccQuery
from app.web.framework.renderer import Renderer
from app.core.clock import now_naive_ist
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
    MeasurementMode,
)


class DispatchController:
    __slots__ = ()

    @staticmethod
    async def list_page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        vlcc_id: str | None = None,
        shift: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        tab: str = "dispatches",
    ):
        tab_param = request.query_params.get("tab", tab)
        active_tab = "comparison" if tab_param == "comparison" else "dispatches"

        handler = GetHandler.dispatch_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=request.state.user))

        today_str = now_naive_ist().strftime("%Y-%m-%d")
        if start_date is None or start_date.strip() == "":
            start_date = today_str
        if end_date is None or end_date.strip() == "":
            end_date = today_str

        v_id = UUID(vlcc_id) if vlcc_id else None
        s_date = None
        e_date = None
        if start_date:
            try:
                s_date = datetime.strptime(start_date, "%Y-%m-%d")
            except Exception:
                pass
        if end_date:
            try:
                # Include the entire day by setting to 23:59:59
                e_date = datetime.strptime(end_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass


        shift_enum = None
        if shift is not None and str(shift).strip() != "":
            try:
                shift_enum = CollectionShift(int(shift))
            except (ValueError, TypeError):
                if str(shift).upper() in CollectionShift.__members__:
                    shift_enum = CollectionShift[str(shift).upper()]

        dispatches = []
        paginated_comparison_items = []
        comparison_summary = None
        total_comparison_items = 0
        total_pages = 1

        if active_tab == "comparison":
            comparison_items, comparison_summary = await handler.get_comparison(
                owner=request.state.user,
                vlcc_id=v_id,
                shift=shift_enum,
                start_date=s_date,
                end_date=e_date,
            )
            total_comparison_items = len(comparison_items)
            c_limit = 20
            total_pages = max(1, (total_comparison_items + c_limit - 1) // c_limit) if total_comparison_items > 0 else 1
            paginated_comparison_items = comparison_items[(page - 1) * c_limit : page * c_limit]
            effective_limit = c_limit
        else:
            dispatches = await handler.list(
                ListDispatchesQuery(
                    vlcc_id=v_id,
                    shift=shift_enum,
                    start_date=s_date,
                    end_date=e_date,
                    page=page,
                    size=limit,
                    owner=request.state.user,
                )
            )
            if len(dispatches) >= limit:
                total_pages = page + 1
            effective_limit = limit

        return Renderer.page(
            request=request,
            template="pages/vlcc_dispatch/list.html",
            model={
                "active_tab": active_tab,
                "items": dispatches,
                "comparison_items": paginated_comparison_items,
                "comparison_summary": comparison_summary,
                "total_comparison_count": total_comparison_items,
                "vlccs": vlccs,
                "selected_vlcc_id": vlcc_id,
                "selected_shift": shift,
                "shifts": CollectionShift,
                "today": today_str,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "limit": effective_limit,
                "total_pages": total_pages,
            },
        )


    @staticmethod
    async def get_create_page(request: Request):
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=request.state.user))
        now = now_naive_ist()
        default_shift = CollectionShift.MORNING if now.hour < 15 else CollectionShift.EVENING
        return Renderer.page(
            request=request,
            template="pages/vlcc_dispatch/create_edit.html",
            model={
                "vlccs": vlccs,
                "dispatch": None,
                "shifts": CollectionShift,
                "default_shift": default_shift,
                "today": now.strftime("%Y-%m-%dT%H:%M"),
            },
        )

    @staticmethod
    async def post_create(request: Request):
        form = await request.form()
        handler = GetHandler.dispatch_handler(request)
        
        vlcc_id = UUID(form["vlcc_id"])
        collected_at = datetime.fromisoformat(form["collected_at"])
        fat = float(form["fat_percent"])
        snf = float(form["snf_percent"])
        qty = float(form["quantity"])
        cans = int(form["can_count"])

        shift_val = form.get("shift")
        shift = CollectionShift.MORNING
        if shift_val is not None and str(shift_val).strip() != "":
            try:
                shift = CollectionShift(int(shift_val))
            except (ValueError, TypeError):
                if str(shift_val).upper() in CollectionShift.__members__:
                    shift = CollectionShift[str(shift_val).upper()]

        await handler.create(
            CreateDispatchCommand(
                vlcc_id=vlcc_id,
                collected_at=collected_at,
                shift=shift,
                fat_percent=fat,
                snf_percent=snf,
                quantity=qty,
                can_count=cans,
                quantity_collection_mode=QuantityCollectionMode.MANUAL,
                measurement_mode=MeasurementMode.MANUAL,
                owner=request.state.user,
            )
        )
        return RedirectResponse("/vlcc-dispatches", status_code=303)

    @staticmethod
    async def get_edit_page(request: Request, id: str):
        handler = GetHandler.dispatch_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)
        
        dispatch = await handler.get(GetDispatchQuery(id=UUID(id), owner=request.state.user))
        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=request.state.user))

        return Renderer.page(
            request=request,
            template="pages/vlcc_dispatch/create_edit.html",
            model={
                "vlccs": vlccs,
                "dispatch": dispatch,
                "shifts": CollectionShift,
                "default_shift": getattr(dispatch, "shift", CollectionShift.MORNING),
                "today": dispatch.collected_at.strftime("%Y-%m-%dT%H:%M"),
            },
        )

    @staticmethod
    async def post_update(request: Request, id: str):
        form = await request.form()
        handler = GetHandler.dispatch_handler(request)
        
        vlcc_id = UUID(form["vlcc_id"])
        collected_at = datetime.fromisoformat(form["collected_at"])
        fat = float(form["fat_percent"])
        snf = float(form["snf_percent"])
        qty = float(form["quantity"])
        cans = int(form["can_count"])

        shift_val = form.get("shift")
        shift = CollectionShift.MORNING
        if shift_val is not None and str(shift_val).strip() != "":
            try:
                shift = CollectionShift(int(shift_val))
            except (ValueError, TypeError):
                if str(shift_val).upper() in CollectionShift.__members__:
                    shift = CollectionShift[str(shift_val).upper()]

        await handler.update(
            UpdateDispatchCommand(
                id=UUID(id),
                vlcc_id=vlcc_id,
                collected_at=collected_at,
                shift=shift,
                fat_percent=fat,
                snf_percent=snf,
                quantity=qty,
                can_count=cans,
                quantity_collection_mode=QuantityCollectionMode.MANUAL,
                measurement_mode=MeasurementMode.MANUAL,
                owner=request.state.user,
            )
        )
        return RedirectResponse("/vlcc-dispatches", status_code=303)

    @staticmethod
    async def post_delete(request: Request, id: str):
        handler = GetHandler.dispatch_handler(request)
        await handler.delete(DeleteDispatchCommand(id=UUID(id), owner=request.state.user))
        return RedirectResponse("/vlcc-dispatches", status_code=303)
