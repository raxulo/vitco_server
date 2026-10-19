from app.modules.admin.repositories.admin_repository import AdminRepository
from app.modules.admin.models import Admin
from app.core.security.password import hash_password


class StartupSeeder:

    @staticmethod
    async def create_default_super_admin(container) -> None:

        repo: AdminRepository = container.resolve(AdminRepository)

        exists = await repo.exists_super_admin()

        if exists:
            return

        admin = Admin(

            name="Super Admin",

            email="admin@example.com",

            password=hash_password("Admin@123"),

            role=0,      # SUPER_ADMIN

            is_active=True,

        )

        await repo.create(admin)