# application/service.py

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

        return await executor.execute(query)