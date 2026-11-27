
import asyncio
from collections.abc import Iterable
from io import BytesIO
from uuid import UUID, uuid4

from app.modules.media.infrastructure.file_cleanup import delete_after_commit, delete_on_rollback
from app.modules.media.infrastructure.image_compressor import ImageProcessor, ProcessedImage
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
LISTING_IMAGE_MAX_BYTES = 300 * 1024
LISTING_IMAGE_MAX_SIDE = 1600
BRAND_LOGO_MAX_UPLOAD = 2 * 1024 * 1024
BRAND_LOGO_MAX_BYTES = 150 * 1024
BRAND_LOGO_MAX_SIDE = 512

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
    # Marketplace images: re-encoded like profile images, larger
    # =========================================================

    async def prepare_listing_image(self, file: UploadFile) -> ProcessedImage:
        """
        Validate and re-encode an upload; raises ValueError with a message for the user.

        Runs in a worker thread and before any database write: decoding takes far longer
        than the write-lock budget (DECISION-010) and the server is a single process.
        """
        if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
            raise ValueError("Use a JPG, PNG or WebP image")

        data = await file.read()
        if not data:
            raise ValueError("The image file is empty")
        if len(data) > MAX_IMAGE_SIZE:
            raise ValueError("Image is too large (maximum 5 MB)")

        processor = ImageProcessor(max_bytes=LISTING_IMAGE_MAX_BYTES, max_side=LISTING_IMAGE_MAX_SIDE)
        return await asyncio.to_thread(processor.process, data)

    async def store_listing_image(
        self,
        image: ProcessedImage,
        category: MediaCategory,
        uploaded_by: UUID,
        name: str,
    ) -> MediaModel:
        media_id = uuid4()
        storage_key = f"{category.value}/{media_id.hex}{image.extension}"

        # If the surrounding transaction rolls back, the new file goes with it
        delete_on_rollback(self.repository._session, self.storage, storage_key)
        await self.storage.save(BytesIO(image.data), storage_key)
        return await self.repository.create(
            MediaModel(
                id=media_id,
                name=name,
                media_type=MediaType.IMAGE,
                category=category,
                storage_key=storage_key,
                mime_type=image.mime_type,
                extension=image.extension,
                file_size=len(image.data),
                uploaded_by=uploaded_by,
                is_active=True,
            )
        )

    async def delete_images(self, media_ids: Iterable[UUID]) -> None:
        """Remove the rows now and the files only after the transaction commits."""
        for media_id in media_ids:
            media = await self.repository.delete(media_id)
            if media is not None:
                delete_after_commit(self.repository._session, self.storage, media.storage_key)

    async def delete_image_by_url(self, url: str | None) -> None:
        """Remove an image known only by its public URL; other URLs are left alone."""
        prefix = f"{MediaUrlService.BASE_PATH}/"
        if not url or not url.startswith(prefix):
            return
        media = await self.repository.get_by_key(url.removeprefix(prefix))
        if media is not None:
            await self.delete_images([media.id])

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

    # =========================================================
    # Self Brand logos: one per Admin, kept in brand/<admin_id>/
    # =========================================================

    async def upload_brand_logo(
        self,
        file: UploadFile,
        admin_id: UUID,
        uploaded_by: UUID | None,
    ) -> MediaModel:
        """
        Store an Admin's Self Brand logo; raises ValueError with a message for the user.

        Re-encoded like every upload (WebP, transparency kept, longest side <= 512 px)
        so the browser never receives the bytes exactly as sent.
        """
        if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
            raise ValueError("Logo must be a PNG, JPG or WebP image")

        data = await file.read()
        if not data:
            raise ValueError("The logo file is empty")
        if len(data) > BRAND_LOGO_MAX_UPLOAD:
            raise ValueError("Logo is too large (maximum 2 MB)")

        processor = ImageProcessor(max_bytes=BRAND_LOGO_MAX_BYTES, max_side=BRAND_LOGO_MAX_SIDE)
        image = await asyncio.to_thread(processor.process, data)

        media_id = uuid4()
        storage_key = f"{MediaCategory.BRAND.value}/{admin_id.hex}/{media_id.hex}{image.extension}"

        # If the surrounding transaction rolls back, the new file goes with it
        delete_on_rollback(self.repository._session, self.storage, storage_key)
        await self.storage.save(BytesIO(image.data), storage_key)
        return await self.repository.create(
            MediaModel(
                id=media_id,
                name=(file.filename or media_id.hex),
                media_type=MediaType.IMAGE,
                category=MediaCategory.BRAND,
                storage_key=storage_key,
                mime_type=image.mime_type,
                extension=image.extension,
                file_size=len(image.data),
                uploaded_by=uploaded_by,
                is_active=True,
                entity_id=admin_id,
            )
        )

    async def delete_brand_logos(
        self,
        admin_id: UUID,
        keep_media_id: UUID | None = None,
    ) -> None:
        """Remove an Admin's logo rows now (except `keep_media_id`) and the files after commit."""
        for media in await self.repository.list_brand_logos_by_admin_id(admin_id):
            if media.id == keep_media_id:
                continue
            await self.repository.delete(media.id)
            delete_after_commit(self.repository._session, self.storage, media.storage_key)

