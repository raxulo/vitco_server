from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.modules.common.device_item_version.domain.enums import DeviceType

@dataclass(slots=True, kw_only=True)
class DeviceItemVersion:
    id: UUID
    device_type: DeviceType | int | None
    device_id: UUID
    item_name: str
    version: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
