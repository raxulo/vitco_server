"""
Overview dashboard use-case.

Builds a role-specific `DashboardResult`:

- Super Admin / Admin / Sub Admin : network view (MCCs, VLCCs, farmers,
  VLCC collection and MCC receipts within their access scope).
- MCC    : milk received from VLCCs.
- VLCC   : milk collected from farmers, plus dispatch to the MCC.
- Farmer : their own pourings and earnings.

KPIs cover the selected period and carry the previous equal-length period
for comparison.
"""

from datetime import datetime, time, timedelta

from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.dashboard.application.command import GetDashboardQuery
from app.modules.dashboard.application.dto import (
    CollectionTotals,
    DashboardResult,
    Kpi,
    QuickAction,
    SplitItem,
    TrendPoint,
)
from app.modules.dashboard.domain.enums import DashboardPeriod
from app.modules.dashboard.infrastructure.repository import DashboardRepository

_ROLE_LABELS = {
    Role.SUPER_ADMIN: "Super Admin",
    Role.ADMIN: "Admin",
    Role.SUB_ADMIN: "Sub Admin",
    Role.MCC: "MCC",
    Role.VLCC: "VLCC",
    Role.FARMER: "Farmer",
}

_NETWORK_ROLES = (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN)

# Shortcuts per role; every href is an existing sidebar route
_QUICK_ACTIONS: dict[Role, tuple[QuickAction, ...]] = {
    Role.SUPER_ADMIN: (
        QuickAction("Add MCC", "/mcc/", "fa-solid fa-sitemap"),
        QuickAction("Add VLCC", "/vlcc/", "fa-solid fa-building"),
        QuickAction("Rate Charts", "/ratecharts/", "fa-solid fa-tags"),
        QuickAction("Managed Admins", "/sub-admins", "fa-solid fa-user-gear"),
        QuickAction("MCC Reports", "/mcc-reports", "fa-solid fa-file-invoice-dollar"),
        QuickAction("Payments", "/payments/overview", "fa-solid fa-money-bill-transfer"),
    ),
    Role.ADMIN: (
        QuickAction("Add MCC", "/mcc/", "fa-solid fa-sitemap"),
        QuickAction("Add VLCC", "/vlcc/", "fa-solid fa-building"),
        QuickAction("Rate Charts", "/ratecharts/", "fa-solid fa-tags"),
        QuickAction("Managed Admins", "/sub-admins", "fa-solid fa-user-gear"),
        QuickAction("MCC Reports", "/mcc-reports", "fa-solid fa-file-invoice-dollar"),
        QuickAction("Payments", "/payments/overview", "fa-solid fa-money-bill-transfer"),
    ),
    Role.SUB_ADMIN: (
        QuickAction("MCC Master", "/mcc/", "fa-solid fa-sitemap"),
        QuickAction("VLCC Master", "/vlcc/", "fa-solid fa-building"),
        QuickAction("Rate Charts", "/ratecharts/", "fa-solid fa-tags"),
        QuickAction("MCC Reports", "/mcc-reports", "fa-solid fa-file-invoice-dollar"),
        QuickAction("Payments", "/payments/overview", "fa-solid fa-money-bill-transfer"),
    ),
    Role.MCC: (
        QuickAction("MCC Collection", "/mcc-collections/", "fa-solid fa-truck-ramp-box"),
        QuickAction("MCC Reports", "/mcc-reports", "fa-solid fa-file-invoice-dollar"),
        QuickAction("VLCCs", "/vlcc/", "fa-solid fa-building"),
        QuickAction("Payments", "/payments/overview", "fa-solid fa-money-bill-transfer"),
    ),
    Role.VLCC: (
        QuickAction("New Collection", "/vlcc-collections/", "fa-solid fa-flask"),
        QuickAction("Dispatches", "/vlcc-dispatches", "fa-solid fa-truck-ramp-box"),
        QuickAction("Farmers", "/farmer/", "fa-solid fa-users"),
        QuickAction("VLCC Reports", "/reports/", "fa-solid fa-chart-bar"),
        QuickAction("Payments", "/payments/overview", "fa-solid fa-money-bill-transfer"),
    ),
    Role.FARMER: (
        QuickAction("My Collections", "/vlcc-collections/", "fa-solid fa-flask"),
        QuickAction("My Payments", "/payments/history", "fa-solid fa-indian-rupee-sign"),
    ),
}


