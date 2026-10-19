from app.modules.administration.domain.enums import Role
from uuid import UUID
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class UserCommand:
    id: UUID
    role: Role

