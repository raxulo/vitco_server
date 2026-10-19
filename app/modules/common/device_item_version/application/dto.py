from dataclasses import dataclass
from uuid import UUID
from datetime import datetime

@dataclass(frozen=True, slots=True)
class DeviceItemVersionDTO:
    id: UUID
    device_type: int
    device_id: UUID
    item_name: str
    version: str
    created_at: datetime | None
    updated_at: datetime | None
