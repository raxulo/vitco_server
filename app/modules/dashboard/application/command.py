from dataclasses import dataclass

from app.middleware.authentication import CurrentUser
from app.modules.dashboard.domain.enums import DashboardPeriod


@dataclass(slots=True, frozen=True, kw_only=True)
class GetDashboardQuery:
    owner: CurrentUser
    period: DashboardPeriod = DashboardPeriod.WEEK
