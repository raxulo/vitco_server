from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True, slots=True, kw_only=True)
class DeviceItemVersionInput:
    item_name: str
    version: str

@dataclass(frozen=True, slots=True, kw_only=True)
class BulkCreateDeviceItemVersionsCommand:
    device_type: int
    device_id: UUID
    items: list[DeviceItemVersionInput]

@dataclass(frozen=True, slots=True, kw_only=True)
class DeviceItemVersionUpdateInput:
    id: UUID
    item_name: str | None = None
    version: str | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class BulkUpdateDeviceItemVersionsCommand:
    updates: list[DeviceItemVersionUpdateInput]

@dataclass(frozen=True, slots=True, kw_only=True)
class BulkDeleteDeviceItemVersionsCommand:
    ids: list[UUID]
