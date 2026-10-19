from sqlalchemy import update
from app.modules.common.address.application.command import UpdateAddressCommand

from uuid import UUID

from sqlalchemy import select

from app.core.database.manager import DatabaseManager

from app.modules.common.address.domain.entities import Address
from app.modules.common.address.domain.repository import (
    IAddressRepository,
)

from app.modules.common.address.infrastructure.mapper import (
    AddressMapper,
)

from app.modules.common.address.infrastructure.models import (
    AddressModel,
)


class AddressRepository(
    IAddressRepository
):

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self._database = database

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        address: Address,
    ) -> None:

        model = AddressMapper.to_model(
            address
        )

        self._database.session.add(model)

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        address_id: UUID,
    ) -> Address | None:

        stmt = (
            select(AddressModel)
            .where(
                AddressModel.id == address_id,
            )
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return AddressMapper.to_entity(model)

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> Address | None:

        stmt = (
            select(AddressModel)
            .where(
                AddressModel.user_id == user_id,
            )
            .limit(1)
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return AddressMapper.to_entity(model)

    # =========================================================
    # EXISTS
    # =========================================================

    async def exists(
        self,
        address_id: UUID,
    ) -> bool:

        stmt = (
            select(AddressModel.id)
            .where(
                AddressModel.id == address_id,
            )
            .limit(1)
        )

        return (
            await self._database.session.scalar(stmt)
        ) is not None

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        address: Address,
    ) -> None:

        model = await self._database.session.get(
            AddressModel,
            address.id,
        )

        if model is None:
            return

        model.line = address.line
        model.state = address.state
        model.city = address.city
        model.pincode = address.pincode

        model.updated_at = address.updated_at

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        address_id: UUID,
    ) -> None:

        model = await self._database.session.get(
            AddressModel,
            address_id,
        )

        if model is None:
            return

        await self._database.session.delete(
            model
        )
    async def update_address_by_command(self, data: UpdateAddressCommand) -> Address:
        stmt = (
            update(AddressModel)
            .where(
                AddressModel.id == data.id,
            )
            .values(
                line=data.line,
                state=data.state,
                city=data.city,
                pincode=data.pincode,
            )
            .execution_options(synchronize_session="fetch")
            .returning(AddressModel)
        )

        model = await self._database.session.scalar(stmt)

        if model is None:
            return None

        return AddressMapper.to_entity(model)
    
        