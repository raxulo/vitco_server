from enum import IntEnum


class CollectionShift(IntEnum):
    MORNING = 0
    EVENING = 1


class MilkType(IntEnum):
    COW = 0
    BUFFALO = 1
    MIXED = 2

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def color(self) -> str:
        return {
            self.COW: "#8277fd",
            self.BUFFALO: "#1d4ed8",
            self.MIXED: "#92400e",
        }[self]

class QuantityCollectionMode(IntEnum):
    MANUAL = 0
    AUTOMATIC = 1


class MeasurementMode(IntEnum):
    MANUAL = 0
    AUTOMATIC = 1


class CollectionStatus(IntEnum):
    UNPAID = 0
    PAID = 1