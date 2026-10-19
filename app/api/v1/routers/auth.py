"""
Auth API Router

Python 3.13+
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.modules.dependencies import GetHandler
from app.api.v1.schemas.auth import LoginRequest, LoginResponse, TokenResponse
from app.modules.auth.application.command import LoginCommand

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    result = await GetHandler.login_handler(request).execute(
        command=LoginCommand(
            email=body.identifier,
            password=body.password,
        ),
    )

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
    )