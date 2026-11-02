from enum import IntEnum
from enum import StrEnum


class Role(IntEnum):

    SUPER_ADMIN = 1
    ADMIN = 2
    SUB_ADMIN = 3
    MCC = 4
    VLCC = 5
    FARMER = 6
    VLCC_FARMER = 7


class Permission(StrEnum):

    USER_CREATE = "user.create"

    USER_UPDATE = "user.update"

    USER_DELETE = "user.delete"

    USER_VIEW = "user.view"

    VLCC_CREATE = "vlcc.create"

    VLCC_UPDATE = "vlcc.update"

    VLCC_DELETE = "vlcc.delete"

    VLCC_VIEW = "vlcc.view"

    MCC_CREATE = "mcc.create"

    MCC_UPDATE = "mcc.update"

    MCC_DELETE = "mcc.delete"

    MCC_VIEW = "mcc.view"

    FARMER_CREATE = "farmer.create"

    FARMER_UPDATE = "farmer.update"

    FARMER_DELETE = "farmer.delete"

    FARMER_VIEW = "farmer.view"



ROLE_PERMISSIONS = {

    Role.SUPER_ADMIN: {

        "*",

    },

    Role.ADMIN: {

        Permission.USER_VIEW,

        Permission.USER_CREATE,

        Permission.USER_UPDATE,

        Permission.VLCC_VIEW,

        Permission.VLCC_CREATE,

        Permission.MCC_VIEW,

    },

    Role.SUB_ADMIN: {

        Permission.USER_VIEW,

        Permission.VLCC_VIEW,

    },

    Role.VLCC: {

        Permission.FARMER_VIEW,

        Permission.FARMER_CREATE,

    },

    Role.MCC: {

        Permission.FARMER_VIEW,

    },

    Role.FARMER: set(),

    Role.VLCC_FARMER: set(),

}