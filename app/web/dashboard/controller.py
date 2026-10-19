"""
Auth Web Controller
"""

from app.middleware.authentication import CurrentUser
from app.modules.dashboard.application.dto import DashboardResult
from app.modules.dashboard.application.command import UserCommand
from app.web.framework.helpers import WebHelper
from app.web.framework.htmx import HTMXBuilder
from app.modules.dependencies import GetHandler
from app.modules.auth.application.command import LoginCommand
from fastapi import Form
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.web.framework.renderer import Renderer

from app.web.auth.presenter import (
    LoginPresenter,
)


class DashboardController:

    @staticmethod
    async def page(request: Request):
        user: CurrentUser | None = getattr(request.state, "user", None)
        if not user:
            return Renderer.redirect(url="/login")

        command = UserCommand(
            id=user.id,
            role=user.role_type,
        )
        result: DashboardResult = await GetHandler.dashboard_handler(request).get_dashboard(command=command)
        return Renderer.page(
            request=request, 
            template="pages/dashboard/dashboard.html", 
            model=result
        )
