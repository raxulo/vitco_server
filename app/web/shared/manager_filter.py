"""
Admin / Sub Admin dropdown filter for the MCC and VLCC list pages.

Who sees what:
    Super Admin -> Admin dropdown (and, when asked for, a Sub Admin dropdown;
                   picking an Admin narrows the Sub Admins to that Admin's)
    Admin       -> Sub Admin dropdown (its own Sub Admins), when asked for
    others      -> no dropdowns

Combined mode (MCC list): a single `manager_id` dropdown grouping Admins and
Sub Admins — all of them for Super Admin, its own Sub Admins for an Admin.

The chosen user becomes a `CurrentUser` "manager"; repositories filter to that
user's line through the `Hierarchy` rules, on top of the viewer's own scope.
Values not offered in the dropdowns are ignored.

Python 3.13+
"""

from dataclasses import dataclass, field
from uuid import UUID

from fastapi import Request

from app.middleware.authentication import CurrentUser
from app.modules.administration.application.command import ListUsersQuery
from app.modules.administration.domain.enums import Role
from app.modules.dependencies import GetHandler


@dataclass(slots=True, kw_only=True)
class ManagerOption:
    id: str
    name: str
    parent_id: str | None = None
    parent_name: str | None = None


@dataclass(slots=True, kw_only=True)
class ManagerFilter:
    admins: list[ManagerOption] = field(default_factory=list)
    sub_admins: list[ManagerOption] = field(default_factory=list)
    admin_id: str = ""
    sub_admin_id: str = ""
    show_admin: bool = False
    show_sub_admin: bool = False
    # Combined mode: one dropdown (`manager_id`) holding Admins and Sub Admins
    combined: bool = False
    manager: CurrentUser | None = None

    @property
    def manager_id(self) -> str:
        return self.sub_admin_id or self.admin_id

    @property
    def active(self) -> bool:
        return bool(self.admin_id or self.sub_admin_id)

    @property
    def query_string(self) -> str:
        """Filter params for pagination links (empty when unused)."""
        if self.combined:
            return f"&manager_id={self.manager_id}" if self.manager_id else ""
        parts = []
        if self.admin_id:
            parts.append(f"&admin_id={self.admin_id}")
        if self.sub_admin_id:
            parts.append(f"&sub_admin_id={self.sub_admin_id}")
        return "".join(parts)


async def resolve_manager_filter(
    request: Request,
    *,
    admin_id: str = "",
    sub_admin_id: str = "",
    manager_id: str = "",
    with_sub_admins: bool = False,
    combined: bool = False,
) -> ManagerFilter:
    user: CurrentUser = request.state.user
    role = user.role_type
    result = ManagerFilter()
    if role not in (Role.SUPER_ADMIN, Role.ADMIN):
        return result

    handler = GetHandler.user_handler(request)

    async def options(of_role: Role) -> list[ManagerOption]:
        users = await handler.list(ListUsersQuery(page=1, size=1000, role=of_role, owner=user))
        return sorted(
            (
                ManagerOption(
                    id=str(u.id),
                    name=u.name,
                    parent_id=str(u.created_by) if u.created_by else None,
                )
                for u in users
            ),
            key=lambda option: option.name.lower(),
        )

    if combined:
        # One dropdown: Super Admin gets every Admin and Sub Admin, an Admin its own Sub Admins
        result.combined = True
        if role == Role.SUPER_ADMIN:
            result.admins = await options(Role.ADMIN)
        result.sub_admins = await options(Role.SUB_ADMIN)
        admin_names = {option.id: option.name for option in result.admins}
        for option in result.sub_admins:
            option.parent_name = admin_names.get(option.parent_id or "")
        result.show_admin = bool(result.admins or result.sub_admins)
        if manager_id in {option.id for option in result.admins}:
            result.admin_id = manager_id
        elif manager_id in {option.id for option in result.sub_admins}:
            result.sub_admin_id = manager_id
        result.manager = _as_manager(result)
        return result

    if role == Role.SUPER_ADMIN:
        result.show_admin = True
        result.admins = await options(Role.ADMIN)
        if admin_id in {option.id for option in result.admins}:
            result.admin_id = admin_id

    if with_sub_admins:
        result.show_sub_admin = True
        result.sub_admins = await options(Role.SUB_ADMIN)
        if result.admin_id:
            # Only the chosen Admin's Sub Admins
            result.sub_admins = [s for s in result.sub_admins if s.parent_id == result.admin_id]
        if sub_admin_id in {option.id for option in result.sub_admins}:
            result.sub_admin_id = sub_admin_id

    result.manager = _as_manager(result)
    return result


def _as_manager(result: ManagerFilter) -> CurrentUser | None:
    """The narrowest choice wins: a Sub Admin, else an Admin (with its Sub Admins)."""
    if result.sub_admin_id:
        return CurrentUser(id=UUID(result.sub_admin_id), role=str(int(Role.SUB_ADMIN)))
    if result.admin_id:
        return CurrentUser(id=UUID(result.admin_id), role=str(int(Role.ADMIN)))
    return None
