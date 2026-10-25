"""
RateChart Web Controller
"""

from app.middleware.authentication import CurrentUser
from pydantic import validate_call_decorator
from uuid import UUID
from datetime import datetime, date
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.modules.ratechart.application.command import SaveFormulaConfigCommand
from app.modules.dependencies import GetHandler
from app.modules.ratechart.application.command import (
    GetRateChartQuery,
    ListRateChartsQuery,
    DeleteRateChartCommand,
    GetAssignmentsByOwnerQuery,
    CreateRateChartAssignmentCommand,
    UpdateRateChartCommand,
)
from app.core.exceptions.base import ForbiddenException
from app.modules.ratechart.domain.exceptions import RateChartNotFoundException, RateChartPermissionException
from app.modules.vlcc.application.command import ListVlccQuery, GetVlccQuery
from app.modules.mcc.application.command import ListMccQuery, GetMccQuery
from app.modules.administration.domain.enums import Role
from app.web.framework.renderer import Renderer
from app.web.ratechart.assembler import RateChartAssembler
from app.modules.ratechart.presentation.requests import (
    CreateRateChartRequest,
    UpdateRateChartRequest,
)
from app.modules.ratechart.domain.enums import MilkType, RateCalculationType, RateChartStatus, RateChartType
from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from sqlalchemy import select, text
from app.core.clock import today_ist


