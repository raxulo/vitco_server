"""
Farmer Web Presentation Controller
"""

from app.modules.administration.domain.enums import Role
from app.modules.ratechart.application.command import ListRateChartsQuery
from uuid import UUID
from fastapi import Request
from fastapi.responses import HTMLResponse

from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.web.framework.helpers import WebHelper
from app.modules.farmer.application.command import (
    GetFarmerQuery,
    ListFarmerQuery,
    DeleteFarmerQuery,
)
from app.modules.vlcc.application.command import ListVlccQuery, GetVlccQuery
from app.web.framework.renderer import Renderer
from app.web.farmer.assembler import FarmerAssembler
from app.modules.farmer.presentation.requests import CreateFarmerRequest, UpdateFarmerRequest


class FarmerController:

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
        handler = GetHandler.farmer_handler(request)
        current_user: CurrentUser = request.state.user

        # Fetch count for pagination
        if search.strip():
            total_items = await handler.count_search(keyword=search.strip(), owner=current_user)
        else:
            total_items = await handler.count(owner=current_user)

        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        result = await handler.list(
            ListFarmerQuery(
                keyword=search.strip(),
                offset=(page - 1) * limit,
                limit=limit,
                owner=current_user
            )
        )

        return Renderer.page(
            request=request,
            template="pages/farmer/list.html",
            model={
                "items": result,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
            },
        )

    # =========================================================
    # CREATE PAGE
    # =========================================================

    @staticmethod
    async def get_create_page(request: Request):
        # Fetch VLCC centers for dropdown selection
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=500, owner=request.state.user))

        return Renderer.page(
            request=request,
            template="pages/farmer/create_edit.html",
            model={
                "vlccs": vlccs,
                "rate_charts": [],  # Optional rate charts dropdown
            },
        )

    # =========================================================
    # EDIT PAGE
    # =========================================================

    @staticmethod
    async def get_edit_page(
        request: Request,
        farmer_id: UUID,
    ):
        WebHelper.deny_role(request, Role.FARMER)
        handler = GetHandler.farmer_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)

        farmer = await handler.get(GetFarmerQuery(id=farmer_id, owner=request.state.user))
        profile = await handler._profile_service.get_profile(farmer.user_id)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=500, owner=request.state.user))

        rate_charts = []
        if farmer.vlcc_id:
            try:
                from app.modules.ratechart.application.command import GetAssignmentsByOwnerQuery
                vlcc = await vlcc_handler.get(GetVlccQuery(id=farmer.vlcc_id, owner=request.state.user))
                rate_charts = await GetHandler.ratechart_handler(request).list(
                    ListRateChartsQuery(page=1, size=100,owner=CurrentUser(
                        id=vlcc.user_id,role=Role.VLCC, name="", permissions=frozenset()
                    ))
                )
            except Exception as e:
                print("Error loading rate charts for edit page:", e)

        return Renderer.page(
            request=request,
            template="pages/farmer/create_edit.html",
            model={
                "farmer": farmer,
                "user": profile.user,
                "address": profile.address,
                "bank_account": profile.bank_account,
                "vlccs": vlccs,
                "rate_charts": rate_charts,
            },
        )

    # =========================================================
    # VIEW PAGE
    # =========================================================

    @staticmethod
    async def view_page(
        request: Request,
        farmer_id: UUID,
    ):
        handler = GetHandler.farmer_handler(request)
        vlcc_handler = GetHandler.vlcc_handler(request)

        farmer = await handler.get(GetFarmerQuery(id=farmer_id, owner=request.state.user))
        profile = await handler._profile_service.get_profile(farmer.user_id)    

        vlcc = None
        if farmer.vlcc_id:
            try:
                vlcc = await vlcc_handler.get(GetVlccQuery(id=farmer.vlcc_id, owner=request.state.user))
            except Exception:
                pass

        return Renderer.page(
            request=request,
            template="pages/farmer/view.html",
            model={
                "farmer": farmer,
                "user": profile.user,
                "address": profile.address,
                "bank_account": profile.bank_account,
                "vlcc": vlcc,
            },
        )

    # =========================================================
    # POST CREATE
    # =========================================================

    @staticmethod
    async def post_create_page(request: Request):
        current_user: CurrentUser = request.state.user

        form_data = await request.form()
        data = CreateFarmerRequest.model_validate(form_data)

        command = FarmerAssembler.create(
            data=data,
            created_by=current_user.id,
        )

        handler = GetHandler.farmer_handler(request)
        result = await handler.full_create(command, current_user)

        if result:
            return Renderer.htmx_redirect("/farmer")

        return Renderer.empty().error(
            "Unable to register farmer"
        ).build()

    # =========================================================
    # POST UPDATE
    # =========================================================

    @staticmethod
    async def post_update_page(
        request: Request,
        farmer_id: UUID,
    ):
        WebHelper.deny_role(request, Role.FARMER)
        current_user: CurrentUser = request.state.user

        form_data = await request.form()
        data = UpdateFarmerRequest.model_validate(form_data)

        command = FarmerAssembler.update(
            data=data,
            farmer_id=farmer_id,
            updated_by=current_user.id,
        )

        # Set the id of the target farmer on the command

        handler = GetHandler.farmer_handler(request)
        result = await handler.full_update(command, owner=current_user)

        if result:
            return Renderer.htmx_redirect(
                f"/farmer/view/{farmer_id}"
            )

        return Renderer.empty().error(
            "Unable to update farmer"
        ).build()

    # =========================================================
    # POST DELETE
    # =========================================================

    @staticmethod
    async def delete_post(
        request: Request,
        farmer_id: UUID,
    ):
        handler = GetHandler.farmer_handler(request)
        await handler.delete(DeleteFarmerQuery(id=farmer_id, owner=request.state.user))
        return HTMLResponse("success")

    # =========================================================
    # CODE VALIDATION
    # =========================================================

    @staticmethod
    async def validate_code(request: Request, farmer_code: str, vlcc_id: UUID | None = None):
        if not vlcc_id:
            # Try to grab vlcc_id from request query params if present
            vlcc_id_str = request.query_params.get("vlcc_id")
            if vlcc_id_str:
                try:
                    vlcc_id = UUID(vlcc_id_str)
                except Exception:
                    pass

        if not vlcc_id:
            return HTMLResponse('<h6 style="color:red">Please select VLCC first</h6>')

        handler = GetHandler.farmer_handler(request)
        exists = await handler._farmer_repository.exists_code_in_vlcc(
            farmer_code.strip(), vlcc_id, request.state.user
        )

        if exists:
            return HTMLResponse(
                '<h6 style="color:red">Code already exists in this VLCC</h6>'
            )

        return HTMLResponse(
            '<h6 style="color:green">Code available</h6>'
        )

    # =========================================================
    # DYNAMIC RATE CHARTS FOR SELECTED VLCC
    # =========================================================

    @staticmethod
    async def get_rate_charts_options(request: Request):
        vlcc_id_str = request.query_params.get("vlcc_id")
        if not vlcc_id_str:
            return HTMLResponse('<option value="">Select Rate Chart (Optional)</option>')

        try:
            vlcc_id = UUID(vlcc_id_str)
            vlcc_handler = GetHandler.vlcc_handler(request)
            vlcc = await vlcc_handler.get(GetVlccQuery(id=vlcc_id, owner=request.state.user))

            rate_charts = await GetHandler.ratechart_handler(request).list(
                ListRateChartsQuery(
                    size=500,
                    owner=CurrentUser(
                        id=vlcc.user_id,
                        role=str(int(Role.VLCC)),
                        name=vlcc.name,
                        permissions=frozenset(),
                    )
                )
            )

            options = ['<select id="rate-chart-select" name="assigned_chart_rank" class="form-control">']
            if not rate_charts:
                options.append('<option value="1">Select Rate Chart (Optional)</option>')
            for idx, chart in enumerate(rate_charts):
                selected_str = 'selected' if idx == 0 else ''
                options.append(f'<option value="{idx + 1}" {selected_str}>{chart.chart_name}</option>')
            options.append('</select>')
            return HTMLResponse("\n".join(options))
        except Exception as e:
            print("Error loading rate chart options:", e)
            return HTMLResponse('<select id="rate-chart-select" name="assigned_chart_rank" class="form-control"><option value="1">Select Rate Chart (Optional)</option></select>')

    @staticmethod
    async def post_delete(request: Request, id: UUID):
        from fastapi.responses import RedirectResponse, Response
        from app.modules.farmer.application.command import DeleteFarmerCommand
        # pyrefly: ignore [missing-import]
        from app.web.renderer import Renderer
        user: CurrentUser = request.state.user
        handler = GetHandler.farmer_handler(request)
        try:
            await handler.delete(DeleteFarmerCommand(id=id, deleted_by=user.id, owner=user))
        except Exception as e:
            print("Error deleting Farmer:", e)
            if request.headers.get("HX-Request"):
                return Renderer.empty(status_code=400).error(str(e)).build()
            pass

        redirect_url = request.query_params.get("redirect")
        if request.headers.get("HX-Request"):
            if redirect_url:
                return Response(headers={"HX-Redirect": redirect_url})
            return Renderer.empty().success("Successfully deleted").build()

        return RedirectResponse("/farmer", status_code=303)

