from enum import StrEnum


class AdminRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    SUB_ADMIN = "SUB_ADMIN"