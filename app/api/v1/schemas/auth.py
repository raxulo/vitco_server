from app.modules.administration.domain.enums import Role
from pydantic import ConfigDict
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field


class LoginRequest(BaseModel):

    email: str | None = None
    username: str | None = None
    mobile: str | None = None

    password: str = Field(
        min_length=1,
        max_length=128,
    )

    @property
    def identifier(self) -> str:
        return (self.email or self.username or self.mobile or "").strip()



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
    
class TokenResponse(BaseModel):

    access_token: str

    refresh_token: str

    token_type: str


class LoginResponse(BaseModel):

    id: str 

    user_id: str | None

    email: str

    full_name: str

    token: TokenResponse

    is_verified: bool

    role: Role

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )