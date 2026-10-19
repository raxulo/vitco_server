from app.core.database import DatabaseManager
from sqlalchemy import select


from app.modules.admin.infrastructure.models import Admin
from app.modules.admin.domain.enums import AdminRole
from app.modules.admin.domain.repository import IAdminRepository


class AdminRepository(IAdminRepository):

    def __init__(
        self,
        database: DatabaseManager,
    ):

        self._database = database

    @property
    def _session(self):
        return self._database.session

    async def get_by_id(
        self,
        admin_id: int,
    ) -> Admin | None:

        return await self._session.get(
            Admin,
            admin_id,
        )

    async def get_by_email(
        self,
        email: str,
    ) -> Admin | None:

        stmt = (
            select(Admin)
            .where(Admin.email == email)
        )

        return await self._session.scalar(stmt)

    async def exists_super_admin(self) -> bool:

        stmt = (

            select(Admin.id)

            .where(

                Admin.role == AdminRole.SUPER_ADMIN

            )

            .limit(1)

        )

        result = await self._session.scalar(stmt)

        return result is not None

    async def create(
        self,
        admin: Admin,
    ) -> Admin:

        self._session.add(admin)
        await self._session.flush()
        return admin

    async def update(
        self,
        admin: Admin,
    ) -> None:

        self._session.add(admin)

        await self._session.flush()

    async def delete(
        self,
        admin: Admin,
    ) -> None:

        await self._session.delete(admin)

        await self._session.flush()