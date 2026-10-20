from sqlalchemy import update
from sqlalchemy import delete
from app.modules.media.domain.enums import MediaCategory
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from sqlalchemy import select
from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from app.modules.media.infrastructure.models import (
    MediaModel,
)


class MediaRepository:

    def __init__(self, db: DatabaseManager) -> None:

        self.database = db

    @property
    def _session(self) -> AsyncSession:
        return self.database.session

    async def create(
        self,
        media: MediaModel,
    ) -> MediaModel:

        self._session.add(media)

        await self._session.flush()

        return media

    async def get_by_id(
        self,
        media_id: UUID,
    ) -> MediaModel | None:

        result = await self._session.execute(
            select(MediaModel).where(
                MediaModel.id == media_id,
                MediaModel.is_active.is_(True),
            )
        )

        return result.scalar_one_or_none()

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> MediaModel | None:

        result = await self._session.execute(
            select(MediaModel).where(
                MediaModel.uploaded_by == user_id,
                MediaModel.category == MediaCategory.PROFILE,
                MediaModel.is_active.is_(True),
            )
        )

        return result.scalar_one_or_none()

    async def delete(self, media_id: UUID) -> MediaModel | None:

        result = await self._session.execute(
            delete(MediaModel).where(
                MediaModel.id == media_id,
            ).returning(MediaModel)
        )

        return result.scalar_one_or_none()

    async def get_profile_image_by_user_id(self, user_id: UUID) -> MediaModel | None:

        result = await self._session.execute(
            select(MediaModel).where(
                MediaModel.uploaded_by == user_id,
                MediaModel.category == MediaCategory.PROFILE,
                MediaModel.is_active.is_(True),
            ).order_by(
                MediaModel.created_at.desc(),
            ).limit(1)
        )

        return result.scalar_one_or_none()

    async def list_profile_images_by_user_id(self, user_id: UUID) -> list[MediaModel]:
        """Every profile image row a user owns (old uploads included)."""
        result = await self._session.execute(
            select(MediaModel).where(
                MediaModel.uploaded_by == user_id,
                MediaModel.category == MediaCategory.PROFILE,
            )
        )
        return list(result.scalars().all())

    async def get_user_profile_url(self, user_id: UUID) -> str | None:
        """Current profile image URL of a (not deleted) user."""
        result = await self._session.execute(
            select(UserModel.profile_url).where(
                UserModel.id == user_id,
                UserModel.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_key(
        self,
        storage_key: str,
    ) -> MediaModel | None:

        result = await self._session.execute(
            select(MediaModel).where(
                MediaModel.storage_key
                == storage_key,
                MediaModel.is_active.is_(True),
            ).limit(1)
        )

        return result.scalar_one_or_none()

    async def deactivate(
        self,
        media_id: UUID,
    ) -> bool:

        result = await self._session.execute(
            update(MediaModel)
            .where(
                MediaModel.id == media_id,
                MediaModel.is_active.is_(True),
            )
            .values(
                is_active=False,
            )
        )

        return result.rowcount == 1