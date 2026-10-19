"""
Password Security Service

Enterprise Authentication Module

Python 3.13+
"""

from __future__ import annotations


from argon2 import PasswordHasher

from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHash,
)



__all__ = (
    "PasswordService",
)



class PasswordService:
    """
    Secure password hashing service.

    Uses Argon2id.
    """


    __slots__ = (
        "_hasher",
    )


    def __init__(self) -> None:


        self._hasher = PasswordHasher(

            time_cost=3,

            memory_cost=65536,

            parallelism=4,

            hash_len=32,

            salt_len=16,

        )


    # ========================================================
    # Hash
    # ========================================================


    def hash(
        self,
        password: str,
    ) -> str:
        """
        Generate password hash.
        """


        return self._hasher.hash(
            password
        )



    # ========================================================
    # Verify
    # ========================================================


    def verify(
        self,
        password_hash: str,
        password: str,
    ) -> bool:
        """
        Verify plain password.

        Returns:

        True  -> valid password
        False -> invalid password
        """


        try:

            return self._hasher.verify(

                password_hash,

                password,

            )


        except (
            VerifyMismatchError,
            VerificationError,
            InvalidHash,
        ):

            return False



    # ========================================================
    # Rehash Check
    # ========================================================


    def needs_rehash(
        self,
        password_hash: str,
    ) -> bool:
        """
        Check if security parameters changed.
        """


        return self._hasher.check_needs_rehash(

            password_hash

        )