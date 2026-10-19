from enum import IntEnum


class RateChartType(IntEnum):
    FORMULA = 0
    CSV = 1
    PRODATA = 2
    TEXT = 3

    @property
    def label(self) -> str:
        return {
            RateChartType.FORMULA: "Formula",
            RateChartType.CSV: "CSV",
            RateChartType.PRODATA: "Prodata",
            RateChartType.TEXT: "Text",
        }[self]


class MilkType(IntEnum):
    COW = 0
    BUFFALO = 1
    MIXED = 2


class RateCalculationType(IntEnum):
    """
    Defines which milk quality parameters
    participate in rate calculation.
    """

    FAT_AND_SNF = 0
    FAT_ONLY = 1


class RateChartStatus(IntEnum):
    INACTIVE = 0
    ACTIVE = 1
    ARCHIVED = 2