from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.database.manager import DatabaseManager

from app.modules.common.address.domain.entities import (
    Address,
)

from app.modules.common.address.domain.exceptions import (
    AddressAlreadyExistsException,
    AddressNotFoundException,
    InvalidAddressException,
)

from app.modules.common.address.domain.repository import (
    IAddressRepository,
)

from app.modules.common.address.application.command import (
    CreateAddressCommand,
    UpdateAddressCommand,
    GetAddressQuery,
)

from app.modules.common.address.application.dto import (
    AddressDto,
)


class AddressHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self,
        database: DatabaseManager,
        repository: IAddressRepository,
    ) -> None:

        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateAddressCommand,
    ) -> AddressDto:

        self._validate(
            line=command.line,
            state=command.state,
            city=command.city,
            pincode=command.pincode,
        )

        # One address per user
        existing = (
            await self._repository
            .get_by_user_id(command.user_id)
        )

        if existing is not None:
            raise AddressAlreadyExistsException()

        now = datetime.now(UTC)

        address = Address(
            id=uuid4(),

            user_id=command.user_id,

            line=self._clean(command.line),
            state=self._clean(command.state),
            city=self._clean(command.city),
            pincode=self._clean(command.pincode),

            created_at=now,
            updated_at=now,
        )

        async with self._database.transaction():

            await self._repository.create(
                address
            )

        return self._to_dto(address)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetAddressQuery,
    ) -> AddressDto:

        address = await self._repository.get_by_id(
            query.id
        )

        if address is None:
            raise AddressNotFoundException()

        return self._to_dto(address)

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user(
        self,
        user_id: UUID,
    ) -> AddressDto | None:

        address = (
            await self._repository
            .get_by_user_id(user_id)
        )

        if address is None:
            return None

        return self._to_dto(address)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateAddressCommand,
    ) -> AddressDto:

        self._validate(
            line=command.line,
            state=command.state,
            city=command.city,
            pincode=command.pincode,
        )

        async with self._database.transaction():

            address = (
                await self._repository
                .get_by_id(command.id)
            )

            if address is None:
                raise AddressNotFoundException()

            address.line = self._clean(
                command.line
            )

            address.state = self._clean(
                command.state
            )

            address.city = self._clean(
                command.city
            )

            address.pincode = self._clean(
                command.pincode
            )

            address.updated_at = datetime.now(UTC)

            await self._repository.update(
                address
            )

        return self._to_dto(address)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        address_id: UUID,
    ) -> None:

        async with self._database.transaction():

            exists = await self._repository.exists(
                address_id
            )

            if not exists:
                raise AddressNotFoundException()

            await self._repository.delete(
                address_id
            )

    # =========================================================
    # VALIDATION
    # =========================================================

    @staticmethod
    def _validate(
        line: str | None,
        state: str | None,
        city: str | None,
        pincode: str | None,
    ) -> None:

        if line and len(line.strip()) > 255:
            raise InvalidAddressException(
                "Address line is too long."
            )

        if state and len(state.strip()) > 255:
            raise InvalidAddressException(
                "State is too long."
            )

        if city and len(city.strip()) > 255:
            raise InvalidAddressException(
                "City is too long."
            )

        if pincode:

            value = pincode.strip()

            if not value.isdigit():
                raise InvalidAddressException(
                    "Invalid pincode."
                )

            if not 4 <= len(value) <= 10:
                raise InvalidAddressException(
                    "Invalid pincode length."
                )

    # =========================================================
    # CLEAN
    # =========================================================

    @staticmethod
    def _clean(
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None

    # =========================================================
    # DTO
    # =========================================================

    @staticmethod
    def _to_dto(
        address: Address,
    ) -> AddressDto:

        return AddressDto(
            id=address.id,
            user_id=address.user_id,

            line=address.line,
            state=address.state,
            city=address.city,
            pincode=address.pincode,
        )