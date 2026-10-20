# application/executors/base.py

from app.modules.administration.infrastructure.models import UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.common.address.infrastructure.models import AddressModel
from typing import Any
from typing import Mapping
from app.modules.reports.application.dto import ReportMetadata
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from uuid import UUID
from app.modules.collections.mcc_collection.domain.enums import MilkType
from datetime import timedelta
from datetime import time
from app.modules.admin.infrastructure import models
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from datetime import datetime
from sqlalchemy import and_, or_
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from abc import ABC, abstractmethod

from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.application.dto import ReportResult


class ReportExecutor(ABC):

    @abstractmethod
    async def execute(
        self,
        query: ReportQuery,
    ) -> ReportResult:
        ...

    @property
    @abstractmethod
    def headers(self) -> list[str]:
        ...  
    
    @abstractmethod
    def apply_filters(
        self,
    ) -> AppliedOnFilters:
        ...  


    def filters(
        self,
        model,
        query: ReportQuery,
    ) -> list:

        config = self.apply_filters()
        filters = []
        model: MccCollectionModel

        # -----------------------------------------
        # MCC
        # -----------------------------------------
        if config.actor_type == Role.MCC:

            if config.mcc_id and query.mcc_id:
                filters.append(
                    model.mcc_id == query.mcc_id
                )

        # -----------------------------------------
        # VLCC
        # -----------------------------------------
        elif config.actor_type == Role.VLCC:

            if config.vlcc_id and query.vlcc_id:
                filters.append(
                    model.vlcc_id == query.vlcc_id
                )

        # -----------------------------------------
        # Date + Shift
        # -----------------------------------------
        filters.append(
            self._date_filters(
                model,
                query,
                config,
            )
        )

        # -----------------------------------------
        # Single shift
        # -----------------------------------------
        # if (
        #     config.shift
        #     and query.start_shift is not None
        # ):
        #     filters.append(
        #         model.shift == CollectionShift(query.start_shift)
        #     )

        # -----------------------------------------
        # Milk type
        # -----------------------------------------
        if (
            config.milk_type
            and query.milk_type is not None
        ):
            filters.append(
                model.milk_type == MilkType(query.milk_type)
            )

        # -----------------------------------------
        # Deleted
        # -----------------------------------------
        if config.is_deleted:
            filters.append(
                model.is_deleted.is_(False)
            )

        return filters

    async def get_mcc(
        self,
        session: AsyncSession,
        mcc_id: UUID | None,
    ) -> Mapping[str, Any] | None:
        if not mcc_id:
            return None

        stmt = (
            select(
                MccModel.name,
                MccModel.code,
                UserModel.name.label("owner_name"),
                AddressModel.line,
                AddressModel.city,
                AddressModel.state,
                AddressModel.pincode,
            )
            .outerjoin(
                AddressModel,
                AddressModel.id == MccModel.address_id,
            ).outerjoin(
                UserModel,
                UserModel.id == MccModel.created_by,
            )
            .where(MccModel.id == mcc_id)
        )

        return (
            await session.execute(stmt)
        ).mappings().one_or_none()


    async def get_vlcc(
        self,
        session,
        vlcc_id,
    ):
        if not vlcc_id:
            return None

        stmt = (
            select(
                VlccModel.name,
                VlccModel.vlcc_code,
                VlccModel.uic_code,
                UserModel.name.label("owner_name"),
                AddressModel.line,
                AddressModel.city,
                AddressModel.state,
                AddressModel.pincode,
            )
            .outerjoin(AddressModel, AddressModel.id == VlccModel.address_id)
            .outerjoin(UserModel, UserModel.id == VlccModel.created_by)
            .where(VlccModel.id == vlcc_id)
        )
        return (await session.execute(stmt)).mappings().one_or_none()

    def avg_fat(self, fat, quantity):
        return round(fat / quantity, 2) if quantity > 0 else 0

    def avg_snf(self, snf, quantity):
        return round(snf / quantity, 2) if quantity > 0 else 0

    def avg_rate(self, amount, quantity):
        return round(amount / quantity, 2) if quantity > 0 else 0

    def short_date(self, datetime_obj: datetime) -> str:
        return datetime_obj.strftime("%d/%m")

    def _date_filters(
        self,
        model,
        query: ReportQuery,
        config: AppliedOnFilters,
    ):
        if not query.start_date:
            return None

        end_date = (query.end_date or query.start_date) if config.date_range else query.start_date

        start = datetime.combine(query.start_date, time.min)
        end = datetime.combine(end_date + timedelta(days=1), time.min)

        conditions = [
            and_(
                model.collected_at >= start,
                model.collected_at < end,
            )
        ]

        if not config.shift_range:
            # Single shift applied to every day in the window
            if query.start_shift is not None:
                conditions.append(model.shift == query.start_shift)
            return and_(*conditions)

        # Shift range runs from (start date, start shift) to (end date, end shift):
        # only the first day is cut by the start shift and only the last day by the end shift.
        # MORNING is 0, so compare against None, never on truthiness; and the column
        # stores enum names, so use equality rather than >= / <= ordering.
        if query.start_shift == CollectionShift.EVENING:
            conditions.append(or_(
                model.collected_at >= start + timedelta(days=1),
                model.shift == CollectionShift.EVENING,
            ))
        if query.end_shift == CollectionShift.MORNING:
            conditions.append(or_(
                model.collected_at < end - timedelta(days=1),
                model.shift == CollectionShift.MORNING,
            ))

        return and_(*conditions)