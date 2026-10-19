from dataclasses import dataclass
from typing import Generic
from typing import TypeVar

from .error import Error

T = TypeVar("T")


@dataclass(slots=True)
class Result(Generic[T]):

    success: bool

    data: T | None = None

    error: Error | None = None


    @classmethod
    def ok(
        cls,
        data: T = None
    ):

        return cls(

            success=True,

            data=data

        )


    @classmethod
    def fail(
        cls,
        error: Error
    ):

        return cls(

            success=False,

            error=error

        )