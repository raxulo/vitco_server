"""
Push notification devices for the mobile app (REQ-76, DECISION-033)

One place for every module's pushes: the app registers its Firebase token here after login (and
whenever Firebase gives it a new one) and removes it on logout. Every push then carries `source`,
`type` and `reference_id` in its data so the app can open the right screen.

Python 3.13+
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.notification.application.handler import RegisterDeviceCommand

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class RegisterDeviceRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"fcm_token": "dQw4w9WgXcQ:APA91bH...", "platform": "android", "app_version": "2.4.1"}}
    )

    fcm_token: str = Field(min_length=20, max_length=512)
    platform: str = Field(pattern="^(android|ios)$")
    app_version: str | None = Field(default=None, max_length=30)


def _user(request: Request) -> CurrentUser:
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def _record(data: dict, message: str) -> JSONResponse:
    return JSONResponse(content={"status": True, "code": 200, "message": message, "data": data})


@router.post("/devices", summary="Register this phone for push notifications")
async def register_device(request: Request, body: RegisterDeviceRequest) -> JSONResponse:
    """Idempotent: the same token again only refreshes it; a token used by another login moves to this user."""
    device = await GetHandler.device_handler(request).register(
        RegisterDeviceCommand(fcm_token=body.fcm_token, platform=body.platform, app_version=body.app_version),
        _user(request),
    )
    return _record(
        {"platform": device.platform, "app_version": device.app_version, "is_active": device.is_active},
        "Device registered",
    )


@router.delete("/devices/{fcm_token}", summary="Stop push notifications to this phone (call on logout)")
async def remove_device(request: Request, fcm_token: str) -> JSONResponse:
    removed = await GetHandler.device_handler(request).remove(fcm_token, _user(request))
    return _record({"removed": removed}, "Device removed" if removed else "Device was not registered")
