"""
Auth API Router

Python 3.13+
"""
from __future__ import annotations

from uuid import UUID

from app.modules.media.domain.enums import MediaCategory
from app.modules.media.application.services import MediaService
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.exceptions import HTTPException

from fastapi import APIRouter, Depends, Request

from app.modules.dependencies import GetHandler

_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

router = APIRouter(
    prefix="/media",
    tags=["Media"],
)


def _is_unsafe(part: str) -> bool:
    return "/" in part or "\\" in part or ".." in part


# Declared before "/{category}/{filename}" so "avatar" is not parsed as a category
@router.get("/avatar/{user_id}")
async def get_avatar(
    request: Request,
    user_id: UUID,
):
    """
    Stable avatar URL for a user: redirects to the user's CURRENT profile image.

    The image URL changes on every update (so it can be cached forever); this
    URL never changes, so pages that only know the user id (e.g. the topbar,
    whose login token may hold an old image URL) always show the latest picture.
    """
    service: MediaService = GetHandler.media_service(request)
    profile_url = await service.current_profile_url(user_id)

    # Always re-checked (no-cache): the redirect is tiny, the target image is cached
    headers = {"Cache-Control": "no-cache"}
    if not profile_url:
        return Response(status_code=404, headers=headers)

    return RedirectResponse(url=profile_url, status_code=302, headers=headers)


@router.get("/{category}/{folder}/{filename}")
async def get_image_in_folder(
    request: Request,
    category: MediaCategory,
    folder: str,
    filename: str,
):
    """Files kept in a per-owner folder, e.g. profile/<user_id>/<file>."""
    if _is_unsafe(folder) or _is_unsafe(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )

    return await _serve(request, f"{category.value}/{folder}/{filename}")


@router.get("/{category}/{filename}")
async def get_image(
    request: Request,
    category: MediaCategory,
    filename: str,
):
    if _is_unsafe(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )

    return await _serve(request, f"{category.value}/{filename}")


async def _serve(request: Request, key: str) -> Response:
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

    # A stored file never changes (an update writes a new file name), so the
    # browser / app may cache it for a year and revalidate with the ETag.
    etag = f'"{media.id.hex}"'
    headers = {
        "Cache-Control": _IMMUTABLE_CACHE,
        "ETag": etag,
    }
    if etag in request.headers.get("if-none-match", ""):
        return Response(status_code=304, headers=headers)

    return FileResponse(
        path=path,
        media_type=media.mime_type,
        filename=media.name,
        content_disposition_type="inline",  # display in <img>, never force a download
        headers=headers,
    )
