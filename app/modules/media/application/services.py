
from sqlalchemy import UUID
from app.modules.media.infrastructure.media_repository import MediaRepository

from uuid import uuid4

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


    async def delete_profile_image(self, user_id: UUID) -> bool:

        media = await self.repository.get_profile_image_by_user_id(user_id)
        if not media:
            return False

        result = await self.repository.delete(media.id)
        if result:
            await self.storage.delete(media.storage_key)

        return result
        