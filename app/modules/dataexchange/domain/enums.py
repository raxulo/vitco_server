"""
Data Exchange Domain Enums

Kinds and lifecycle states of Excel import / export jobs.

Python 3.13+
"""

from enum import IntEnum


class ExcelJobKind(IntEnum):

    FARMER_EXPORT = 1
    FARMER_IMPORT = 2
    VLCC_EXPORT = 3
    VLCC_IMPORT = 4
    PRODATA_EXPORT = 5
    PRODATA_IMPORT = 6

    @property
    def is_import(self) -> bool:
        return self in (
            ExcelJobKind.FARMER_IMPORT,
            ExcelJobKind.VLCC_IMPORT,
            ExcelJobKind.PRODATA_IMPORT,
        )


class ExcelJobStatus(IntEnum):

    QUEUED = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4

    @property
    def is_active(self) -> bool:
        return self in (ExcelJobStatus.QUEUED, ExcelJobStatus.RUNNING)

    @property
    def is_finished(self) -> bool:
        return not self.is_active


class ImportMode(IntEnum):

    UPSERT = 0          # existing code -> update, new code -> insert
    CREATE_ONLY = 1     # existing code -> discarded with a reason
