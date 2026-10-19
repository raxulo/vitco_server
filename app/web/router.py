"""
RealTimeTransfer
================

Web Router Registrar

Python 3.13+
"""

from fastapi import FastAPI

from fastapi import APIRouter, Request, Query
from starlette.responses import Response, RedirectResponse
from fastapi.responses import HTMLResponse

from app.web.auth.router import auth_router
from app.web.dashboard.router import dashboard_router
from app.web.mcc.router import mcc_router
from app.web.vlcc.router import router as vlcc_router
from app.web.farmer.router import router as farmer_router
from app.web.mcc_collection.router import router as mcc_collection_router
from app.web.vlcc_collection.router import router as vlcc_collection_router
from app.web.ratechart.router import router as ratechart_router
from app.web.unit.router import router as unit_router
from app.web.item.router import router as item_router
from app.web.route.router import router as route_router
from app.web.reports.router import router as reports_router
from app.web.vlcc_dispatch.router import router as dispatch_router
from app.web.sub_admin.router import router as sub_admin_router
from app.web.payments.router import router as payments_router
from app.web.advanced_item.router import router as advance_item_router
from app.web.marketplace.router import marketplace_router
from app.web.marketplace.controller import MarketplaceWebController

root_router = APIRouter(tags=["Web Root"])

@root_router.get("/", response_class=HTMLResponse)
async def root_page(
    request: Request,
    category: str = Query("all"),
    animal_type: str = Query("all"),
    query: str = Query(""),
    sort_by: str = Query("default"),
) -> Response:
    """Home Page (/) Endpoint: Unauthenticated visitors see Marketplace UI, authenticated users go to Dashboard."""
    user = getattr(request.state, "user", None)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return await MarketplaceWebController.index_page(
        request=request,
        category=category,
        animal_type=animal_type,
        query=query,
        sort_by=sort_by,
    )


class WebRouterRegistrar:
    """
    Register all web routes.
    """
    __slots__ = ()

    @classmethod
    def register(cls, app: FastAPI) -> None:
        app.include_router(root_router)
        app.include_router(auth_router)
        app.include_router(dashboard_router)
        app.include_router(mcc_router)
        app.include_router(vlcc_router)
        app.include_router(farmer_router)
        app.include_router(mcc_collection_router)
        app.include_router(vlcc_collection_router)
        app.include_router(ratechart_router)
        app.include_router(unit_router)
        app.include_router(item_router)
        app.include_router(route_router)
        app.include_router(reports_router)
        app.include_router(dispatch_router)
        app.include_router(sub_admin_router)
        app.include_router(payments_router)
        app.include_router(advance_item_router)
        app.include_router(marketplace_router)