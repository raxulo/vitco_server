from enum import IntEnum
    

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
    MEDIUM = 1
    LARGE = 2
    EXTRA_LARGE = 3
    

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