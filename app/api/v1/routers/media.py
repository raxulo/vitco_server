"""
Auth API Router

Python 3.13+
"""
from __future__ import annotations

from app.modules.media.domain.enums import MediaCategory
from app.modules.media.application.services import MediaService
from fastapi.responses import FileResponse
from fastapi.exceptions import HTTPException

from fastapi import APIRouter, Depends, Request

from app.modules.dependencies import GetHandler

router = APIRouter(
    prefix="/media",
    tags=["Media"],
)


@router.get("/{category}/{filename}")
async def get_image(
    request: Request,
    category: MediaCategory,
    filename: str,
):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )

    key = f"{category.value}/{filename}"

    service: MediaService = GetHandler.media_service(request)
    media = await service.repository.get_by_key(key)

    if not media:
        raise HTTPException(
            status_code=404,
            detail="Media not found",
        )

    path = service.storage.get_path(
        media.storage_key
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return FileResponse(
        path=path,
        media_type=media.mime_type,
        filename=media.name,
    )