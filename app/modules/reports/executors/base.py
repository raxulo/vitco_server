# application/executors/base.py

from app.modules.administration.infrastructure.models import UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Integer, cast, select
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
from app.modules.collections.mcc_collection.domain.enums import CollectionShift, QuantityCollectionMode
from datetime import datetime
from sqlalchemy import and_, or_
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from abc import ABC, abstractmethod

from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.application.dto import ReportResult
from app.core.numeric import fixed, to_fixed_2


class ReportExecutor(ABC):

    # =========================================================
    # Code filters (member / VLCC / farmer / route codes)
    #
    # Codes are compared numerically so leading zeros never matter:
    # users sometimes type "00001" for what is really "1".
    # =========================================================

    @staticmethod
    def code_as_int(column):
        """The code column as an integer, so "00001" and "1" are equal."""
        return cast(column, Integer)

    @staticmethod
    def _code_int(value) -> int | None:
        """A user-entered code as int; None when blank or not all digits."""
        text = str(value).strip() if value is not None else ""
        return int(text) if text.isdigit() else None

    @classmethod
    def code_match(cls, column, value):
        """
        Equality on a code, ignoring leading zeros ("00001" matches "1").
        Falls back to an exact text match when the value is not all digits.
        """
        number = cls._code_int(value)
        if number is None:
            return column == value
        return cls.code_as_int(column) == number

    @classmethod
    def code_between(cls, column, low, high) -> list:
        """
        Inclusive numeric range conditions for a code column, ignoring leading
        zeros. A blank / non-digit bound is skipped. Returns a list to splat
        into ``.where(...)`` (or extend a filter list with).
        """
        numeric = cls.code_as_int(column)
        conditions = []
        low_int = cls._code_int(low)
        high_int = cls._code_int(high)
        if low_int is not None:
            conditions.append(numeric >= low_int)
        if high_int is not None:
            conditions.append(numeric <= high_int)
        return conditions

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
        return to_fixed_2(fat / quantity) if quantity > 0 else 0.0

    def avg_snf(self, snf, quantity):
        return to_fixed_2(snf / quantity) if quantity > 0 else 0.0

    def avg_rate(self, amount, quantity):
        return to_fixed_2(amount / quantity) if quantity > 0 else 0.0

    def short_date(self, datetime_obj: datetime) -> str:
        return datetime_obj.strftime("%d/%m")

    # -----------------------------------------
    # Manual-entry markers ('*')
    # Quantity carries '*' when quantity_collection_mode is MANUAL,
    # FAT carries '*' when measurement_mode is MANUAL.
    # Only per-entry values are marked; totals and averages never are.
    # -----------------------------------------
    @staticmethod
    def is_manual(mode) -> bool:
        return mode is not None and int(mode) == QuantityCollectionMode.MANUAL

    @staticmethod
    def marked(value, manual) -> str:
        """Value truncated to 2 decimals, with '*' when it was entered manually."""
        return f"{fixed(value)}{'*' if manual else ''}"

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