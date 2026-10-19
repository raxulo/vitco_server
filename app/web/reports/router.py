# app/web/reports/router.py

from fastapi import APIRouter
from app.web.reports.controller import ReportsController

router = APIRouter(tags=["Reports"])

router.add_api_route(
    path="/mcc-reports",
    endpoint=ReportsController.page,
    methods=["GET"],
)

router.add_api_route(
    path="/mcc-reports/mcc-type-reports",
    endpoint=ReportsController.mcc_type_reports,
    methods=["GET"],
)

router.add_api_route(
    path="/mcc-reports/generate",
    endpoint=ReportsController.generate,
    methods=["POST"],
)

router.add_api_route(
    path="/mcc-reports/preview",
    endpoint=ReportsController.preview,
    methods=["POST"],
)

router.add_api_route(
    path="/reports",
    endpoint=ReportsController.vlcc_page,
    methods=["GET"],
)

router.add_api_route(
    path="/reports/",
    endpoint=ReportsController.vlcc_page,
    methods=["GET"],
)

router.add_api_route(
    path="/reports/generate",
    endpoint=ReportsController.generate,
    methods=["POST"],
)

router.add_api_route(
    path="/reports/preview",
    endpoint=ReportsController.preview,
    methods=["POST"],
)
