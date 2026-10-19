from fastapi import APIRouter
from app.web.vlcc_dispatch.controller import DispatchController

router = APIRouter(
    prefix="/vlcc-dispatches",
    tags=["VLCC Dispatches"],
)

router.add_api_route(
    "",
    DispatchController.list_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    DispatchController.get_create_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    DispatchController.post_create,
    methods=["POST"],
)

router.add_api_route(
    "/edit/{id}",
    DispatchController.get_edit_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{id}",
    DispatchController.post_update,
    methods=["POST"],
)

router.add_api_route(
    "/delete/{id}",
    DispatchController.post_delete,
    methods=["POST"],
)
