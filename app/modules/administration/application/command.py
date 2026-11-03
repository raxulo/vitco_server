from dataclasses import dataclass
from typing import Any
from fastapi import UploadFile
from fastapi import File
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from pydantic import ConfigDict
from fastapi.openapi.models import EmailStr
from pydantic import BaseModel
from uuid import UUID


class UserData(BaseModel):
    name: str
    email: EmailStr
    mobile: str | None = None
    role: Role
    is_active: bool = True
    password_hash: str | None
    profile_image: Any | None = None

class CreateUserCommand(BaseModel):
    name: str
    email: EmailStr
    mobile: str | None = None
    role: Role
    is_active: bool = True
    password_hash: str | None
    created_by: UUID | None = None
    profile_image: UploadFile | None = None



class UpdateUserCommand(CreateUserCommand):

    id: UUID 

class DeleteUserCommand(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )

    id: UUID
    deleted_by: UUID | None = None


class GetUserQuery(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )

    id: UUID

class ListUsersQuery(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )


    page: int = 1

    size: int = 20

    search: str | None = None

    role: Role | None = None

    is_active: bool | None = None

    owner: CurrentUser | None = None


@dataclass(slots=True, kw_only=True)
class PartialUserUpdateCommand:
    name: str | None = None
    email: str | None = None
    mobile: str | None = None
    profile_image: Any | None = None