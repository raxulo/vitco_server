"""
Auth Routes
"""

from fastapi import APIRouter

from app.web.auth.controller import (
    AuthController,
)


auth_router = APIRouter(tags=["Web Auth"])



# -------------------------------
# AUTHENTICATE
# -------------------------------

auth_router.add_api_route(
    path="/login", 
    endpoint=AuthController.login_page, 
    methods=["GET"]
)

auth_router.add_api_route(
    path="/auth/login", 
    endpoint=AuthController.login_post_page, 
    methods=["POST"]
)

auth_router.add_api_route(
    path="/profile", 
    endpoint=AuthController.profile_page, 
    methods=["GET"]
)

# -------------------------------
# LOGOUT
# -------------------------------

auth_router.add_api_route(
    path="/logout",
    endpoint=AuthController.logout,
    methods=["GET"]
)