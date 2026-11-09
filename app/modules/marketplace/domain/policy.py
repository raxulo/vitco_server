"""
Who may sell on the marketplace (DECISION-016).

This is the only list of selling roles. Adding Role.ADMIN and Role.SUB_ADMIN here is
what lets them sell later; repository scope already limits them to their own listings.

Python 3.13+
"""

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.exceptions import SellingNotAllowedException


class SellerPolicy:

    __slots__ = ()

    SELLER_ROLES: frozenset[Role] = frozenset({Role.SUPER_ADMIN})

    @classmethod
    def can_sell(cls, role: Role) -> bool:
        return role in cls.SELLER_ROLES

    @classmethod
    def ensure_can_sell(cls, role: Role) -> None:
        if not cls.can_sell(role):
            raise SellingNotAllowedException()