class DashboardHandler:

    __slots__ = ("_repository",)

    def __init__(
        self,
        repository: DashboardRepository,
    ) -> None:
        self._repository = repository

    async def get_dashboard(
        self,
        query: GetDashboardQuery,
    ) -> DashboardResult:
        owner, period = query.owner, query.period
        role = owner.role_type
        repo = self._repository

        # Windows: [start, end) for the period, the one before it, and the trend range
        today_start = datetime.combine(now_naive_ist().date(), time.min)
        end = today_start + timedelta(days=1)
        start = end - timedelta(days=period.days)
        prev_start = start - timedelta(days=period.days)
        trend_start = end - timedelta(days=period.trend_days)

        # Primary collection source for this role
        if role == Role.MCC:
            source = repo.mcc_collections(owner)
            party_column = "vlcc_id"
        elif role in (Role.VLCC, Role.FARMER):
            source = repo.vlcc_collections(owner)
            party_column = "farmer_id"
        else:
            source = repo.vlcc_collections(owner)
            party_column = "vlcc_id"

        current = await repo.totals(source, start, end, party_column=party_column)
        previous = await repo.totals(source, prev_start, start, party_column=party_column)

        kpis = await self._kpis(owner, role, current, previous, start, end, prev_start)

        daily = await repo.daily(source, trend_start, end)
        trend = tuple(
            TrendPoint(day=d, quantity=daily.get(d, (0.0, 0.0))[0], amount=daily.get(d, (0.0, 0.0))[1])
            for d in ((trend_start + timedelta(days=i)).date() for i in range(period.trend_days))
        )

        shift_split = self._split(
            await repo.quantity_by(source, start, end, "shift"),
            order=(CollectionShift.MORNING, CollectionShift.EVENING),
        )
        milk_split = self._split(await repo.quantity_by(source, start, end, "milk_type"))

        if role == Role.FARMER:
            leaderboard_title, leaderboard = "", ()
        elif role == Role.VLCC:
            leaderboard_title = "Top Farmers"
            leaderboard = await repo.top_farmers(source, start, end)
        else:
            leaderboard_title = "Top VLCCs"
            leaderboard = await repo.top_vlccs(source, start, end)

        recent_party = "farmer" if role in (Role.VLCC, Role.FARMER) else "vlcc"
        recent = await repo.recent(source, party=recent_party)

        return DashboardResult(
            role_label=_ROLE_LABELS.get(role, "User"),
            user_name=owner.name or "",
            scope_label=await repo.scope_label(owner) or ("All network" if role == Role.SUPER_ADMIN else "Your network"),
            period=period.value,
            period_label=period.label,
            period_options=tuple((p.value, p.label) for p in DashboardPeriod),
            kpis=kpis,
            trend_title=self._trend_title(role),
            trend=trend,
            shift_split=shift_split,
            milk_split=milk_split,
            quality=(
                Kpi("Avg FAT", current.avg_fat, "pct", "fa-solid fa-droplet", "amber", previous.avg_fat or None),
                Kpi("Avg SNF", current.avg_snf, "pct", "fa-solid fa-flask", "teal", previous.avg_snf or None),
                Kpi("Avg Rate", current.avg_rate, "money", "fa-solid fa-indian-rupee-sign", "green", previous.avg_rate or None),
            ),
            leaderboard_title=leaderboard_title,
            leaderboard=leaderboard,
            recent_title="My Recent Pourings" if role == Role.FARMER else "Recent Collections",
            recent=recent,
            quick_actions=_QUICK_ACTIONS.get(role, ()),
        )

    # =========================================================
    # Role KPIs
    # =========================================================

    async def _kpis(
        self,
        owner: CurrentUser,
        role: Role,
        current: CollectionTotals,
        previous: CollectionTotals,
        start: datetime,
        end: datetime,
        prev_start: datetime,
    ) -> tuple[Kpi, ...]:
        repo = self._repository
        quantity = Kpi("Milk Collected", current.quantity, "qty", "fa-solid fa-droplet", "blue", previous.quantity, "Farmer → VLCC")
        amount = Kpi("Collection Value", current.amount, "money", "fa-solid fa-indian-rupee-sign", "green", previous.amount)

        if role in _NETWORK_ROLES:
            mcc_source = repo.mcc_collections(owner)
            received = await repo.totals(mcc_source, start, end)
            received_prev = await repo.totals(mcc_source, prev_start, start)
            return (
                Kpi("MCCs", await repo.count_mccs(owner), "int", "fa-solid fa-sitemap", "violet"),
                Kpi("VLCCs", await repo.count_vlccs(owner), "int", "fa-solid fa-building", "teal", hint=f"{current.parties} active in period"),
                Kpi("Farmers", await repo.count_farmers(owner), "int", "fa-solid fa-users", "amber"),
                quantity,
                Kpi("MCC Received", received.quantity, "qty", "fa-solid fa-warehouse", "rose", received_prev.quantity, "VLCC → MCC"),
                amount,
            )

        if role == Role.MCC:
            return (
                Kpi("Milk Received", current.quantity, "qty", "fa-solid fa-warehouse", "blue", previous.quantity, "from VLCCs"),
                Kpi("Payable Value", current.amount, "money", "fa-solid fa-indian-rupee-sign", "green", previous.amount),
                Kpi("Supplying VLCCs", current.parties, "int", "fa-solid fa-building", "teal", previous.parties),
                Kpi("Entries", current.entries, "int", "fa-solid fa-receipt", "violet", previous.entries),
            )

        if role == Role.VLCC:
            dispatched = await repo.dispatch_quantity(owner, start, end)
            dispatched_prev = await repo.dispatch_quantity(owner, prev_start, start)
            return (
                Kpi("Milk Collected", current.quantity, "qty", "fa-solid fa-droplet", "blue", previous.quantity, "from farmers"),
                Kpi("Farmer Payable", current.amount, "money", "fa-solid fa-indian-rupee-sign", "green", previous.amount),
                Kpi("Dispatched", dispatched, "qty", "fa-solid fa-truck-ramp-box", "rose", dispatched_prev, "to MCC"),
                Kpi("Active Farmers", current.parties, "int", "fa-solid fa-users", "amber", previous.parties,
                    f"of {await repo.count_farmers(owner)} registered"),
            )

        # Farmer
        return (
            Kpi("Milk Poured", current.quantity, "qty", "fa-solid fa-droplet", "blue", previous.quantity),
            Kpi("Earnings", current.amount, "money", "fa-solid fa-indian-rupee-sign", "green", previous.amount),
            Kpi("Days Poured", current.days, "int", "fa-solid fa-calendar-check", "violet", previous.days),
            Kpi("Entries", current.entries, "int", "fa-solid fa-receipt", "amber", previous.entries),
        )

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _split(values: dict, order: tuple = ()) -> tuple[SplitItem, ...]:
        """Quantity shares; `order` fixes category order so colors stay stable."""
        keys = list(order) + [k for k in values if k not in order]
        total = sum(values.values())
        return tuple(
            SplitItem(
                label=getattr(k, "name", str(k)).replace("_", " ").title(),
                value=values.get(k, 0.0),
                share=round(values.get(k, 0.0) / total * 100, 1) if total else 0.0,
            )
            for k in keys
            if k is not None
        )

    @staticmethod
    def _trend_title(role: Role) -> str:
        return {
            Role.MCC: "Milk Received per Day",
            Role.FARMER: "My Milk per Day",
        }.get(role, "Milk Collected per Day")
