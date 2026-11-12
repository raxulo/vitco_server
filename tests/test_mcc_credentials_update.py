"""
MCC edit and login: a new password or email works for login straight away, and a
blank password field keeps the current password.

Python 3.13+
"""

from uuid import UUID, uuid4

import pytest

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.mcc.application.handler import MccHandler
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.mcc.presentation.requests import UpdateMccRequest
from app.web.mcc.assembler import MccAssembler
from tests.dataexchange.factories import create_user, unique_mobile

LOGIN = "/api/v1/auth/login"
OLD_PASSWORD = "Old@123"


async def _mcc(database, admin: UUID) -> tuple[UUID, str, str, str]:
    """An MCC whose user has a real password hash; returns its id, code, email and mobile."""
    user_id = await create_user(database, role=Role.MCC, created_by=admin, name="Cred MCC")
    email, mobile = f"mcc-{user_id.hex[:8]}@gmail.com", unique_mobile()
    mcc_id, code = uuid4(), str(uuid4().int)[:6]
    async with database.transaction() as session:
        user = await session.get(UserModel, user_id)
        user.email, user.mobile = email, mobile
        user.password_hash = PasswordService().hash(OLD_PASSWORD)
        session.add(MccModel(
            id=mcc_id, user_id=user_id, code=code, name="Cred MCC",
            mcc_type=MccType.NORMAL, created_by=admin,
        ))
    return mcc_id, code, email, mobile


async def _edit(admin: UUID, mcc_id: UUID, code: str, *, email: str, mobile: str, password: str | None) -> None:
    """Edit through the same request model, assembler and handler as the web form."""
    from app.main import app

    form = UpdateMccRequest.model_validate({
        "code": code, "name": "Cred MCC", "mobile": mobile, "email": email, "password": password,
    })
    handler = app.state.application.container.resolve(MccHandler)
    owner = CurrentUser(id=admin, role=str(Role.ADMIN.value))
    # A web request runs inside the request's database session; this stands in for it
    async with app.state.application.container.database.transaction():
        await handler.full_update(MccAssembler.update(form, mcc_id, admin), owner=owner)


async def _login(api, email: str, password: str) -> int:
    return (await api.post(LOGIN, json={"email": email, "password": password})).status_code


@pytest.fixture
async def mcc(api, database):
    admin = await create_user(database, role=Role.ADMIN)
    return admin, *await _mcc(database, admin)


async def test_new_password_logs_in(api, mcc):
    admin, mcc_id, code, email, mobile = mcc
    await _edit(admin, mcc_id, code, email=email, mobile=mobile, password="New@456")

    assert await _login(api, email, "New@456") == 200
    assert await _login(api, email, OLD_PASSWORD) != 200


@pytest.mark.parametrize("blank", [None, "", "   "])
async def test_blank_password_keeps_the_current_one(api, mcc, blank):
    admin, mcc_id, code, email, mobile = mcc
    await _edit(admin, mcc_id, code, email=email, mobile=mobile, password=blank)

    assert await _login(api, email, OLD_PASSWORD) == 200


async def test_new_email_logs_in_with_any_case(api, mcc):
    admin, mcc_id, code, _, mobile = mcc
    new_email = f"Changed-{uuid4().hex[:8]}@GMail.Com"
    await _edit(admin, mcc_id, code, email=new_email, mobile=mobile, password=None)

    assert await _login(api, new_email.lower(), OLD_PASSWORD) == 200
    assert await _login(api, f"  {new_email.upper()} ", OLD_PASSWORD) == 200
