from app.modules.administration.domain.enums import Role

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class User:
    id: UUID
    name: str
    email: str
    mobile: str | None
    role: Role
    is_active: bool
    is_locked: bool
    created_by: UUID | None
    is_deleted: bool = False
    deleted_by: UUID | None = None
    password_hash: str | None = None
    last_login: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    owner_name: str | None = None
    owner_id: UUID | None = None
    profile_image: str | None = None
    own_id: UUID | None = None
    self_brand: bool = False
    brand_logo: str | None = None



@dataclass(slots=True)
class UserDto:
    id: UUID
    name: str
    email: str
    mobile: str | None
    role: Role
    is_active: bool
    created_by: UUID | None
    is_locked: bool = False
    created_at: datetime | None = None
    profile_image: str | None = None


@dataclass(slots=True, frozen=True)
class Brand:
    """
    The Self Brand a user works under: its own when it is an Admin, otherwise
    the Admin above it in the ownership hierarchy.

    `logo_url` is None when Self Brand is off or no logo was uploaded; the web
    then shows the Vitco logo and name. `name` is the Admin's name, shown next
    to its logo in the sidebar.
    """
    enabled: bool = False
    logo_url: str | None = None
    name: str | None = None

    @property
    def logo(self) -> str | None:
        return self.logo_url if self.enabled else None


NO_BRAND = Brand()

