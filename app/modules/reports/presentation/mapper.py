# presentation/mappers.py

from app.modules.reports.application.dto import ReportResult
from app.modules.reports.presentation.schemas import ReportResponse


def to_response(
    result: ReportResult,
) -> ReportResponse:

    return ReportResponse(
        report_type=result.report_type,
        rows=result.rows,
        total=result.total,
        page=result.page,
        size=result.size,
    )