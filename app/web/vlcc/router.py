"""
VLCC Web Routes
"""

from fastapi import APIRouter

from app.web.vlcc.controller import VlccController


router = APIRouter(
    prefix="/vlcc",
    tags=["VLCC"],
)


router.add_api_route(
    "",
    VlccController.list_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    VlccController.create_page,
    methods=["GET"],
)

router.add_api_route(
    "/create",
    VlccController.create,
    methods=["POST"],
)

router.add_api_route(
    "/validate-code",
    VlccController.validate_code,
    methods=["GET"],
)

router.add_api_route(
    "/view/{vlcc_id}",
    VlccController.view_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{vlcc_id}",
    VlccController.edit_page,
    methods=["GET"],
)

router.add_api_route(
    "/edit/{vlcc_id}",
    VlccController.update,
    methods=["POST"],
)

router.add_api_route(
    "/validation-code",
    VlccController.validate_code,
    methods=["GET"],
)

router.add_api_route(
    "/validate-uic-code",
    VlccController.validate_uic_code,
    methods=["GET"],
)

router.add_api_route(
    "/vlccs-by-mcc/{mcc_id}",
    VlccController.get_vlccs_by_mcc,
    methods=["GET"],
)

router.add_api_route(
    "/delete/{id}",
    VlccController.post_delete,
    methods=["POST"],
)