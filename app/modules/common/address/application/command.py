from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class AddressData:
    line: str | None = None
    state: str | None = None
    city: str | None = None
    pincode: str | None = None

@dataclass(slots=True, kw_only=True)
class CreateAddressCommand(AddressData):
    pass


@dataclass(slots=True, kw_only=True)
class UpdateAddressCommand(AddressData):

    id: UUID


@dataclass(slots=True, frozen=True)
class GetAddressQuery:

    id: UUID