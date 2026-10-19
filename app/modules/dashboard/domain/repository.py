from abc import ABC, abstractmethod

from app.modules.admin.infrastructure.models import Admin


class IAdminRepository(ABC):

    @abstractmethod
    async def get_by_id(
        self,
        admin_id: int,
    ) -> Admin | None:
        ...

    @abstractmethod
    async def get_by_email(
        self,
        email: str,
    ) -> Admin | None:
        ...

    @abstractmethod
    async def exists_super_admin(self) -> bool:
        ...

    @abstractmethod
    async def create(
        self,
        admin: Admin,
    ) -> Admin:
        ...

    @abstractmethod
    async def update(
        self,
        admin: Admin,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        admin: Admin,
    ) -> None:
        ...