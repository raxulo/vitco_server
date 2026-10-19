### `app/modules/dashboard/application/handler.py`
from app.modules.dashboard.application.command import UserCommand
from app.modules.dashboard.application.dto import (
    DashboardResult,
)
from app.modules.dashboard.infrastructure.repository import (
    DashboardRepository,
)


class DashboardHandler:

    __slots__ = ("_repository",)

    def __init__(
        self,
        repository: DashboardRepository,
    ) -> None:
        self._repository = repository

    async def get_dashboard(
        self,
        command: UserCommand,
    ) -> DashboardResult:

        stats = await self._repository.get_stats(
            command,
        )

        recent_vlcc = await self._repository.get_recent_vlcc(
            command,
            limit=5,
        )

        return DashboardResult(
            stats=stats,
            recent_vlcc=recent_vlcc,
        )