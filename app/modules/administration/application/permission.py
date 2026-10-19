from app.modules.administration.domain.enums import Role
from app.modules.administration.domain.enums import ROLE_PERMISSIONS
class PermissionService:

    @staticmethod
    def has_permission(

        role,

        permission,

    ):

        permissions = ROLE_PERMISSIONS.get(
            role,
            set(),
        )

        return (

            "*" in permissions

            or permission in permissions

        )


class UserPermissions:

    def __init__(self, role: Role):
        self.role = role

    @property
    def can_manage_mcc(self) -> bool:
        return self.role in {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.SUB_ADMIN,
        }

    @property
    def can_manage_ratecharts(self) -> bool:
        return self.role in {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.SUB_ADMIN,
        }

    @property
    def can_view_vlcc_reports(self) -> bool:
        return self.role in {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.SUB_ADMIN,
            Role.VLCC,
        }

    @property
    def can_view_mcc_reports(self) -> bool:
        return self.role in {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.SUB_ADMIN,
            Role.MCC,
        }