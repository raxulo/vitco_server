"""
Ownership hierarchy shared by every MCC / VLCC / farmer / collection scope.

    Super Admin -> everything
    Admin       -> itself + its Sub Admins ("managers")
                   MCCs created by a manager
                   VLCCs created by a manager or by the user of one of those MCCs
    Sub Admin   -> the same, with itself as the only manager
    MCC         -> VLCCs its user created
    VLCC        -> its own VLCC

Farmers and collections follow the VLCCs / MCCs above. Seeing a record and
modifying it use the same rules.

User-owned records (rate charts) use the user lines instead:
`controlled_users` (the user and everyone below) may modify, and
`ancestor_users` (everyone above) adds read-only visibility.

Every helper returns a SELECT of ids meant for `.in_(...)`, or None for
Super Admin (no restriction).
"""

from sqlalchemy import Select, false, literal, or_, select, true, union

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.vlcc.infrastructure.models import VlccModel

_MANAGER_ROLES = (Role.ADMIN, Role.SUB_ADMIN)


class Hierarchy:

    __slots__ = ()

    @staticmethod
    def managers(owner: CurrentUser) -> Select:
        """Users whose MCCs/VLCCs the owner controls: itself, plus an Admin's Sub Admins."""
        if owner.role_type == Role.ADMIN:
            return select(UserModel.id).where(
                or_(
                    UserModel.id == owner.id,
                    (UserModel.created_by == owner.id) & (UserModel.role == Role.SUB_ADMIN),
                )
            )
        return select(literal(owner.id))

    @classmethod
    def mcc_ids(cls, owner: CurrentUser) -> Select | None:
        role = owner.role_type
        if role == Role.SUPER_ADMIN:
            return None
        if role in _MANAGER_ROLES:
            return select(MccModel.id).where(MccModel.created_by.in_(cls.managers(owner)))
        if role == Role.MCC:
            return select(MccModel.id).where(MccModel.user_id == owner.id)
        return select(MccModel.id).where(literal(False))

    @classmethod
    def vlcc_creators(cls, owner: CurrentUser) -> Select | None:
        """Users whose created VLCCs the owner controls."""
        role = owner.role_type
        if role == Role.SUPER_ADMIN:
            return None
        if role in _MANAGER_ROLES:
            managers = cls.managers(owner)
            mcc_users = select(MccModel.user_id).where(MccModel.created_by.in_(managers))
            return union(managers, mcc_users)
        if role == Role.MCC:
            return select(literal(owner.id))
        return select(UserModel.id).where(literal(False))

    @classmethod
    def vlcc_ids(cls, owner: CurrentUser) -> Select | None:
        role = owner.role_type
        if role == Role.SUPER_ADMIN:
            return None
        if role == Role.VLCC:
            return select(VlccModel.id).where(VlccModel.user_id == owner.id)
        if role in (*_MANAGER_ROLES, Role.MCC):
            return select(VlccModel.id).where(VlccModel.created_by.in_(cls.vlcc_creators(owner)))
        return select(VlccModel.id).where(literal(False))

    # =========================================================
    # User lines (for records owned by users, e.g. rate charts)
    # =========================================================

    @classmethod
    def controlled_users(cls, owner: CurrentUser) -> Select | None:
        """The owner and every user below it: Sub Admins, MCC users, VLCC users."""
        role = owner.role_type
        if role == Role.SUPER_ADMIN:
            return None
        if role in (*_MANAGER_ROLES, Role.MCC):
            mcc_users = select(MccModel.user_id).where(MccModel.id.in_(cls.mcc_ids(owner)))
            vlcc_users = select(VlccModel.user_id).where(VlccModel.id.in_(cls.vlcc_ids(owner)))
            base = cls.managers(owner) if role in _MANAGER_ROLES else select(literal(owner.id))
            return union(base, mcc_users, vlcc_users)
        return select(literal(owner.id))

    # =========================================================
    # Shared masters (rate charts, route codes, units, items)
    # =========================================================

    @classmethod
    def shared_visible(cls, owner: CurrentUser, created_by):
        """
        View / use a user-created master record: Super Admin records are
        visible to everyone; others to their creator, everyone below it and
        everyone above it. Another Admin's tree never sees them.
        """
        if owner.role_type == Role.SUPER_ADMIN:
            return true()
        conditions = [
            created_by.in_(select(UserModel.id).where(UserModel.role == Role.SUPER_ADMIN)),
            created_by.in_(cls.ancestor_users(owner)),
        ]
        below = cls.controlled_users(owner)
        if below is not None:
            conditions.append(created_by.in_(below))
        return or_(*conditions)

    @classmethod
    def shared_modifiable(cls, owner: CurrentUser | None, created_by):
        """Modify / delete a user-created master record: its creator and everyone above it."""
        if owner is None or owner.role_type == Role.FARMER:
            return false()
        below = cls.controlled_users(owner)
        return true() if below is None else created_by.in_(below)

    @classmethod
    def farmer_users(cls, owner: CurrentUser) -> Select | None:
        """Login users of the farmers in the VLCCs the owner controls."""
        if owner.role_type == Role.FARMER:
            return select(literal(owner.id))
        vlcc_ids = cls.vlcc_ids(owner)
        if vlcc_ids is None:
            return None
        return select(FarmerModel.user_id).where(FarmerModel.vlcc_id.in_(vlcc_ids))

    @staticmethod
    def ancestor_users(owner: CurrentUser) -> Select:
        """Users above the owner: whoever created its VLCC / MCC, and a Sub Admin's Admin."""
        role = owner.role_type

        # Direct parents of the owner
        if role == Role.FARMER:
            vlcc_filter = VlccModel.id.in_(
                select(FarmerModel.vlcc_id).where(FarmerModel.user_id == owner.id)
            )
            # The farmer's VLCC user and whoever created that VLCC
            direct = [
                select(VlccModel.user_id).where(vlcc_filter),
                select(VlccModel.created_by).where(vlcc_filter),
            ]
        elif role == Role.VLCC:
            direct = [select(VlccModel.created_by).where(VlccModel.user_id == owner.id)]
        elif role == Role.MCC:
            direct = [select(MccModel.created_by).where(MccModel.user_id == owner.id)]
        elif role == Role.SUB_ADMIN:
            direct = [select(UserModel.created_by).where(UserModel.id == owner.id)]
        else:
            return select(UserModel.id).where(literal(False))

        direct_ids = union(*direct) if len(direct) > 1 else direct[0]
        # A VLCC may have been created by an MCC user -> whoever created that MCC
        via_mcc = select(MccModel.created_by).where(MccModel.user_id.in_(direct_ids))
        # Sub Admins in the line -> the Admin above them
        admins = select(UserModel.created_by).where(
            UserModel.id.in_(union(*direct, via_mcc)),
            UserModel.role == Role.SUB_ADMIN,
        )
        return union(*direct, via_mcc, admins)
