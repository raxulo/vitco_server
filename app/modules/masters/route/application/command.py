from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
from app.middleware.authentication import CurrentUser


@dataclass(slots=True)
class CreateRouteMasterCommand:

    route_code: int
    route_name: str
    created_by: UUID | None = None


@dataclass(slots=True)
class UpdateRouteMasterCommand:

    id: UUID
    route_code: int
    route_name: str
    is_active: bool
    owner: CurrentUser | None = None


@dataclass(slots=True)
class DeleteRouteMasterCommand:

    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class GetRouteMasterQuery:

    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class ListRouteMasterQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None
    owner: CurrentUser | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
