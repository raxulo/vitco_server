"""
Recycle Bin — entity kinds that can be soft-deleted and purged.

Python 3.13+
"""

from enum import StrEnum


class DeletedEntityType(StrEnum):
    """URL-safe keys of the recycle bin tabs."""

    ADMIN = "admin"
    SUB_ADMIN = "sub-admin"
    MCC = "mcc"
    VLCC = "vlcc"
    FARMER = "farmer"

    @property
    def label(self) -> str:
        return {
            DeletedEntityType.ADMIN: "Admins",
            DeletedEntityType.SUB_ADMIN: "Sub Admins",
            DeletedEntityType.MCC: "MCCs",
            DeletedEntityType.VLCC: "VLCCs",
            DeletedEntityType.FARMER: "Farmers",
        }[self]
