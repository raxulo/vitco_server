from app.modules.administration.domain.entities import UserDto
from app.modules.administration.domain.entities import User

from .models import UserModel


class UserMapper:

    @staticmethod
    def to_entity(
        model: UserModel,
    ) -> User:

        return User(
            id=model.id,
            name=model.name,
            email=model.email,
            mobile=model.mobile,

            password_hash=model.password_hash,

            role=model.role,

            is_active=model.is_active,

            is_locked=model.is_locked,

            last_login=model.last_login,

            created_at=model.created_at,

            updated_at=model.updated_at,

            created_by=model.created_by,
            profile_image=model.profile_url,
            own_id=getattr(model, "own_id", None),
        )

    @staticmethod
    def to_model(
        entity: User,
    ) -> UserModel:

        return UserModel(
            id=entity.id,
            name=entity.name,
            email=entity.email,
            mobile=entity.mobile,
            password_hash=entity.password_hash,
            role=entity.role,
            is_active=entity.is_active,
            is_locked=entity.is_locked,
            last_login=entity.last_login,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            created_by=entity.created_by,
            profile_url=entity.profile_image,
        )

    @staticmethod
    def model_to_dto(
        model: UserModel,
    ) -> UserDto:

        return UserDto(
            id=model.id,
            name=model.name,
            email=model.email,
            mobile=model.mobile,
            role=model.role,
            is_active=model.is_active,
            created_by=model.created_by,
            profile_image=model.profile_url,
            is_locked=model.is_locked,
            created_at=model.created_at,
        )

    @staticmethod
    def entity_to_dto(
        entity: User,
    ) -> UserDto:

        return UserDto(
            id=entity.id,
            name=entity.name,
            email=entity.email,
            mobile=entity.mobile,
            role=entity.role,
            is_active=entity.is_active,
            created_by=entity.created_by,
            profile_image=entity.profile_image,
            is_locked=entity.is_locked,
            created_at=entity.created_at,
        )