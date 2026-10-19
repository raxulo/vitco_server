from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, frozen=True)
class AddressDto:

    id: UUID
    user_id: UUID

    line: str | None
    state: str | None
    city: str | None
    pincode: str | None

@dataclass(slots=True, frozen=True)
class AddressInfoDto:
    line: str | None
    state: str | None
    city: str | None
    pincode: str | None