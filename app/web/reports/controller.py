# app/web/reports/controller.py

from app.modules.reports.presentation.request import ReportPreviewRequest
from datetime import datetime
from uuid import UUID
from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.mcc.application.command import ListMccQuery, GetMccQuery
from app.modules.mcc.domain.enums import MccType
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.domain.enums import ReportType
from app.web.framework.renderer import Renderer

REPORT_TITLES = {
    ReportType.MCC_WEIGHT_SHIFT_SUMMARY.value: "Weight Shift Summary",
    ReportType.MCC_WEIGHT_DATE_WISE.value: "MCC Weight Date Wise",
    ReportType.MCC_WEIGHT_VLCC_WISE.value: "MCC Weight VLCC Wise",
    ReportType.MCC_WEIGHT_ROUTE_WISE.value: "MCC Weight Route Wise",
    ReportType.MCC_FIXED_RATE_SUMMARY.value: "MCC Fixed Rate Summary",
    ReportType.MCC_FIXED_RATE_PAYMENT_SUMMARY.value: "MCC Fixed Rate Payment Summary",
    ReportType.MCC_PAYMENT_SUMMARY.value: "MCC Payment Summary",
    ReportType.MCC_LEDGER.value: "Member Ledger",
    ReportType.MCC_SHIFT_SUMMARY.value: "MCC Shift Summary",
    ReportType.MCC_VLCC_BILL.value: "MCC VLCC Bill",
    ReportType.MCC_BILL_COMPARISON.value: "Milk Bill Comparison",
    ReportType.MCC_MILK_BILL_SUMMARY.value: "MCC Milk Bill Summary",
    ReportType.VLCC_SHIFT_SUMMARY.value: "VLCC Shift Summary",
    ReportType.DISPATCH_SUMMARY.value: "Dispatch Summary",
}

# Reports with a dedicated layout; all others use the generic result/preview partials
CUSTOM_RESULT_TEMPLATES = {
    ReportType.MCC_BILL_COMPARISON.value: "pages/reports/partials/bill_comparison_result.html",
    ReportType.MCC_PAYMENT_SUMMARY.value: "pages/reports/partials/payment_summary_result.html",
}
CUSTOM_PREVIEW_TEMPLATES = {
    ReportType.MCC_BILL_COMPARISON.value: "pages/reports/partials/bill_comparison_preview.html",
    ReportType.MCC_PAYMENT_SUMMARY.value: "pages/reports/partials/payment_summary_preview.html",
}

