from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4
from email_validator import validate_email

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.administration.domain.enums import Role
from app.modules.administration.domain.entities import User
from app.modules.administration.domain.exceptions import (
    UserNotFoundException,
    UserAlreadyExistsException,
)
from app.modules.administration.infrastructure.repository import UserRepository
from app.modules.vlcc.domain.entities import Vlcc
from app.modules.vlcc.domain.exceptions import (
    VlccNotFoundException,
    VlccCodeAlreadyExistsException,
)
from app.modules.vlcc.infrastructure.repository import VlccRepository
from app.modules.vlcc.domain.dto import VlccDto, VlccListDto
from app.core.clock import now_naive_ist
from app.modules.vlcc.application.command import (
    CreateVlccCommand,
    UpdateVlccCommand,
    DeleteVlccCommand,
    GetVlccQuery,
    ListVlccQuery,
)


class VlccHandler:

    __slots__ = (
        "_database",
        "_user_repository",
        "_vlcc_repository",
        "_password",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        user_repository: UserRepository,
        vlcc_repository: VlccRepository,
        password: PasswordService,
    ) -> None:
        self._database = database
        self._user_repository = user_repository
        self._vlcc_repository = vlcc_repository
        self._password = password

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateVlccCommand,
    ) -> VlccDto:
        self._validate(command)

        await self._ensure_code_available(command.vlcc_code)
        await self._ensure_email_available(command.email)

        async with self._database.transaction():
            user = self._build_user(command)
            await self._user_repository.create(user)
            vlcc = self._build_vlcc(command, user.id)
            await self._vlcc_repository.create(vlcc)

        return self._to_dto(vlcc)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateVlccCommand,
    ) -> VlccDto:
        self._validate(command)

        async with self._database.transaction():
            vlcc = await self._vlcc_repository.get_by_id(command.id)
            if vlcc is None:
                raise VlccNotFoundException()

            user = await self._user_repository.get_by_id(vlcc.user_id)
            if user is None:
                raise UserNotFoundException()

            self._update_user(user, command)
            self._update_vlcc(vlcc, command)

            await self._user_repository.update(user)
            await self._vlcc_repository.update(vlcc)

        return self._to_dto(vlcc)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteVlccCommand,
    ) -> None:
        async with self._database.transaction():
            vlcc = await self._vlcc_repository.get_by_id(command.id)
            if vlcc is None:
                raise VlccNotFoundException()

            user = await self._user_repository.get_by_id(vlcc.user_id)
            if user is None:
                raise UserNotFoundException()

            # VLCC table does not support SoftDeleteMixin currently, so we set is_active=False
            vlcc.is_active = False
            user.is_active = False
            await self._user_repository.update(user)
            await self._vlcc_repository.update(vlcc)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetVlccQuery,
    ) -> VlccDto:
        vlcc = await self._vlcc_repository.get_by_id(query.id)
        if vlcc is None:
            raise VlccNotFoundException()

        return self._to_dto(vlcc)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListVlccQuery,
    ) -> list[VlccListDto]:
        if query.keyword:
            entities = await self._vlcc_repository.search(
                keyword=query.keyword,
                offset=query.offset,
                limit=query.size,
            )
        else:
            entities = await self._vlcc_repository.list(
                offset=query.offset,
                limit=query.size,
            )

        return [
            self._to_list_dto(entity)
            for entity in entities
        ]

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        vlcc: Vlcc,
    ) -> VlccListDto:
        return VlccListDto(
            id=vlcc.id,
            user_id=vlcc.user_id,
            vlcc_code=vlcc.vlcc_code,
            name=vlcc.name,
            entry_mode=vlcc.entry_mode,
            route_code=vlcc.route_code,
            is_active=vlcc.is_active,
        )

    def _build_user(self, command: CreateVlccCommand) -> User:
        now = now_naive_ist()
        return User(
            id=uuid4(),
            name=command.name,
            email=command.email.lower(),
            mobile=None,
            password_hash=self._password.hash(command.password),
            role=Role.VLCC,
            created_by=command.created_by,
            is_active=True,
            is_locked=False,
            created_at=now,
            updated_at=now,
        )

    def _build_vlcc(
        self,
        command: CreateVlccCommand,
        user_id: UUID,
    ) -> Vlcc:
        now = now_naive_ist()
        return Vlcc(
            id=uuid4(),
            user_id=user_id,
            uic_code=command.uic_code.strip(),
            vlcc_code=command.vlcc_code.strip(),
            name=command.name.strip(),
            contact_person=command.contact_person,
            address_id=command.address_id,
            bank_account_id=command.bank_account_id,
            milk_quality_config_id=command.milk_quality_config_id,
            settings_id=command.settings_id,
            profile_image=command.profile_image,
            entry_mode=command.entry_mode,
            route_code=command.route_code,
            soc_percentage=command.soc_percentage,
            farmer_enabled=command.farmer_enabled,
            is_active=True,
            created_by=command.created_by,
            created_at=now,
            updated_at=now,
        )

    def _validate(
        self,
        command: CreateVlccCommand | UpdateVlccCommand,
    ) -> None:
        if len(command.name.strip()) < 3:
            raise ValidationException("Invalid VLCC Name")

        # Email format validation
        validate_email(command.email)

    async def _ensure_code_available(self, code: str) -> None:
        if await self._vlcc_repository.exists_code(code):
            raise VlccCodeAlreadyExistsException()

    async def _ensure_email_available(self, email: str) -> None:
        if await self._user_repository.exists_email(email):
            raise UserAlreadyExistsException()

    def _update_user(
        self,
        user: User,
        command: UpdateVlccCommand,
    ) -> None:
        user.name = command.name.strip()
        user.email = command.email.lower()

        if command.password:
            user.password_hash = self._password.hash(command.password)

        user.updated_at = now_naive_ist()
        user.updated_by = command.updated_by

    def _update_vlcc(
        self,
        vlcc: Vlcc,
        command: UpdateVlccCommand,
    ) -> None:
        vlcc.uic_code = command.uic_code.strip()
        vlcc.vlcc_code = command.vlcc_code.strip()
        vlcc.name = command.name.strip()
        vlcc.contact_person = command.contact_person
        vlcc.address_id = command.address_id
        vlcc.bank_account_id = command.bank_account_id
        vlcc.milk_quality_config_id = command.milk_quality_config_id
        vlcc.settings_id = command.settings_id
        vlcc.profile_image = command.profile_image
        vlcc.entry_mode = command.entry_mode
        vlcc.route_code = command.route_code
        vlcc.soc_percentage = command.soc_percentage
        vlcc.farmer_enabled = command.farmer_enabled
        vlcc.is_active = command.is_active
        vlcc.updated_at = now_naive_ist()

    def _to_dto(self, vlcc: Vlcc) -> VlccDto:
        return VlccDto(
            id=vlcc.id,
            user_id=vlcc.user_id,
            uic_code=vlcc.uic_code,
            vlcc_code=vlcc.vlcc_code,
            name=vlcc.name,
            contact_person=vlcc.contact_person,
            address_id=vlcc.address_id,
            bank_account_id=vlcc.bank_account_id,
            milk_quality_config_id=vlcc.milk_quality_config_id,
            settings_id=vlcc.settings_id,
            profile_image=vlcc.profile_image,
            entry_mode=vlcc.entry_mode,
            route_code=vlcc.route_code,
            soc_percentage=vlcc.soc_percentage,
            farmer_enabled=vlcc.farmer_enabled,
            is_active=vlcc.is_active,
        )