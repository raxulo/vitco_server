"""
Login ViewModel Assembler
"""

from app.web.auth.models import (
    LoginViewModel,
)


class LoginAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        error: str | None = None,
        email: str = "",
    ) -> LoginViewModel:

        return LoginViewModel(

            title="Login",

            error=error,

            email=email,

        )