# app/modules/dashboard/infrastructure/repository.py

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.collections.vlcc_collection.infrastructure.models import (
    VlccCollectionModel,
)
from app.modules.dashboard.application.command import UserCommand
from app.modules.dashboard.application.dto import (
    DashboardStats,
    RecentVlcc,
)
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.vlcc.infrastructure.models import VlccModel


class DashboardRepository:

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # Public API
    # =========================================================

    async def get_stats(
        self,
        command: UserCommand,
    ) -> DashboardStats:

        vlcc_filter = self._vlcc_scope(command)
        farmer_filter = self._farmer_scope(command)
        collection_filter = self._collection_scope(command)

        statement = select(
            self._count_vlcc(vlcc_filter).label("total_vlcc"),
            self._count_farmers(farmer_filter).label("total_farmers"),
            self._sum_quantity(collection_filter).label("total_quantity"),
            self._sum_amount(collection_filter).label("total_amount"),
        )

        result = await self._session.execute(statement)
        row = result.one()

        return DashboardStats(
            total_vlcc=row.total_vlcc or 0,
            total_farmers=row.total_farmers or 0,
            total_quantity=row.total_quantity or Decimal("0.00"),
            total_amount=row.total_amount or Decimal("0.00"),
        )

    async def get_recent_vlcc(
        self,
        command: UserCommand,
        *,
        limit: int = 5,
    ) -> tuple[RecentVlcc, ...]:

        statement = (
            select(
                VlccModel.name,
                VlccModel.is_active,
            )
            .where(
                *self._vlcc_scope(command),
            )
            .order_by(
                VlccModel.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(statement)

        return tuple(
            RecentVlcc(
                name=row.name,
                city="jkk",
                status=row.is_active,
            )
            for row in result
        )

    # =========================================================
    # Aggregates
    # =========================================================

    @staticmethod
    def _count_vlcc(filters: list):
        return (
            select(func.count(VlccModel.id))
            .where(*filters)
            .scalar_subquery()
        )

    @staticmethod
    def _count_farmers(filters: list):
        return (
            select(func.count(FarmerModel.id))
            .where(*filters)
            .scalar_subquery()
        )

    @staticmethod
    def _sum_quantity(filters: list):
        return (
            select(
                func.coalesce(
                    func.sum(VlccCollectionModel.quantity),
                    Decimal("0.00"),
                )
            )
            .where(*filters)
            .scalar_subquery()
        )

    @staticmethod
    def _sum_amount(filters: list):
        return (
            select(
                func.coalesce(
                    func.sum(VlccCollectionModel.total_amount),
                    Decimal("0.00"),
                )
            )
            .where(*filters)
            .scalar_subquery()
        )

    # =========================================================
    # Scope
    # =========================================================

    def _vlcc_scope(
        self,
        command: UserCommand,
    ) -> list:

        role = command.role

        if role == Role.SUPER_ADMIN:
            return []

        if role == Role.ADMIN:
            from sqlalchemy import exists, or_
            from sqlalchemy.orm import aliased
            from app.modules.administration.infrastructure.models import UserModel
            parent_user = aliased(UserModel)
            return [
                or_(
                    VlccModel.created_by == command.id,
                    exists(
                        select(1)
                        .select_from(UserModel)
                        .where(
                            UserModel.id == VlccModel.created_by,
                            or_(
                                UserModel.created_by == command.id,
                                exists(
                                    select(1)
                                    .select_from(parent_user)
                                    .where(
                                        parent_user.id == UserModel.created_by,
                                        parent_user.created_by == command.id,
                                    )
                                ),
                            ),
                        )
                        .correlate(VlccModel)
                    ),
                )
            ]

        if role == Role.SUB_ADMIN:
            from sqlalchemy import exists, or_
            from app.modules.administration.infrastructure.models import UserModel
            return [
                or_(
                    VlccModel.created_by == command.id,
                    exists(
                        select(1)
                        .select_from(UserModel)
                        .where(
                            UserModel.id == VlccModel.created_by,
                            UserModel.created_by == command.id,
                        )
                        .correlate(VlccModel)
                    ),
                )
            ]

        if role == Role.VLCC:
            return [
                VlccModel.user_id == command.id,
            ]

        if role == Role.MCC:
            return [
                VlccModel.created_by == command.id,
            ]

        return [
            VlccModel.id == None,
        ]

    def _farmer_scope(
        self,
        command: UserCommand,
    ) -> list:

        role = command.role

        if role == Role.SUPER_ADMIN:
            return []

        if role == Role.ADMIN:
            from sqlalchemy import exists, or_
            from sqlalchemy.orm import aliased
            from app.modules.administration.infrastructure.models import UserModel
            parent_user = aliased(UserModel)
            return [
                exists(
                    select(1)
                    .select_from(VlccModel)
                    .where(
                        VlccModel.id == FarmerModel.vlcc_id,
                        or_(
                            VlccModel.created_by == command.id,
                            exists(
                                select(1)
                                .select_from(UserModel)
                                .where(
                                    UserModel.id == VlccModel.created_by,
                                    or_(
                                        UserModel.created_by == command.id,
                                        exists(
                                            select(1)
                                            .select_from(parent_user)
                                            .where(
                                                parent_user.id == UserModel.created_by,
                                                parent_user.created_by == command.id,
                                            )
                                        ),
                                    ),
                                )
                                .correlate(VlccModel)
                            ),
                        )
                    )
                    .correlate(FarmerModel)
                )
            ]

        if role == Role.SUB_ADMIN:
            from sqlalchemy import exists, or_
            from app.modules.administration.infrastructure.models import UserModel
            return [
                exists(
                    select(1)
                    .select_from(VlccModel)
                    .where(
                        VlccModel.id == FarmerModel.vlcc_id,
                        or_(
                            VlccModel.created_by == command.id,
                            exists(
                                select(1)
                                .select_from(UserModel)
                                .where(
                                    UserModel.id == VlccModel.created_by,
                                    UserModel.created_by == command.id,
                                )
                                .correlate(VlccModel)
                            ),
                        )
                    )
                    .correlate(FarmerModel)
                )
            ]

        if role == Role.VLCC:
            return [
                FarmerModel.vlcc_id == command.id,
            ]

        if role == Role.MCC:
            return [
                FarmerModel.vlcc_id == command.id,
            ]

        return [
            FarmerModel.id == None,
        ]

    def _collection_scope(
        self,
        command: UserCommand,
    ) -> list:

        role = command.role

        base = [
            VlccCollectionModel.is_deleted.is_(False),
        ]

        if role == Role.SUPER_ADMIN:
            return base

        if role == Role.ADMIN:
            from sqlalchemy import exists, or_
            from sqlalchemy.orm import aliased
            from app.modules.administration.infrastructure.models import UserModel
            parent_user = aliased(UserModel)
            return [
                *base,
                exists(
                    select(1)
                    .select_from(VlccModel)
                    .where(
                        VlccModel.id == VlccCollectionModel.vlcc_id,
                        or_(
                            VlccModel.created_by == command.id,
                            exists(
                                select(1)
                                .select_from(UserModel)
                                .where(
                                    UserModel.id == VlccModel.created_by,
                                    or_(
                                        UserModel.created_by == command.id,
                                        exists(
                                            select(1)
                                            .select_from(parent_user)
                                            .where(
                                                parent_user.id == UserModel.created_by,
                                                parent_user.created_by == command.id,
                                            )
                                        ),
                                    ),
                                )
                                .correlate(VlccModel)
                            ),
                        )
                    )
                    .correlate(VlccCollectionModel)
                )
            ]

        if role == Role.SUB_ADMIN:
            from sqlalchemy import exists, or_
            from app.modules.administration.infrastructure.models import UserModel
            return [
                *base,
                exists(
                    select(1)
                    .select_from(VlccModel)
                    .where(
                        VlccModel.id == VlccCollectionModel.vlcc_id,
                        or_(
                            VlccModel.created_by == command.id,
                            exists(
                                select(1)
                                .select_from(UserModel)
                                .where(
                                    UserModel.id == VlccModel.created_by,
                                    UserModel.created_by == command.id,
                                )
                                .correlate(VlccModel)
                            ),
                        )
                    )
                    .correlate(VlccCollectionModel)
                )
            ]

        if role == Role.VLCC:
            return [
                *base,
                VlccCollectionModel.vlcc_id == command.id,
            ]

        if role == Role.MCC:
            return [
                *base,
                VlccCollectionModel.vlcc_id == command.id,
            ]

        return [
            VlccCollectionModel.id == None,
        ]