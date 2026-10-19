from app.modules.common.address.application.dto import AddressDto

from app.modules.common.address.domain.entities import Address
from app.modules.common.address.infrastructure.models import AddressModel


class AddressMapper:

    __slots__ = ()

    @staticmethod
    def to_model(
        entity: Address,
    ) -> AddressModel:

        return AddressModel(
            id=entity.id,
            user_id=entity.user_id,

            line=entity.line,
            state=entity.state,
            city=entity.city,
            pincode=entity.pincode,

            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_entity(
        model: AddressModel,
    ) -> Address:

        return Address(
            id=model.id,
            user_id=model.user_id,

            line=model.line,
            state=model.state,
            city=model.city,
            pincode=model.pincode,

            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_dto(
        entity: Address,
    ) -> AddressDto:


        return AddressDto(
            id=entity.id,
            user_id=entity.user_id,

            line=entity.line,
            state=entity.state,
            city=entity.city,
            pincode=entity.pincode,
        )
