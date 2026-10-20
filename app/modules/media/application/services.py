
from io import BytesIO
from uuid import UUID, uuid4

from app.modules.media.infrastructure.file_cleanup import delete_after_commit, delete_on_rollback
from app.modules.media.infrastructure.image_compressor import ImageProcessor
from app.modules.media.infrastructure.media_repository import MediaRepository

from fastapi import UploadFile

from app.modules.media.domain.enums import (
    MediaCategory,
    MediaType,
)
from app.modules.media.infrastructure.models import (
    MediaModel,
)


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024

class MediaUrlService:

    BASE_PATH = "/api/v1/media"

    @classmethod
    def build(
        cls,
        storage_key: str | None,
    ) -> str | None:

        if not storage_key:
            return None

        return (
            f"{cls.BASE_PATH}/"
            f"{storage_key}"
        )


class MediaService:

    def __init__(
        self,
        repository: MediaRepository,
        storage,
    ) -> None:

        self.repository = repository
        self.storage = storage

    async def upload_image(
        self,
        file: UploadFile,
        category: MediaCategory,
        uploaded_by=None,
        entity_id=None
    ) -> MediaModel:

        content_type = ( file.content_type or "" ).lower() 
        extension = ALLOWED_IMAGE_TYPES.get( content_type ) 
        if extension is None: 
            raise ValueError( "Unsupported image type" ) 

        media_id = uuid4() 
        storage_key = ( f"{category.value}/{media_id.hex}{extension}" ) 

        try:
            file_size = await self.storage.save( file.file, storage_key)

            media = MediaModel(
                id=media_id,
                name=( file.filename or media_id.hex ),
                media_type=MediaType.IMAGE,
                category=category,
                storage_key=storage_key,
                mime_type=content_type,
                extension=extension,
                file_size=file_size,
                uploaded_by=uploaded_by,
                is_active=True,
                entity_id=entity_id,
            )
            return await self.repository.create( media ) 
        except Exception: 
            try: 
                await self.storage.delete( storage_key ) 
            except Exception: 
                pass 
            raise

        return await self.repository.create(media)

    async def get_by_path(
        self,
        category: MediaCategory,
        filename: str,
    ) -> MediaModel | None:

        if (
            "/" in filename
            or "\\" in filename
            or ".." in filename
        ):
            return None

        storage_key = (
            f"{category.value}/"
            f"{filename}"
        )

        return await self.repository.get_by_storage_key(
            storage_key
        )


    # =========================================================
    # Profile images: one per user, kept in profile/<user_id>/
    # =========================================================

    async def upload_profile_image(
        self,
        file: UploadFile,
        user_id: UUID,
    ) -> MediaModel:
        """
        Store a user's profile image in its own folder (profile/<user_id>/).

        The upload is always re-encoded to a single WebP image of at most
        100 KB (EXIF/GPS stripped).
        """
        content_type = (file.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise ValueError("Unsupported image type")

        data = await file.read()
        if not data:
            raise ValueError("Empty image file")
        if len(data) > MAX_IMAGE_SIZE:
            raise ValueError("Image is too large (maximum 5 MB)")

        image = ImageProcessor().process(data)

        media_id = uuid4()
        storage_key = f"{MediaCategory.PROFILE.value}/{user_id.hex}/{media_id.hex}{image.extension}"

        # If the surrounding transaction rolls back, the new file goes with it
        delete_on_rollback(self.repository._session, self.storage, storage_key)
        try:
            await self.storage.save(BytesIO(image.data), storage_key)
            media = MediaModel(
                id=media_id,
                name=(file.filename or media_id.hex),
                media_type=MediaType.IMAGE,
                category=MediaCategory.PROFILE,
                storage_key=storage_key,
                mime_type=image.mime_type,
                extension=image.extension,
                file_size=len(image.data),
                uploaded_by=user_id,
                is_active=True,
                entity_id=user_id,
            )
            return await self.repository.create(media)
        except Exception:
            try:
                self.storage.remove(storage_key)
            except Exception:
                pass
            raise

    async def current_profile_url(self, user_id: UUID) -> str | None:
        """The user's latest profile image URL (None when they have none or are deleted)."""
        return await self.repository.get_user_profile_url(user_id)

    async def delete_profile_image(
        self,
        user_id: UUID,
        keep_media_id: UUID | None = None,
    ) -> int:
        """
        Delete a user's profile image rows (except `keep_media_id`); returns how many.

        The files themselves are removed only after the transaction commits, so a
        rolled-back update / delete never leaves a row pointing at a missing file.
        """
        deleted = 0
        for media in await self.repository.list_profile_images_by_user_id(user_id):
            if media.id == keep_media_id:
                continue
            await self.repository.delete(media.id)
            delete_after_commit(self.repository._session, self.storage, media.storage_key)
            deleted += 1
        return deleted
