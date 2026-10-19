"""
Dahboard Routes
"""

from fastapi import APIRouter

from app.web.mcc.controller import (
    MccController,
)

mcc_router = APIRouter(tags=["MCC"])

# -------------------------------
# AUTHENTICATE
# -------------------------------

mcc_router.add_api_route(
    path="/mcc", 
    endpoint=MccController.page, 
    methods=["GET"]
)

mcc_router.add_api_route(
    path="/mcc/create", 
    endpoint=MccController.get_create_page, 
    methods=["GET"]
)

mcc_router.add_api_route(
    path="/mcc/create", 
    endpoint=MccController.post_create_page, 
    methods=["POST"]
)

mcc_router.add_api_route(
    path="/mcc/validate-code", 
    endpoint=MccController.validate_code, 
    methods=["GET"]
)

mcc_router.add_api_route(
    path="/mcc/view/{id}", 
    endpoint=MccController.view_page, 
    methods=["GET"]
)

mcc_router.add_api_route(
    path="/mcc/edit/{id}", 
    endpoint=MccController.get_edit_page, 
    methods=["GET"]
)

mcc_router.add_api_route(
    path="/mcc/edit/{id}", 
    endpoint=MccController.post_update_page, 
    methods=["POST"]
)

mcc_router.add_api_route(
    path="/mcc/delete/{id}",
    endpoint=MccController.post_delete,
    methods=["POST"]
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