class ReportsController:

    __slots__ = ()

    @staticmethod
    async def page(request: Request):
        owner = request.state.user
        
        mcc_handler = GetHandler.mcc_handler(request)
        mccs = await mcc_handler.list(ListMccQuery(size=200, owner=owner))

        from app.modules.vlcc.application.command import ListVlccQuery
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=owner))
        
        initial_reports = []
        if mccs:
            mcc_type = mccs[0].mcc_type
            initial_reports = ReportsController._get_reports_for_mcc_type(mcc_type)

        return Renderer.page(
            request=request,
            template="pages/reports/mcc_reports.html",
            model={
                "mccs": mccs,
                "vlccs": vlccs,
                "reports": initial_reports,
                "today": datetime.now().date().isoformat(),
            },
        )

    @staticmethod
    async def vlcc_page(request: Request):
        from app.modules.vlcc.application.command import ListVlccQuery
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlccs = await vlcc_handler.list(ListVlccQuery(size=200, owner=request.state.user))
        
        reports = [
            {"value": ReportType.VLCC_SHIFT_SUMMARY.value, "label": "VLCC Shift Summary"},
            {"value": ReportType.VLCC_MEMBER_LEDGER.value, "label": "Member Ledger"},
            {"value": ReportType.VLCC_MILK_BILL_SUMMARY.value, "label": "VLCC Milk Bill Summary"},
            {"value": ReportType.VLCC_DUPLICATE_RECEIPT.value, "label": "VLCC Duplicate Receipt"},
            {"value": ReportType.DISPATCH_SUMMARY.value, "label": "Dispatch Summary"},
        ]

        return Renderer.page(
            request=request,
            template="pages/reports/vlcc_reports.html",
            model={
                "vlccs": vlccs,
                "reports": reports,
                "today": datetime.now().date().isoformat(),
            },
        )

    @staticmethod
    async def mcc_type_reports(request: Request, mcc_id: str):
        mcc_handler = GetHandler.mcc_handler(request)
        try:
            mcc = await mcc_handler.get(GetMccQuery(id=UUID(mcc_id), owner=request.state.user))
            reports = ReportsController._get_reports_for_mcc_type(mcc.mcc_type)
            print("RRRRRRRR", mcc)  
        except Exception as e:
            print("PPPPPP", e)
            reports = []

        return Renderer.page(
            request=request,
            template="pages/reports/partials/report_options.html",
            model={
                "reports": reports,
            },
        )

    @staticmethod
    async def generate(request: Request):
        try:
            form_data = dict(await request.form())
            for key in list(form_data.keys()):
                if form_data[key] in ("", "null", "None"):
                    form_data[key] = None
                    
            body = ReportPreviewRequest.model_validate(form_data)
            report_service = GetHandler.report_service(request)
            
            query = body.to_query(actor_id=request.state.user.id)
            result = await report_service.execute(query)

            total_pages = (result.total + query.size - 1) // query.size if result.total > 0 else 1
        
        except Exception as e:
            return Renderer.page(
                request=request,
                template="pages/reports/partials/report_error.html",
                model={
                    "error_message": str(e),
                },
            )

        return Renderer.page(
            request=request,
            template=CUSTOM_RESULT_TEMPLATES.get(
                query.report_type.value,
                "pages/reports/partials/report_result.html",
            ),
            model={
                "result": result,
                "report_type": query.report_type.value,
                "page": query.page,
                "size": query.size,
                "total_pages": total_pages,
            },
        )
    @staticmethod
    async def preview(request: Request):
        form_data = dict(await request.form())
        for key in list(form_data.keys()):
            if form_data[key] in ("", "null", "None"):
                form_data[key] = None
                
        body = ReportPreviewRequest.model_validate(form_data)
        report_service = GetHandler.report_service(request)
        
        query = body.to_query(actor_id=request.state.user.id)
        
        result = await report_service.execute(query)
        return Renderer.page(
            request=request,
            template=CUSTOM_PREVIEW_TEMPLATES.get(
                query.report_type.value,
                "pages/reports/partials/report_preview.html",
            ),
            model={
                "result": result,
                "report_type": query.report_type.value,
                "today": datetime.now().strftime("%d/%m/%Y"),
                "time": datetime.now().strftime("%H:%M:%S"),
            },
        )

    @staticmethod
    def _get_reports_for_mcc_type(mcc_type: MccType) -> list[dict[str, str]]:
        if mcc_type == MccType.WEIGHT:
            types = [
                ReportType.MCC_WEIGHT_SHIFT_SUMMARY,
                ReportType.MCC_WEIGHT_DATE_WISE,
                ReportType.MCC_WEIGHT_VLCC_WISE,
                ReportType.MCC_WEIGHT_ROUTE_WISE,
            ]
        elif mcc_type == MccType.FIXED_RATE:
            types = [
                ReportType.MCC_FIXED_RATE_SUMMARY,
                ReportType.MCC_FIXED_RATE_PAYMENT_SUMMARY,
                ReportType.MCC_LEDGER,
            ]
        else:
            types = [
                ReportType.MCC_SHIFT_SUMMARY,
                ReportType.MCC_VLCC_BILL,
                ReportType.MCC_BILL_COMPARISON,
                ReportType.MCC_PAYMENT_SUMMARY,
            ]
        return [{"value": t.value, "label": REPORT_TITLES.get(t.value, t.name)} for t in types]
