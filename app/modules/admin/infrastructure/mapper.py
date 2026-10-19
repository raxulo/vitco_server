from app.modules.auth.domain.entities import User

from .models import UserModel


class UserMapper:

    @staticmethod
    def to_entity(model: UserModel) -> User:

        return User(

            id=model.id,

            email=model.email,

            username=model.username,

            password_hash=model.password_hash,

            is_active=model.is_active,

            is_verified=model.is_verified,

            created_at=model.created_at,

            updated_at=model.updated_at,

        )

    @staticmethod
    def to_model(entity: User) -> UserModel:

        return UserModel(

            id=entity.id,

            email=entity.email,

            username=entity.username,

            password_hash=entity.password_hash,

            is_active=entity.is_active,

            is_verified=entity.is_verified,

            created_at=entity.created_at,

            updated_at=entity.updated_at,

        )

    @staticmethod
    def update_model(
        model: UserModel,
        entity: User,
    ) -> None:

        model.email = entity.email

        model.username = entity.username

        model.password_hash = entity.password_hash

        model.is_active = entity.is_active

        model.is_verified = entity.is_verified

        model.updated_at = entity.updated_at