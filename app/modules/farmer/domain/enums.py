from enum import IntEnum


class MilkType(IntEnum):

    COW = 0
    BUFFALO = 1
    MIXED = 2

    @property
    def color(self) -> str:
        return {
            self.COW: "#22c55e",
            self.BUFFALO: "#eab308",
            self.MIXED: "#ef4444",
        }[self]

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

class FarmerType(IntEnum):

    NORMAL = 0
    VIP = 1