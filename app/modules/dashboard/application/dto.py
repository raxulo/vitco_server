from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class DashboardStats:
    total_vlcc: int
    total_farmers: int
    total_quantity: float
    total_amount: float


@dataclass(slots=True)
class RecentVlcc:
    name: str
    city: str
    status: str


@dataclass(frozen=True, slots=True)
class DashboardResult:
    stats: DashboardStats
    recent_vlcc: tuple[RecentVlcc, ...]
