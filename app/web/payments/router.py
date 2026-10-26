from fastapi import APIRouter
from app.web.payments.controller import PaymentsController

router = APIRouter(
    prefix="/payments",
    tags=["Payment Ledger"],
)

router.add_api_route(
    "/overview",
    PaymentsController.overview_page,
    methods=["GET"],
)

router.add_api_route(
    "/api/users",
    PaymentsController.search_users_api,
    methods=["GET"],
)

router.add_api_route(
    "/api/centers",
    PaymentsController.search_centers_api,
    methods=["GET"],
)

router.add_api_route(
    "/user-to",
    PaymentsController.give_receive_page,
    methods=["GET"],
)

router.add_api_route(
    "/user-to",
    PaymentsController.post_give_receive,
    methods=["POST"],
)

router.add_api_route(
    "/history",
    PaymentsController.history_page,
    methods=["GET"],
)

router.add_api_route(
    "/outstanding",
    PaymentsController.outstanding_page,
    methods=["GET"],
)

router.add_api_route(
    "/pair-statement",
    PaymentsController.pair_statement_page,
    methods=["GET"],
)
