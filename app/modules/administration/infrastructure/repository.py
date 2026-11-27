from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.mcc.infrastructure.models import MccModel
from operator import and_
from sqlalchemy.orm import aliased
from sqlalchemy import alias
from dataclasses import asdict
from sqlalchemy import case, func, update
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.administration.domain.entities import UserDto
from app.modules.administration.domain.enums import Role
from uuid import UUID
from operator import or_
from app.modules.administration.application.command import ListUsersQuery
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.entities import NO_BRAND, Brand, User
from sqlalchemy import select

from app.modules.administration.domain.repository import IUserRepository
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.mapper import UserMapper
from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser


class UserRepository(IUserRepository):

    def __init__(self, database:DatabaseManager):

        self._database = database

    @property
    def _session(self):
        return self._database.session

    async def create(
        self,
        user: User,
    ) -> User:

        self._session.add(UserMapper.to_model(user))
        await self._session.flush()
        return user

    async def exists_email(
        self,
        email: str,
        exclude_user_id: str | UUID | None = None,
    ) -> bool:
        """Email taken by any user (case-insensitive), optionally ignoring one user (on update)."""
        if not email or not str(email).strip():
            return False

        stmt = (
            select(UserModel.id)
            .where(
                func.lower(UserModel.email) == str(email).strip().lower()
            )
        )
        if exclude_user_id is not None:
            stmt = stmt.where(UserModel.id != UUID(str(exclude_user_id)))

        result = await self._database.session.scalar(stmt.limit(1))

        return result is not None

    async def exists_mobile(
        self,
        mobile: str,
        exclude_user_id: str | UUID | None = None,
    ) -> bool:
        if not mobile or not str(mobile).strip():
            return False

        clean_mobile = str(mobile).strip()
        stmt = (
            select(UserModel.id)
            .where(UserModel.mobile == clean_mobile)
        )
        if exclude_user_id is not None:
            try:
                ex_uuid = UUID(str(exclude_user_id))
                stmt = stmt.where(UserModel.id != ex_uuid)
            except Exception:
                pass
        stmt = stmt.limit(1)

        result = await self._database.session.scalar(stmt)
        return result is not None

    async def exists_user(
        self,
        email: str,
        mobile: str,
    ) -> bool:

        stmt = (
            select(UserModel.id)
            .where(
                or_(
                    UserModel.email == email,
                    UserModel.mobile == mobile
                )
            )
            .limit(1)
        )

        result = await self._database.session.scalar(stmt)

        return result is not None

    async def get_by_id(
        self,
        id: UUID,
    ) -> User | None:

        Creator = aliased(UserModel, name="creator")

        stmt = (
            select(
                UserModel,
                Creator.name.label("creator_name"),
                Creator.id.label("creator_id"),
            )
            .outerjoin(
                Creator,
                Creator.id == UserModel.created_by,
            )
            .where(
                UserModel.id == id,
            )
        )

        result = await self._database.session.execute(stmt)
        row = result.one_or_none()

        if row is None:
            return None

        return self._to_entity(
            row.UserModel,
            row.creator_name,
            row.creator_id,
        )
    async def get_by_email(
        self,
        email: str,
    ) -> User | None:

        if not email or not email.strip():
            return None

        clean_val = email.strip()

        stmt = (
            select(
                UserModel,
                MccModel.id.label("mcc_id"),
                VlccModel.id.label("vlcc_id"),
                VlccModel.vlcc_type.label("vlcc_type"),
                FarmerModel.id.label("farmer_id"),
            )
            .outerjoin(
                MccModel,
                and_(
                    MccModel.user_id == UserModel.id,
                    UserModel.role == Role.MCC,
                ),
            )
            .outerjoin(
                VlccModel,
                and_(
                    VlccModel.user_id == UserModel.id,
                    UserModel.role.in_([Role.VLCC, Role.VLCC_FARMER]),
                ),
            )
            .outerjoin(
                FarmerModel,
                and_(
                    FarmerModel.user_id == UserModel.id,
                    UserModel.role == Role.FARMER,
                ),
            )
            # Email ignores case and surrounding spaces; an exact match still wins
            # when older rows differ only by case
            .where(
                or_(
                    func.lower(func.trim(UserModel.email)) == clean_val.lower(),
                    UserModel.mobile == clean_val,
                )
            )
            .order_by(case((UserModel.email == clean_val, 0), else_=1))
            .limit(1)
        )

        result = await self._database.session.execute(stmt)
        row = result.first()

        if row is None:
            return None

        user_model = row.UserModel

        from app.modules.vlcc.domain.enums import VlccType
        raw_vlcc_type = getattr(row, "vlcc_type", None)
        is_vlcc_farmer = False
        if raw_vlcc_type is not None:
            if (
                raw_vlcc_type == VlccType.VLCC_FARMER_TYPE
                or raw_vlcc_type == 1
                or getattr(raw_vlcc_type, "value", None) == 1
                or str(raw_vlcc_type).strip().upper() in ("VLCC_FARMER_TYPE", "1")
            ):
                is_vlcc_farmer = True

        if is_vlcc_farmer:
            user_model.role = Role.VLCC_FARMER

        if user_model.role == Role.MCC:
            own_id = row.mcc_id
        elif user_model.role in (Role.VLCC, Role.VLCC_FARMER):
            own_id = row.vlcc_id
        elif user_model.role == Role.FARMER:
            own_id = row.farmer_id
        else:
            own_id = None

        setattr(user_model, "own_id", own_id)
        return UserMapper.to_entity(user_model)
    
    async def exists_super_admin(self) -> bool:

        stmt = (

            select(UserModel.id)

            .where(

                UserModel.role == Role.SUPER_ADMIN

            )

            .limit(1)

        )

        result = await self._session.scalar(stmt)

        return result is not None

    async def delete(
        self,
        user_id,
    ):

        model = await self._database.session.get(UserModel, user_id)

        if model:
            await self._database.session.delete(model)
            await self._database.session.flush()

    async def update(
        self,
        user: User,
    ):

        model = await self._database.session.get(UserModel, user.id)

        model.name = user.name
        model.email = user.email
        model.mobile = user.mobile
        model.role = user.role
        if user.password_hash:
            model.password_hash = user.password_hash
        model.is_active = user.is_active
        model.is_deleted = user.is_deleted
        model.deleted_at = user.deleted_at
        model.deleted_by = user.deleted_by
        model.is_locked = user.is_locked
        model.created_by = user.created_by
        model.profile_url = user.profile_image

        await self._database.session.flush()
        return model


    async def set_brand(self, user_id: UUID, *, enabled: bool, logo_url: str | None) -> None:
        """Write an Admin's Self Brand switch and logo URL (None removes the logo)."""
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(self_brand=enabled, brand_logo_url=logo_url, updated_at=now_naive_ist())
        )

    async def brand_of(self, owner: CurrentUser) -> Brand:
        """
        The Self Brand `owner` works under: its own row for an Admin, otherwise the
        Admin found above it (Sub Admin -> Admin, MCC / VLCC -> creator chain).
        Super Admin and users with no Admin above them get no brand.
        """
        role = owner.role_type
        if role == Role.SUPER_ADMIN:
            return NO_BRAND
        if role == Role.ADMIN:
            condition = UserModel.id == owner.id
        else:
            # Imported here: the hierarchy module imports this package's models
            from app.modules.administration.infrastructure.hierarchy import Hierarchy

            condition = UserModel.id.in_(Hierarchy.ancestor_users(owner))

        row = (
            await self._session.execute(
                select(UserModel.self_brand, UserModel.brand_logo_url, UserModel.name)
                .where(
                    condition,
                    UserModel.role == Role.ADMIN,
                    UserModel.is_deleted.is_(False),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return NO_BRAND
        return Brand(enabled=bool(row.self_brand), logo_url=row.brand_logo_url, name=row.name)

    async def user_update(self, entity: UpdateUserCommand) -> bool:
        data = entity.model_dump()
        data.pop("id")
        # Ownership never changes on update; the command's default None would detach
        # the user from its creator and break the access hierarchy
        data.pop("created_by", None)

        if "profile_image" in data:
            if data["profile_image"] is None:
                data.pop("profile_image")
            else:
                data["profile_url"] = data.pop("profile_image")

        if not data.get("password_hash"):
            data.pop("password_hash")
        # Mobile is mandatory: an update without one keeps the current number
        if not data.get("mobile"):
            data.pop("mobile", None)
        result = await self._session.execute(
            update(UserModel)
            .where(UserModel.id == entity.id)
            .values(**data,updated_at=now_naive_ist())
        )

        return result.rowcount > 0


    async def list(
        self,
        query: ListUsersQuery,
    ) -> list[User]:
        conditions = []

        Creator = aliased(UserModel, name="creator")

        # ---------------------------------------------------------
        # SEARCH
        # ---------------------------------------------------------
        if search := query.search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    UserModel.name.ilike(pattern),
                    UserModel.email.ilike(pattern),
                    UserModel.mobile.ilike(pattern),
                )
            )

        # ---------------------------------------------------------
        # FILTERS
        # ---------------------------------------------------------
        # Soft-deleted users live only in the Super Admin recycle bin
        conditions.append(UserModel.is_deleted.is_(False))

        if query.role is not None:
            conditions.append(UserModel.role == query.role)

        if query.is_active is not None:
            conditions.append(
                UserModel.is_active == query.is_active
            )

        # ---------------------------------------------------------
        # ACCESS SCOPE
        # ---------------------------------------------------------
        owner = query.owner

        if owner is None:
            raise PermissionError(
                "Owner is not provided."
            )

        if owner.role_type == Role.SUPER_ADMIN:
            pass

        elif owner.role_type == Role.ADMIN:
            conditions.append(
                or_(
                    UserModel.id == owner.id,
                    and_(
                        UserModel.role == Role.SUB_ADMIN,
                        UserModel.created_by == owner.id,
                    ),
                )
            )

        elif owner.role_type == Role.SUB_ADMIN:
            raise PermissionError(
                "SubAdmin is not allowed to access user management."
            )

        else:
            raise PermissionError(
                "Permission denied for user management."
            )

        # ---------------------------------------------------------
        # QUERY
        # ---------------------------------------------------------
        stmt = (
            select(
                UserModel,
                Creator.id.label("owner_id"),
                Creator.name.label("owner_name"),
            )
            .outerjoin(
                Creator,
                Creator.id == UserModel.created_by,
            )
            .where(*conditions)
            .order_by(UserModel.created_at.desc())
            .offset((query.page - 1) * query.size)
            .limit(query.size)
        )

        result = await self._session.execute(stmt)

        return [
            self._to_entity(
                row.UserModel,
                row.owner_name,
                row.owner_id,
            )
            for row in result
        ]
    async def search(
        self,
        keyword: str,
    ):

        stmt = (

            select(UserModel)

            .where(

                or_(
                    UserModel.name.ilike(f"%{keyword}%"),
                    UserModel.email.ilike(f"%{keyword}%"),
                )
            )
        )

        result = await self._session.scalars(stmt)

        return [self._to_entity(i) for i in result]
    
    def to_dto(self, user: User) -> UserDto:
        return UserDto(
            id = user.id,
            name = user.name,
            email = user.email,
            mobile = user.mobile,
            role = user.role,
            is_active = user.is_active,
            created_by=user.created_by,
            profile_image=user.profile_image
        )

    def _to_entity(self, model: UserModel, owner_name: str | None = None, owner_id: str | None = None) -> User:
        return User(
            id=model.id,
            name=model.name,
            email=model.email,
            mobile=model.mobile,
            role=model.role,
            is_active=model.is_active,
            created_by=model.created_by,
            is_locked=model.is_locked,
            last_login=model.last_login,
            created_at=model.created_at,
            updated_at=model.updated_at,
            # Soft-delete state round-trips, so an update never revives a deleted user
            is_deleted=model.is_deleted,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
            owner_name=owner_name,
            owner_id=owner_id,
            profile_image=model.profile_url,
            self_brand=bool(model.self_brand),
            brand_logo=model.brand_logo_url,
        )
        