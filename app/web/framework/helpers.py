from __future__ import annotations
from dataclasses import fields
from typing import Any
from fastapi import Request

class WebHelper:

    __slots__ = ()

    @staticmethod
    def deny_role(request: Request, role, message: str = "Use My Profile to update your own details") -> None:
        """
        Block a role from a full edit page of its own kind (an MCC user editing
        MCCs, a VLCC user editing VLCCs, a farmer editing farmers). Their own
        details are edited through /profile/edit instead.
        """
        from app.core.exceptions.base import ForbiddenException

        user = getattr(request.state, "user", None)
        if user is not None and user.role_type == role:
            raise ForbiddenException(message)

    @staticmethod
    def deny_farmer_vlcc(request: Request, message: str = "Access denied for VLCC Farmer accounts") -> None:
        from app.core.exceptions.base import ForbiddenException
        from app.modules.administration.domain.enums import Role

        user = getattr(request.state, "user", None)
        if user is not None and (getattr(user, "is_farmer_vlcc", False) or user.role_type == Role.VLCC_FARMER):
            raise ForbiddenException(message)

    @staticmethod
    def client_ip(request: Request) -> str:

        forwarded = request.headers.get("X-Forwarded-For")

        if forwarded:
            return forwarded.split(",")[0].strip()

        if request.client:
            return request.client.host

        return ""

    @staticmethod
    def user_agent(request: Request) -> str:
        return request.headers.get(
            "User-Agent",
            "",
        )

    @staticmethod
    def referer(request: Request) -> str:
        return request.headers.get(
            "Referer",
            "",
        )

    @staticmethod
    def host(request: Request) -> str:
        return request.url.hostname or ""

    @staticmethod
    def base_url(request: Request) -> str:
        return str(request.base_url)

    @staticmethod
    def path(request: Request) -> str:
        return request.url.path

    @staticmethod
    def query(request: Request) -> dict[str, Any]:
        return dict(request.query_params)

    @staticmethod
    def is_htmx(request: Request) -> bool:
        return (
            request.headers.get("HX-Request")
            == "true"
        )

    @staticmethod
    def is_api(request: Request) -> bool:
        return request.url.path.startswith("/api")

    @staticmethod
    def is_web(request: Request) -> bool:
        return (
            not WebHelper.is_api(request) or WebHelper.is_htmx(request)
        )

    @staticmethod
    def is_ajax(request: Request) -> bool:
        return (
            request.headers.get(
                "X-Requested-With"
            )
            == "XMLHttpRequest"
        )

    @staticmethod
    def validate(data: Any, schema: Any) -> dict[str, Any]:
        return schema.model_validate(data).model_dump()

    
    @staticmethod
    async def bind_form(request: Request, model) -> Any:
        data = await request.form()
        values = {}
        for field in fields(model):
            values[field.name] = data.get(field.name)
        return model(**values)


from dataclasses import fields, MISSING
from typing import TypeVar, Type, get_type_hints, get_origin, get_args
from uuid import UUID


T = TypeVar("T")


class FormBinder:

    @classmethod
    async def bind(
        cls,
        request,
        form_type: Type[T],
    ) -> T:

        form = await request.form()

        data = {}

        hints = get_type_hints(form_type)

        for field in fields(form_type):

            name = field.name
            value = form.get(name)

            if value is None:

                if field.default is not MISSING:
                    continue

                if field.default_factory is not MISSING:
                    continue

                value = None

            data[name] = cls._convert(
                value,
                hints.get(name),
            )

        return form_type(**data)

    @classmethod
    def _convert(
        cls,
        value,
        annotation,
    ):

        if value is None:
            return None

        if not annotation:
            return value

        origin = get_origin(annotation)

        # Optional[T]
        if origin is type(None):
            return value

        if origin is not None:
            args = get_args(annotation)

            for arg in args:

                if arg is type(None):
                    continue

                try:
                    return cls._convert(
                        value,
                        arg,
                    )
                except (ValueError, TypeError):
                    pass

            return value

        if annotation is str:
            return str(value).strip()

        if annotation is int:
            return int(value)

        if annotation is float:
            return float(value)

        if annotation is bool:
            return str(value).lower() in {
                "1",
                "true",
                "yes",
                "on",
            }

        if annotation is UUID:
            return UUID(str(value))

        return value