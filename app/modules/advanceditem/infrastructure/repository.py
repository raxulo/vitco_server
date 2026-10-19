from sqlalchemy import func
from app.middleware.authentication import CurrentUser
from app.modules.masters.items.infrastructure.models import ItemMasterModel
from app.modules.administration.infrastructure.models import UserModel
from sqlalchemy.orm import aliased
from app.core.database.manager import DatabaseManager
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.advanceditem.infrastructure.models import (
    AdvanceItemModel,
    AdvanceRecordModel,
)


class AdvanceRecordRepository:

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database

    @property
    def _session(self):
        return self._database.session

    # =========================================================
    # CREATE
    # =========================================================

    async def create_record(
        self,
        record: AdvanceRecordModel,
    ) -> AdvanceRecordModel:

        self._session.add(record)

        return record

    # =========================================================
    # CREATE MULTIPLE ITEMS
    #
    # One add_all() instead of N add() calls
    # =========================================================

    async def create_items(
        self,
        items: list[AdvanceItemModel],
    ) -> None:

        if not items:
            return

        self._session.add_all(items)

    # =========================================================
    # GET RECORD
    # =========================================================

    async def get_record( self,
        record_id: UUID,
    ) -> AdvanceRecordModel | None:

        stmt = (
            select(AdvanceRecordModel)
            .where(
                AdvanceRecordModel.id == record_id,
            )
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # GET USER ADVANCE RECORDS
    #
    # Important:
    # No OFFSET based pagination here.
    # Service/API should use cursor pagination for huge data.
    # =========================================================

    async def get_user_records(
        self,
        *,
        user_id: UUID,
        limit: int = 50,
        before_id: UUID | None = None,
    ) -> list[AdvanceRecordModel]:

        stmt = (
            select(AdvanceRecordModel)
            .where(
                AdvanceRecordModel.user_id == user_id,
            )
            .order_by(
                AdvanceRecordModel.advance_date.desc(),
                AdvanceRecordModel.id.desc(),
            )
            .limit(limit)
        )

        if before_id is not None:

            cursor = await self._session.scalar(
                select(
                    AdvanceRecordModel.advance_date,
                ).where(
                    AdvanceRecordModel.id == before_id,
                )
            )

            if cursor is not None:
                stmt = stmt.where(
                    AdvanceRecordModel.advance_date
                    <= cursor
                )

        result = await self._session.scalars(stmt)

        return list(result)

    # =========================================================
    # GET RECORD ITEMS
    # =========================================================

    async def get_items(
        self,
        record_id: UUID,
    ) -> list[AdvanceItemModel]:

        stmt = (
            select(AdvanceItemModel)
            .where(
                AdvanceItemModel.advance_record_id
                == record_id,
            )
            .order_by(
                AdvanceItemModel.created_at.asc(),
            )
        )

        result = await self._session.scalars(stmt)

        return list(result)

    # =========================================================
    # GET RECORD + ITEMS
    #
    # Two small indexed queries are often better than
    # loading a large ORM graph.
    # =========================================================

    async def get_record_with_items(
        self,
        record_id: UUID,
    ) -> tuple[
        AdvanceRecordModel | None,
        list[AdvanceItemModel],
    ]:

        record = await self.get_record(record_id)

        if record is None:
            return None, []

        items = await self.get_items(record_id)

        return record, items

    # =========================================================
    # TOTAL OF ONE ADVANCE
    # =========================================================

    async def get_total(
        self,
        record_id: UUID,
    ) -> Decimal:

        from sqlalchemy import func

        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        AdvanceItemModel.amount
                    ),
                    0,
                )
            )
            .where(
                AdvanceItemModel.advance_record_id
                == record_id,
            )
        )

        return await self._session.scalar(stmt) or Decimal("0")

    # =========================================================
    # USER TOTAL ADVANCE
    # =========================================================

    async def get_user_total(
        self,
        user_id: UUID,
    ) -> Decimal:

        from sqlalchemy import func

        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        AdvanceItemModel.amount
                    ),
                    0,
                )
            )
            .join(
                AdvanceRecordModel,
                AdvanceRecordModel.id
                == AdvanceItemModel.advance_record_id,
            )
            .where(
                AdvanceRecordModel.user_id == user_id,
            )
        )

        return await self._session.scalar(stmt) or Decimal("0")

    # =========================================================
    # DELETE RECORD
    #
    # CASCADE will delete its items.
    # =========================================================

    async def delete_record(
        self,
        record_id: UUID,
    ) -> bool:

        stmt = (
            delete(AdvanceRecordModel)
            .where(
                AdvanceRecordModel.id == record_id,
            )
        )

        result = await self._session.execute(stmt)

        return result.rowcount > 0

    async def get_detail_rows(
        self,
        advance_id: UUID,
    ) -> list[tuple]:

        selected_user = aliased(UserModel, name="selected_user")

        creator_user = aliased(UserModel, name="creator_user")

        stmt = (
            select(

                AdvanceRecordModel.id,
                AdvanceRecordModel.user_id,
                AdvanceRecordModel.advance_date,
                AdvanceRecordModel.total_amount,
                AdvanceRecordModel.created_by,
                AdvanceRecordModel.notes,

                selected_user.name.label("user_name"),
                selected_user.role.label("user_role"),
                creator_user.name.label("created_by_name"),
                creator_user.role.label("created_by_role"),
                AdvanceItemModel.id.label("item_id"),
                AdvanceItemModel.item_master_id,
                AdvanceItemModel.quantity,
                AdvanceItemModel.unit_rate,
                AdvanceItemModel.amount,
                ItemMasterModel.item_name,
                ItemMasterModel.item_code,
            )

            .join(
                AdvanceItemModel,
                AdvanceItemModel.advance_record_id
                == AdvanceRecordModel.id,
            )

            .join(
                ItemMasterModel,
                ItemMasterModel.id
                == AdvanceItemModel.item_master_id,
            )

            .join(
                selected_user,
                selected_user.id
                == AdvanceRecordModel.user_id,
            )

            .join(
                creator_user,
                creator_user.id
                == AdvanceRecordModel.created_by,
            )

            .where(
                AdvanceRecordModel.id == advance_id,
            )

            .order_by(
                AdvanceItemModel.id,
            )
        )

        result = await self._session.execute(stmt)

        return result.all()

    async def get_list(self,  owner: CurrentUser, size=10, page=1,) -> list[ tuple]:
        selected_user = aliased(UserModel, name="selected_user")
        creator_user = aliased(UserModel, name="creator_user")

        stmt = (
            select(
                AdvanceRecordModel.id,
                AdvanceRecordModel.user_id,
                AdvanceRecordModel.created_by,
                AdvanceRecordModel.advance_date,
                AdvanceRecordModel.total_amount,
                AdvanceRecordModel.notes,
                selected_user.name.label("user_name"),
                selected_user.role.label("user_role"),
                creator_user.name.label("created_by_name"),
                creator_user.role.label("created_by_role"),
            )
            .join(
                selected_user,
                selected_user.id
                == AdvanceRecordModel.user_id,
            )
            .join(
                creator_user,
                creator_user.id
                == AdvanceRecordModel.created_by,
            )
        )
        result = await self._session.execute(stmt)
        return result.all()

    async def count(self, owner: CurrentUser) -> int:
        stmt = (
            select(
                func.count(AdvanceRecordModel.id),
            )
        )
        result = await self._session.scalar(stmt)
        return result

    async def flush(self) -> None:
        await self._session.flush()