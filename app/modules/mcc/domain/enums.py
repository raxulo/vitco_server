from enum import IntEnum


class MccType(IntEnum):

    NORMAL     = 0
    FAT_SNF    = 1
    WEIGHT     = 2
    FIXED_RATE = 3

    @property
    def color(self) -> str:
        colors = {
            self.NORMAL: "#3b82f6",
            self.WEIGHT: "#10b981",
            self.FAT_SNF: "#f59e0b",
            self.FIXED_RATE: "#ef4444",
        }
        return colors[self]

    @property
    def label(self) -> str:
        labels = {
            self.NORMAL: "Normal",
            self.WEIGHT: "Weight",
            self.FAT_SNF: "Fat & SNF",
            self.FIXED_RATE: "Fixed Rate",
        }
        return labels[self]

    @property
    def supports_visible_member(self) -> bool:
        """Only these MCCs fill a collection from a sample number and can hide the VLCC's name."""
        return self in (MccType.FAT_SNF, MccType.FIXED_RATE)

    def shows_member_name(self, visible_member: bool) -> bool:
        return visible_member or not self.supports_visible_member

    @property
    def supports_shift_delay(self) -> bool:
        """Only FAT / SNF MCCs have a shift delay; every other type records at the real time (DECISION-029)."""
        return self == MccType.FAT_SNF


class AnalyzerType(IntEnum):
    TYPE_A = 0
    TYPE_B = 1
    TYPE_C = 2
    TYPE_D = 3


class CollectionMode(IntEnum):
    MANUAL = 0
    AUTOMATIC = 1


class ReceiptSize(IntEnum):
    SMALL = 0
    LARGE = 1


class CattleType(IntEnum):
    COW_AND_BUFFALO = 0
    COW_ONLY = 1
    BUFFALO_ONLY = 2


class WeightUnit(IntEnum):
    LITER = 0
    KILOGRAM = 1


class PrinterType(IntEnum):
    NONE = 0
    THERMAL = 1
    DOT_MATRIX = 2
    LASER = 3