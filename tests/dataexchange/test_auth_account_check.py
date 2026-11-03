"""
A token only authenticates while its user still exists, is active and is not
soft-deleted — an old login (e.g. from a recreated database) must not act as
a user that is gone, nor record that ghost id as `deleted_by`.
"""

from uuid import uuid4

from sqlalchemy import update

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel

_PROTECTED = "/api/v1/excel/options/vlccs"


async def test_token_of_existing_user_is_accepted(api, api_user):
    _, headers = await api_user(Role.SUPER_ADMIN)
    response = await api.get(_PROTECTED, headers=headers)
    assert response.status_code != 401


async def test_token_of_unknown_user_is_rejected(api, token_for):
    response = await api.get(_PROTECTED, headers=token_for(uuid4(), Role.SUPER_ADMIN))
    assert response.status_code == 401


async def test_token_of_deleted_or_disabled_user_is_rejected(api, database, user_factory, token_for):
    deleted_id = await user_factory(Role.ADMIN)
    disabled_id = await user_factory(Role.ADMIN)
    async with database.transaction() as session:
        await session.execute(update(UserModel).where(UserModel.id == deleted_id).values(is_deleted=True))
        await session.execute(update(UserModel).where(UserModel.id == disabled_id).values(is_active=False))

    for user_id in (deleted_id, disabled_id):
        response = await api.get(_PROTECTED, headers=token_for(user_id, Role.ADMIN))
        assert response.status_code == 401
