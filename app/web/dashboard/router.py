"""
Dahboard Routes
"""

from fastapi import APIRouter

from app.web.dashboard.controller import (
    DashboardController,
)


dashboard_router = APIRouter(tags=["Dashboard"])



# -------------------------------
# AUTHENTICATE
# -------------------------------

dashboard_router.add_api_route(
    path="/dashboard", 
    endpoint=DashboardController.page, 
    methods=["GET"]
)

# -------------------------------
# AUTHORIZE
# -------------------------------


# -------------------------------
# TOKEN
# -------------------------------


# -------------------------------
# OAUTH
# -------------------------------


# -------------------------------
# LOGOUT
# -------------------------------