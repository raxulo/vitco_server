from fastapi import UploadFile
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field


class LoginRequest(BaseModel):

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class RegisterRequest(BaseModel):

    full_name: str = Field(
        min_length=3,
        max_length=100,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class RefreshTokenRequest(BaseModel):

    refresh_token: str


class ForgotPasswordRequest(BaseModel):

    email: EmailStr


class ResetPasswordRequest(BaseModel):

    token: str

    password: str


class VerifyOTPRequest(BaseModel):

    email: EmailStr

    otp: str


class PartialUpdateUserRequest(BaseModel):
    name: str | None = Field(default=None)
    email: str | None = Field(default=None)
    mobile: str | None = Field(default=None)
    profile_image: UploadFile | None = Field(default=None)