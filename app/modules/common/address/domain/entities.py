from datetime import datetime
from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class Address:

    id: UUID
    user_id: UUID

    line: str | None
    state: str | None
    city: str | None
    pincode: str | None

    created_at: datetime
    updated_at: datetime | None = None

    @property
    def full_address(self) -> str:
        return f"{self.line}, {self.city}, {self.state}, {self.pincode}"

    @property
    def short_address(self) -> str:
        return f"{self.city}, {self.state}"
    
    @property
    def location_address(self) -> str:
        return f"{self.city}, {self.state}, {self.pincode}"