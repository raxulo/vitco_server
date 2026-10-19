from app.modules.administration.domain.entities import User
from app.modules.common.address.domain.entities import Address
from app.modules.common.bank.domain.entities import BankAccount
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class CreatedProfile:
    user: User
    address: Address | None
    bank_account: BankAccount | None

    @staticmethod
    def of(
        user: User,
        address: Address | None,
        bank_account: BankAccount | None,
    ) -> CreatedProfile:
        return CreatedProfile(
            user=user,
            address=address,
            bank_account=bank_account,
        )