"""
Auth API Router

Python 3.13+
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.modules.administration.domain.enums import Role
from app.modules.dependencies import GetHandler
from app.api.v1.schemas.auth import LoginRequest, LoginResponse, TokenResponse
from app.modules.auth.application.command import LoginCommand
from app.middleware.authentication import CurrentUser
from app.modules.notification.application.handler import RegisterDeviceCommand

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Management accounts use the web panel only; the API (devices / mobile app) is for MCC, VLCC and farmers
API_BLOCKED_ROLES = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.SUPPORT})


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    result = await GetHandler.login_handler(request).execute(
        command=LoginCommand(
            email=body.identifier,
            password=body.password,
        ),
    )

    if Role(int(result.role)) in API_BLOCKED_ROLES:
        raise HTTPException(status_code=401, detail="Unauthorized")

    push_registered = await _register_push_device(request, body, result)

    return LoginResponse(
        id=str(result.id),
        user_id=str(result.user_id),
        email=result.email,
        full_name=result.full_name,
        is_verified=True,
        role=result.role,
        token=TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
        ),
        push_registered=push_registered,
    )


async def _register_push_device(request: Request, body: LoginRequest, result) -> bool:
    """Register the phone's Firebase token sent with the login. Never fails the login."""
    if not body.fcm_token:
        return False
    try:
        await GetHandler.device_handler(request).register(
            RegisterDeviceCommand(
                fcm_token=body.fcm_token, platform=body.platform or "android", app_version=body.app_version,
            ),
            CurrentUser(id=UUID(str(result.user_id)), role=str(result.role)),
        )
        return True
    except Exception as exc:
        # A wrong or missing token only means no push for now; the app can send it again later
        logger.info("Login succeeded but the push device was not registered: %s", type(exc).__name__)
        return False