"""
Dashboard Web Controller
"""

from fastapi import Request

from app.middleware.authentication import CurrentUser
from app.modules.dashboard.application.command import GetDashboardQuery
from app.modules.dashboard.domain.enums import DashboardPeriod
from app.modules.dependencies import GetHandler
from app.web.framework.renderer import Renderer


class DashboardController:

    @staticmethod
    async def page(request: Request, period: str = DashboardPeriod.WEEK.value):
        user: CurrentUser | None = getattr(request.state, "user", None)
        if not user:
            return Renderer.redirect(url="/login")

        try:
            selected = DashboardPeriod(period)
        except ValueError:
            selected = DashboardPeriod.WEEK

        result = await GetHandler.dashboard_handler(request).get_dashboard(
            GetDashboardQuery(owner=user, period=selected)
        )
        return Renderer.page(
            request=request,
            template="pages/dashboard/dashboard.html",
            model={"dashboard": result},
        )
