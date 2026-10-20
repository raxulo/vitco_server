from enum import StrEnum


class DashboardPeriod(StrEnum):
    TODAY = "today"
    WEEK = "7d"
    MONTH = "30d"

    @property
    def days(self) -> int:
        return {"today": 1, "7d": 7, "30d": 30}[self.value]

    @property
    def label(self) -> str:
        return {"today": "Today", "7d": "Last 7 days", "30d": "Last 30 days"}[self.value]

    @property
    def trend_days(self) -> int:
        """Days shown on the trend chart (a single day is too short to show a trend)."""
        return {"today": 7, "7d": 14, "30d": 30}[self.value]


class AdminRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    SUB_ADMIN = "SUB_ADMIN"