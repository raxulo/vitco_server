"""
Recycle Bin Router (Super Admin only)
"""

from fastapi import APIRouter

from app.web.recycle_bin.controller import RecycleBinController

router = APIRouter(tags=["Web Recycle Bin"])

router.add_api_route(
    path="/recycle-bin",
    endpoint=RecycleBinController.list_page,
    methods=["GET"],
)

router.add_api_route(
    path="/recycle-bin/{entity_type}/{record_id}/impact",
    endpoint=RecycleBinController.impact_partial,
    methods=["GET"],
)

router.add_api_route(
    path="/recycle-bin/{entity_type}/{record_id}/purge",
    endpoint=RecycleBinController.purge_post,
    methods=["POST"],
)
