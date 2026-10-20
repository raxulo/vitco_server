"""
Dashboard DTOs.

`DashboardResult` is the complete, role-specific view model the overview page
renders; the remaining classes are its building blocks and the raw rows the
repository returns.
"""

from dataclasses import dataclass
from datetime import date, datetime


# =========================================================
# Repository rows
# =========================================================

@dataclass(frozen=True, slots=True)
class CollectionTotals:
    quantity: float
    amount: float
    fat_qty: float
    snf_qty: float
    entries: int
    parties: int
    days: int

    @property
    def avg_fat(self) -> float:
        return round(self.fat_qty / self.quantity, 2) if self.quantity else 0.0

    @property
    def avg_snf(self) -> float:
        return round(self.snf_qty / self.quantity, 2) if self.quantity else 0.0

    @property
    def avg_rate(self) -> float:
        return round(self.amount / self.quantity, 2) if self.quantity else 0.0


@dataclass(frozen=True, slots=True)
class RankRow:
    code: str
    name: str
    quantity: float
    amount: float


@dataclass(frozen=True, slots=True)
class RecentRow:
    collected_at: datetime
    shift: int
    code: str
    name: str
    quantity: float
    fat: float
    snf: float
    amount: float


# =========================================================
# View model
# =========================================================

@dataclass(frozen=True, slots=True)
class Kpi:
    label: str
    value: float
    fmt: str                     # "int" | "qty" | "money" | "pct"
    icon: str
    tone: str                    # css accent key: blue | violet | amber | green | teal | rose
    previous: float | None = None
    hint: str = ""

    @property
    def delta_pct(self) -> float | None:
        """Change vs the previous period; None when there is nothing to compare."""
        if self.previous is None or self.previous == 0:
            return None
        return round((self.value - self.previous) / self.previous * 100, 1)


@dataclass(frozen=True, slots=True)
class TrendPoint:
    day: date
    quantity: float
    amount: float


@dataclass(frozen=True, slots=True)
class SplitItem:
    label: str
    value: float
    share: float                 # 0..100


@dataclass(frozen=True, slots=True)
class QuickAction:
    label: str
    href: str
    icon: str


@dataclass(frozen=True, slots=True)
class DashboardResult:
    role_label: str
    user_name: str
    scope_label: str
    period: str
    period_label: str
    period_options: tuple[tuple[str, str], ...]
    kpis: tuple[Kpi, ...]
    trend_title: str
    trend: tuple[TrendPoint, ...]
    shift_split: tuple[SplitItem, ...]
    milk_split: tuple[SplitItem, ...]
    quality: tuple[Kpi, ...]
    leaderboard_title: str
    leaderboard: tuple[RankRow, ...]
    recent_title: str
    recent: tuple[RecentRow, ...]
    quick_actions: tuple[QuickAction, ...]
