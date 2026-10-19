"""
JWT Security Service

Enterprise Authentication Module

Python 3.13+
"""

from __future__ import annotations


from datetime import (
    datetime,
    timedelta,
    timezone,
)


from typing import Any


from jose import (
    jwt,
    JWTError,
)



__all__ = (
    "JWTService",
)



class JWTService:
    """
    JWT token management service.
    """


    __slots__ = (
        "_secret",
        "_algorithm",
        "_access_expire",
        "_refresh_expire",
    )


    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_minutes: int = 15,
        refresh_days: int = 30,
    ) -> None:


        self._secret = secret_key

        self._algorithm = algorithm

        self._access_expire = timedelta(

            minutes=access_minutes

        )

        self._refresh_expire = timedelta(

            days=refresh_days

        )


    # ========================================================
    # Access Token
    # ========================================================


    def create_access_token(
        self,
        subject: str,
        claims: dict[str, Any] | None = None,
    ) -> str:


        now = datetime.now(
            timezone.utc
        )


        payload = {

            "sub": subject,

            "type": "access",

            "iat": now,

            "exp": now + self._access_expire,

        }


        if claims:

            payload.update(
                claims
            )


        return jwt.encode(

            payload,

            self._secret,

            algorithm=self._algorithm,

        )



    # ========================================================
    # Refresh Token
    # ========================================================


    def create_refresh_token(
        self,
        subject: str,
    ) -> str:


        now = datetime.now(
            timezone.utc
        )


        payload = {

            "sub": subject,

            "type": "refresh",

            "iat": now,

            "exp": now + self._refresh_expire,

        }


        return jwt.encode(

            payload,

            self._secret,

            algorithm=self._algorithm,

        )



    # ========================================================
    # Decode
    # ========================================================


    def decode(
        self,
        token: str,
    ) -> dict[str, Any] | None:


        try:

            return jwt.decode(

                token,

                self._secret,

                algorithms=[
                    self._algorithm
                ],

            )


        except JWTError:

            return None



    # ========================================================
    # Validation
    # ========================================================


    def verify_type(
        self,
        payload: dict[str, Any],
        token_type: str,
    ) -> bool:


        return (
            payload.get("type")
            ==
            token_type
        )