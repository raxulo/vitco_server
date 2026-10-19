from app.modules.common.bank.domain.dto import BankAccountDto
from app.modules.common.bank.domain.entities import (
    BankAccount,
)
from app.modules.common.bank.infrastructure.models import (
    BankAccountModel,
)


class BankAccountMapper:

    __slots__ = ()

    @staticmethod
    def to_model(
        entity: BankAccount,
    ) -> BankAccountModel:

        return BankAccountModel(
            id=entity.id,
            user_id=entity.user_id,

            account_holder=entity.account_holder,
            bank_name=entity.bank_name,
            account_number=entity.account_number,
            ifsc_code=entity.ifsc_code,
            upi_id=entity.upi_id,

            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_entity(
        model: BankAccountModel,
    ) -> BankAccount:

        return BankAccount(
            id=model.id,
            user_id=model.user_id,

            account_holder=model.account_holder,
            bank_name=model.bank_name,
            account_number=model.account_number,
            ifsc_code=model.ifsc_code,
            upi_id=model.upi_id,

            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_dto(
        entity: BankAccount,
    ) -> BankAccountDto:

        return BankAccountDto(
            id=entity.id,
            user_id=entity.user_id,

            account_holder=entity.account_holder,
            bank_name=entity.bank_name,
            account_number=entity.account_number,
            ifsc_code=entity.ifsc_code,
            upi_id=entity.upi_id,
        )