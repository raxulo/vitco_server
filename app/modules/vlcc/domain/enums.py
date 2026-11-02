from enum import IntEnum, StrEnum


class CollectionMode(IntEnum):

    MANUAL = 0
    AUTOMATIC = 1


class VlccType(IntEnum):

    NORMAL = 0
    VLCC_FARMER_TYPE = 1

    @property
    def label(self) -> str:
        match self:
            case VlccType.NORMAL:
                return "Normal"
            case VlccType.VLCC_FARMER_TYPE:
                return "VLCC Farmer Type"

    @property
    def color(self) -> str:
        match self:
            case VlccType.NORMAL:
                return "#3b82f6"
            case VlccType.VLCC_FARMER_TYPE:
                return "#10b981"
