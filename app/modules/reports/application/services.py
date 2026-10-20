# application/service.py

from app.modules.reports.application.formatting import format_report
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.application.registry import ReportRegistry


class ReportService:

    def __init__(
        self,
        registry: ReportRegistry,
    ):
        self._registry = registry

    async def execute(
        self,
        query: ReportQuery,
    ):
        executor = self._registry.get(
            query.report_type
        )

        # Same display precision for every report: qty/rate/amount 2 decimals, FAT/SNF 1
        return format_report(await executor.execute(query))