class RateChartController:

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
    ):
        handler = GetHandler.ratechart_handler(request)
        user: CurrentUser = request.state.user

        if search.strip():
            total_items = await handler.count_search(keyword=search.strip(), owner=user)
        else:
            total_items = await handler.count(owner=user)

        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        result = await handler.list(
            ListRateChartsQuery(
                page=page,
                size=limit,
                keyword=search.strip(),
                owner=user,
            )
        )

        # MCC / VLCC without the rate chart permission only view charts
        can_edit = await handler.can_edit(user)

        detailed_items = []
        for item in result:
            detailed_items.append({
                "id": item.id,
                "chart_name": item.chart_name,
                "chart_type": item.chart_type,
                "milk_type": item.milk_type,
                "effective_date": item.effective_from.strftime("%Y-%m-%d") if item.effective_from else "Immediate",
                "status": item.status,
                "is_default": False,
                "admin_name": item.owner_name or "System",
                "admin_id": "y",
                "creator_id": str(item.id),
                "can_modify": item.can_modify and can_edit,
            })

        # MCC / VLCC: charts created vs the maximum their settings allow (None = no limit)
        charts_used, charts_limit = await handler.chart_quota(user)

        return Renderer.page(
            request=request,
            template="pages/ratechart/list.html",
            model={
                "can_edit": can_edit,
                "charts_used": charts_used,
                "charts_limit": charts_limit,
                "items": detailed_items,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
                "total": total_items,
                "groups": [],
                "admins": [],
            },
        )

    # =========================================================
    # CREATE PAGE
    # =========================================================

    @staticmethod
    async def get_create_page(request: Request):
        if not await GetHandler.ratechart_handler(request).can_edit(request.state.user):
            raise ForbiddenException(RateChartPermissionException.message)
        return Renderer.page(
            request=request,
            template="pages/ratechart/create_edit.html",
            model={
                "chart": None,
                "today": today_ist().strftime("%Y-%m-%d"),
                "grids_data": [],
                "prodata_data": [],
            },
        )

    # =========================================================
    # POST CREATE
    # =========================================================

    @staticmethod
    async def post_create_page(request: Request):
        # We accept JSON request bodies for advanced grids & prodata arrays
        try:
            body = await request.json()
        except Exception:
            body = dict(await request.form())

        # Map rate_type to calculation_type
        if "rate_type" in body:
            body["calculation_type"] = int(body["rate_type"])

        # Coerce values
        if "effective_date" in body:
            body["effective_from"] = body["effective_date"]
        if "effective_from" not in body or not body["effective_from"]:
            body["effective_from"] = today_ist().strftime("%Y-%m-%d")
        if "status" in body:
            # Handle status coercion
            status_val = body["status"]
            if isinstance(status_val, str):
                body["status"] = 1 if status_val.lower() == "true" else 0
            else:
                body["status"] = 1 if status_val else 0

        data = CreateRateChartRequest.model_validate(body)
        command = RateChartAssembler.create(data=data, created_by=request.state.user.id)
        command.owner = request.state.user
        handler = GetHandler.ratechart_handler(request)

        result = await handler.create(command)
        if not result:
            return JSONResponse({"detail": "Unable to create rate chart"}, status_code=400)

        await RateChartController._save_chart_config(
            handler, result.id, int(body.get("chart_type", 0)), body, request.state.user
        )
        return JSONResponse({"status": "success", "id": str(result.id)})

    @staticmethod
    async def _save_chart_config(handler, chart_id: UUID, chart_type: int, body: dict, user: CurrentUser) -> None:
        """Formula / grid / prodata rows for a chart (grid and prodata rows are replaced)."""
        result_id = chart_id
        if chart_type == 0:
            # Formula Configuration

            formula_command = SaveFormulaConfigCommand(
                rate_chart_id=result_id,
                milk_type=2,  # Mixed default
                cow_standard_fat=float(body.get("cow_std_fat", 0.0) or 0.0),
                cow_standard_snf=float(body.get("cow_std_snf", 0.0) or 0.0),
                cow_standard_rate=float(body.get("cow_std_rate", 0.0) or 0.0),
                buffalo_standard_fat=float(body.get("buf_std_fat", 0.0) or 0.0),
                buffalo_standard_snf=float(body.get("buf_std_snf", 0.0) or 0.0),
                buffalo_standard_rate=float(body.get("buf_std_rate", 0.0) or 0.0),
                cow_fat_percentage=float(body.get("cow_fat_pct", 0.0) or 0.0),
                cow_snf_percentage=float(body.get("cow_snf_pct", 0.0) or 0.0),
                buffalo_fat_percentage=float(body.get("buf_fat_pct", 0.0) or 0.0),
                buffalo_snf_percentage=float(body.get("buf_snf_pct", 0.0) or 0.0),
            )
            await handler.save_formula_config(formula_command, user )

        elif chart_type in (1, 3):
            # CSV or Text Matrix Grid rows
            from app.modules.ratechart.application.command import SaveGridRowsCommand, GridRowInput
            raw_grids = body.get("grids", [])
            rows = []
            for idx, g in enumerate(raw_grids):
                rows.append(
                    GridRowInput(
                        row_number=idx + 1,
                        fat=float(g.get("fat", 0.0)),
                        snf=float(g.get("snf", 0.0)),
                        rate=float(g.get("rate", 0.0)),
                    )
                )
            await handler.save_grid_rows(SaveGridRowsCommand(rate_chart_id=result_id, rows=rows), user)

        elif chart_type == 2:
            # Prodata Configuration rows
            from app.modules.ratechart.application.command import SaveProdataRowsCommand, ProdataRowInput
            raw_prodata = body.get("prodata_rows", [])
            rows = []
            for idx, r in enumerate(raw_prodata):
                rows.append(
                    ProdataRowInput(
                        row_number=idx + 1,
                        fat_min=float(r.get("fat_min", 0.0)),
                        fat_max=float(r.get("fat_max", 0.0)),
                        snf_min=float(r.get("snf_min", 0.0)) if r.get("snf_min") is not None else None,
                        snf_max=float(r.get("snf_max", 0.0)) if r.get("snf_max") is not None else None,
                        fat_rate_per_kg=float(r.get("kg_fat_rate", 0.0)) if r.get("kg_fat_rate") is not None else None,
                        snf_rate_per_kg=float(r.get("kg_snf_rate", 0.0)) if r.get("kg_snf_rate") is not None else None,
                        snf_cutoff=float(r.get("snf_cut_off", 0.0)) if r.get("snf_cut_off") is not None else None,
                        snf_deduction=float(r.get("snf_deduction", 0.0)) if r.get("snf_deduction") is not None else None,
                    )
                )
            await handler.save_prodata_rows(SaveProdataRowsCommand(rate_chart_id=result_id, rows=rows), user)

    # =========================================================
    # EDIT PAGE
    # =========================================================

    @staticmethod
    async def get_edit_page(request: Request, chart_id: UUID):
        user = request.state.user
        handler = GetHandler.ratechart_handler(request)
        # Charts created above the user, or no rate chart permission: open them in view mode
        try:
            await handler.ensure_modifiable(chart_id, user)
        except (RateChartNotFoundException, RateChartPermissionException):
            return RedirectResponse(f"/ratecharts/view/{chart_id}", status_code=303)

        dto = await handler.get(GetRateChartQuery(id=chart_id, owner=user))
        formula = None
        grids_data, prodata_data = [], []
        if int(dto.chart_type) == 0:
            formula = await handler.get_formula_config(rate_chart_id=chart_id)
        elif int(dto.chart_type) in (1, 3):
            grids = await handler.get_grid_rows(rate_chart_id=chart_id)
            grids_data = [{"fat": float(g.fat), "snf": float(g.snf), "rate": float(g.rate)} for g in grids]
        elif int(dto.chart_type) == 2:
            prodata = await handler.get_prodata_rows(rate_chart_id=chart_id)
            prodata_data = [{
                "fat_min": float(p.fat_min),
                "fat_max": float(p.fat_max),
                "snf_min": float(p.snf_min) if p.snf_min is not None else None,
                "snf_max": float(p.snf_max) if p.snf_max is not None else None,
                "kg_fat_rate": float(p.fat_rate_per_kg) if p.fat_rate_per_kg is not None else 0.0,
                "kg_snf_rate": float(p.snf_rate_per_kg) if p.snf_rate_per_kg is not None else 0.0,
                "snf_cut_off": float(p.snf_cutoff) if p.snf_cutoff is not None else 0.0,
                "snf_deduction": float(p.snf_deduction) if p.snf_deduction is not None else 0.0,
            } for p in prodata]

        # View model in the shape create_edit.html reads (chart + flattened formula fields)
        chart = {
            "id": str(dto.id),
            "chart_name": dto.chart_name,
            "chart_type": int(dto.chart_type),
            "rate_type": int(dto.calculation_type),
            "status": int(dto.status) == RateChartStatus.ACTIVE,
            "is_default": False,
            "cow_fat_pct": formula.cow_fat_percentage if formula else 0,
            "cow_snf_pct": formula.cow_snf_percentage if formula else 100,
            "cow_std_fat": formula.cow_standard_fat if formula else "",
            "cow_std_snf": formula.cow_standard_snf if formula else "",
            "cow_std_rate": formula.cow_standard_rate if formula else "",
            "buf_fat_pct": formula.buffalo_fat_percentage if formula else 0,
            "buf_snf_pct": formula.buffalo_snf_percentage if formula else 100,
            "buf_std_fat": formula.buffalo_standard_fat if formula else "",
            "buf_std_snf": formula.buffalo_standard_snf if formula else "",
            "buf_std_rate": formula.buffalo_standard_rate if formula else "",
        }
        return Renderer.page(
            request=request,
            template="pages/ratechart/create_edit.html",
            model={
                "chart": chart,
                "today": dto.effective_from.strftime("%Y-%m-%d"),
                "grids_data": grids_data,
                "prodata_data": prodata_data,
            },
        )

    # =========================================================
    # POST EDIT
    # =========================================================

    @staticmethod
    async def post_update_page(request: Request, chart_id: UUID):
        user = request.state.user
        handler = GetHandler.ratechart_handler(request)
        try:
            await handler.ensure_modifiable(chart_id, user)
        except RateChartPermissionException as exc:
            return JSONResponse({"detail": exc.message}, status_code=403)
        except RateChartNotFoundException:
            return JSONResponse({"detail": "You can only edit rate charts created by you or below you"}, status_code=403)

        body = await request.json()
        current = await handler.get(GetRateChartQuery(id=chart_id, owner=user))

        status_val = body.get("status", True)
        if isinstance(status_val, str):
            status_val = status_val.lower() == "true"

        # Chart type is fixed after creation; milk type / end date / description are not on this form
        command = UpdateRateChartCommand(
            id=chart_id,
            chart_name=(body.get("chart_name") or "").strip(),
            chart_type=current.chart_type,
            milk_type=current.milk_type,
            calculation_type=RateCalculationType(int(body.get("rate_type", int(current.calculation_type)))),
            effective_from=date.fromisoformat(body["effective_date"]) if body.get("effective_date") else current.effective_from,
            effective_to=current.effective_to,
            status=RateChartStatus.ACTIVE if status_val else RateChartStatus.INACTIVE,
            description=current.description,
            owner=user,
        )
        if not command.chart_name:
            return JSONResponse({"detail": "Chart name is required"}, status_code=400)

        await handler.update(command)
        await RateChartController._save_chart_config(handler, chart_id, int(current.chart_type), body, user)
        return JSONResponse({"status": "success", "id": str(chart_id)})

    # =========================================================
    # VIEW PAGE
    # =========================================================

    @staticmethod
    async def view_page(
        request: Request,
        chart_id: UUID,
    ):
        handler = GetHandler.ratechart_handler(request)
        chart = await handler.get(GetRateChartQuery(id=chart_id, owner=request.state.user))

        formula_config = None
        grids_data = []
        prodata_data = []

        if chart.chart_type == 0:
            try:
                formula_config = await handler.get_formula_config(rate_chart_id=chart_id)
            except Exception:
                pass
        elif chart.chart_type in (1, 3):
            try:
                grids = await handler._repository.get_grid_rows(rate_chart_id=chart_id)
                grids_data = [{"fat": float(g.fat), "snf": float(g.snf), "rate": float(g.rate)} for g in grids]
            except Exception:
                pass
        elif chart.chart_type == 2:
            try:
                prodata = await handler._repository.get_prodata_rows(rate_chart_id=chart_id)
                prodata_data = [{
                    "fat_min": float(p.fat_min),
                    "fat_max": float(p.fat_max),
                    "snf_min": float(p.snf_min) if p.snf_min is not None else None,
                    "snf_max": float(p.snf_max) if p.snf_max is not None else None,
                    "kg_fat_rate": float(p.fat_rate_per_kg) if p.fat_rate_per_kg is not None else 0.0,
                    "kg_snf_rate": float(p.snf_rate_per_kg) if p.snf_rate_per_kg is not None else 0.0,
                    "snf_cut_off": float(p.snf_cutoff) if p.snf_cutoff is not None else 0.0,
                    "snf_deduction": float(p.snf_deduction) if p.snf_deduction is not None else 0.0,
                } for p in prodata]
            except Exception:
                pass

        # Edit / default buttons only with the rate chart permission and when the chart is not above the user
        try:
            await handler.ensure_modifiable(chart_id, request.state.user)
            can_modify = True
        except (RateChartNotFoundException, RateChartPermissionException):
            can_modify = False

        return Renderer.page(
            request=request,
            template="pages/ratechart/view.html",
            model={
                "can_modify": can_modify,
                "chart": chart,
                "formula_config": formula_config,
                "grids_data": grids_data,
                "prodata_data": prodata_data,
            },
        )

    # =========================================================
    # POST DELETE
    # =========================================================

    @staticmethod
    async def delete_post(
        request: Request,
        chart_id: UUID,
    ):
        handler = GetHandler.ratechart_handler(request)
        await handler.delete(DeleteRateChartCommand(id=chart_id, owner=request.state.user))
        return HTMLResponse("success")

    # =========================================================
    # ASSIGN (VLCC / MCC)
    # =========================================================

    @staticmethod
    async def assign_page(request: Request):
        vlcc_handler = GetHandler.vlcc_handler(request)
        rate_handler = GetHandler.ratechart_handler(request)

        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=request.state.user))
        charts = await rate_handler.list(ListRateChartsQuery(size=500, owner=request.state.user))

        master_charts = [{"id": str(c.id), "chart_name": c.chart_name} for c in charts]

        return Renderer.page(
            request=request,
            template="pages/ratechart/assign.html",
            model={
                "shops": vlccs,
                "master_charts": master_charts,
                "groups": [],
            },
        )

    @staticmethod
    async def assign_mcc_page(request: Request):
        mcc_handler = GetHandler.mcc_handler(request)
        rate_handler = GetHandler.ratechart_handler(request)

        mccs = await mcc_handler.for_assigned_list(ListMccQuery(size=200, owner=request.state.user))
        charts = await rate_handler.list(ListRateChartsQuery(size=500, owner=request.state.user))

        master_charts = [{"id": str(c.id), "chart_name": c.chart_name} for c in charts]


        return Renderer.page(
            request=request,
            template="pages/ratechart/assign_mcc.html",
            model={
                "mccs": mccs,
                "master_charts": master_charts,
                "groups": [],
            },
        )

    @staticmethod
    async def get_assigned_api(request: Request, shop_id: UUID):
        vlcc_handler = GetHandler.vlcc_handler(request)
        try:
            vlcc = await vlcc_handler.get(GetVlccQuery(id=shop_id, owner=request.state.user))
            user_id = vlcc.user_id
        except Exception:
            return JSONResponse([])

        rate_handler = GetHandler.ratechart_handler(request)
        assignments = await rate_handler.get_assignments_by_owner(GetAssignmentsByOwnerQuery(owner_id=user_id))

        assigned_charts = []
        for a in assignments:
            try:
                chart = await rate_handler.get(GetRateChartQuery(id=a.rate_chart_id, owner=request.state.user))
                assigned_charts.append({"id": str(chart.id), "chart_name": chart.chart_name})
            except Exception:
                pass

        return JSONResponse(assigned_charts)

    @staticmethod
    async def get_assigned_mcc_api(request: Request, mcc_id: UUID):
        mcc_handler = GetHandler.mcc_handler(request)
        try:
            mcc = await mcc_handler.get(GetMccQuery(id=mcc_id, owner=request.state.user))
            user_id = mcc.user_id
        except Exception:
            return JSONResponse([])

        rate_handler = GetHandler.ratechart_handler(request)
        assignments = await rate_handler.get_assignments_by_owner(GetAssignmentsByOwnerQuery(owner_id=user_id))

        assigned_charts = []
        for a in assignments:
            try:
                chart = await rate_handler.get(GetRateChartQuery(id=a.rate_chart_id, owner=request.state.user))
                assigned_charts.append({"id": str(chart.id), "chart_name": chart.chart_name})
            except Exception:
                pass

        return JSONResponse(assigned_charts)

    @staticmethod
    async def _charts_visible(handler, chart_ids: list[str], owner: CurrentUser) -> bool:
        """A chart can only be mapped by users who can see it (rate chart access scope)."""
        try:
            for cid in chart_ids:
                await handler.get(GetRateChartQuery(id=UUID(cid), owner=owner))
        except Exception:
            return False
        return True

    @staticmethod
    async def post_assign_bulk_api(request: Request):
        body = await request.json()
        shop_id = UUID(body.get("shop_id"))
        chart_ids = body.get("chart_ids", [])

        vlcc_handler = GetHandler.vlcc_handler(request)
        print("vlcccccc: ", shop_id,)

        try:
            vlcc = await vlcc_handler.get(GetVlccQuery(id=shop_id, owner=request.state.user))
            user_id = vlcc.user_id
            print("KKKKKK:, ", user_id)

        except Exception as e:
            return JSONResponse({"detail": "VLCC not found"}, status_code=404)

        handler = GetHandler.ratechart_handler(request)
        if not await RateChartController._charts_visible(handler, chart_ids, request.state.user):
            return JSONResponse({"detail": "You can only map rate charts you have access to"}, status_code=403)
        await handler.delete_assignments_by_owner(user_id)
        for idx, cid in enumerate(chart_ids):
            cmd = CreateRateChartAssignmentCommand(
                owner_type=Role.VLCC,
                owner_id=user_id,
                rate_chart_id=UUID(cid),
                priority=idx,
                is_default=(idx == 0),
                created_by=request.state.user.id,
            )
            await handler.create_assignment(cmd)

        return JSONResponse({"status": "success"})

    @staticmethod
    async def post_assign_mcc_bulk_api(request: Request):
        body = await request.json()
        mcc_id = UUID(body.get("mcc_id"))
        chart_ids = body.get("chart_ids", [])

        mcc_handler = GetHandler.mcc_handler(request)
        try:
            mcc = await mcc_handler.get(GetMccQuery(id=mcc_id, owner=request.state.user))
            user_id = mcc.user_id
        except Exception:
            return JSONResponse({"detail": "MCC not found"}, status_code=404)

        handler = GetHandler.ratechart_handler(request)
        if not await RateChartController._charts_visible(handler, chart_ids, request.state.user):
            return JSONResponse({"detail": "You can only map rate charts you have access to"}, status_code=403)
        await handler.delete_assignments_by_owner(user_id)

        for idx, cid in enumerate(chart_ids):
            cmd = CreateRateChartAssignmentCommand(
                owner_type=Role.MCC,
                owner_id=user_id,
                rate_chart_id=UUID(cid),
                priority=idx,
                is_default=(idx == 0),
                created_by=request.state.user.id,
            )
            await handler.create_assignment(cmd)

        return JSONResponse({"status": "success"})

    @staticmethod
    async def load_mcc_boxes(request: Request, mcc_id: UUID | None = None):
        rate_handler = GetHandler.ratechart_handler(request)
        charts = await rate_handler.list(ListRateChartsQuery(size=500, owner=request.state.user))

        assigned_charts = []
        if mcc_id:
            mcc_handler = GetHandler.mcc_handler(request)
            try:
                mcc = await mcc_handler.get(GetMccQuery(id=mcc_id, owner=request.state.user))
                user_id = mcc.user_id
            except Exception:
                user_id = mcc_id

            assignments = await rate_handler.get_assignments_by_owner(GetAssignmentsByOwnerQuery(owner_id=user_id))
            assigned_ids = {a.rate_chart_id for a in assignments}
            pool_charts = await rate_handler.list(ListRateChartsQuery(size=500, owner=request.state.user))
            pool_charts = [c for c in pool_charts if c.id not in assigned_ids]
            for a in assignments:
                try:
                    c = await rate_handler.get(GetRateChartQuery(id=a.rate_chart_id, owner=request.state.user))
                    assigned_charts.append(c)
                except Exception:
                    pass
        else:
            pool_charts = charts

        return Renderer.page(
            request=request,
            template="pages/ratechart/assign_boxes_mcc.html",
            model={
                "pool_charts": pool_charts,
                "assigned_charts": assigned_charts,
            },
        )

    @staticmethod
    async def load_vlcc_boxes(request: Request, shop_id: UUID | None = None):
        rate_handler = GetHandler.ratechart_handler(request)
        charts = await rate_handler.list(ListRateChartsQuery(size=500, owner=request.state.user))

        assigned_charts = []
        if shop_id:
            vlcc_handler = GetHandler.vlcc_handler(request)
            try:
                # Assignments are stored against the VLCC's user, so resolve it (owner-scoped)
                vlcc = await vlcc_handler.get(GetVlccQuery(id=shop_id, owner=request.state.user))
                user_id = vlcc.user_id
            except Exception:
                user_id = shop_id

            assignments = await rate_handler.get_assignments_by_owner(GetAssignmentsByOwnerQuery(owner_id=user_id))
            assigned_ids = {a.rate_chart_id for a in assignments}
            pool_charts = await rate_handler.list(ListRateChartsQuery(size=500, owner=request.state.user))
            pool_charts = [c for c in pool_charts if c.id not in assigned_ids]
            for a in assignments:
                try:
                    c = await rate_handler.get(GetRateChartQuery(id=a.rate_chart_id, owner=request.state.user))
                    assigned_charts.append(c)
                except Exception:
                    pass
        else:
            pool_charts = charts

        return Renderer.page(
            request=request,
            template="pages/ratechart/assign_boxes_vlcc.html",
            model={
                "pool_charts": pool_charts,
                "assigned_charts": assigned_charts,
            },
        )

    @staticmethod
    async def calculate_rate(request: Request, chart_id: str, fat_percent: float, snf_percent: float, milk_type: int|None = None):
        if not chart_id:
            raise ValueError("Chart ID is required")
        if not fat_percent:
            raise ValueError("Fat percentage is required")
        if not snf_percent:
            raise ValueError("Snf is required")

        rate_handler = GetHandler.ratechart_handler(request)
        # milk_type 0 is COW, so test for None (not truthiness)
        rate = await rate_handler.get_rate_by_chart_id(chart_id=UUID(chart_id), fat_percent=fat_percent, snf_percent=snf_percent, milk_type=MilkType(milk_type) if milk_type is not None else None)
        value = f"{rate:.2f}" if rate is not None else "0.00"
        return HTMLResponse(
            content=f'''<div class="form-group" id="group-rate">
            <label>Rate (₹/Unit) *</label>
            <div class="input-icon-wrapper">
                <i class="fa-solid fa-indian-rupee-sign"></i>
                <input readonly type="number" value="{value}" step="0.01" name="rate_per_unit" id="cf-rate" class="form-control"
                    required hx-get="/ratecharts/get-rate" hx-trigger="rate:calculate"
                    hx-include="#cf-ratechart, #cf-fat, #cf-snf, #cf-type" hx-target="#group-rate" hx-swap="outerHTML">
            </div>
        </div>'''
                )
