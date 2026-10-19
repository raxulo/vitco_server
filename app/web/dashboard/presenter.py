"""
Login Presenter
"""

from app.web.auth.assembler import (
    LoginAssembler,
)


class LoginPresenter:

    __slots__ = ()

    @staticmethod
    def show_login(result):

        return LoginAssembler.create(result.error,result.email)