"""
Technical Support web routes (Phase 25)

Everything under `/support`. Fixed paths (`/new`, `/_kit`) come before `{id}` paths.
"""

from fastapi import APIRouter

from app.web.support.controller import SupportHomeController
from app.web.support.members_controller import SupportMembersController
from app.web.support.roles_controller import SupportRolesController
from app.web.support.teams_controller import SupportTeamsController

router = APIRouter(tags=["Web Support"])


def _route(path: str, endpoint, method: str = "GET") -> None:
    router.add_api_route(path=path, endpoint=endpoint, methods=[method])


_route("/support", SupportHomeController.home)
_route("/support/_kit", SupportHomeController.kit)

# Teams (Super Admin)
_route("/support/teams", SupportTeamsController.list_page)
_route("/support/teams/new", SupportTeamsController.new_page)
_route("/support/teams/new", SupportTeamsController.create, "POST")
_route("/support/teams/{team_id}", SupportTeamsController.detail_page)
_route("/support/teams/{team_id}/edit", SupportTeamsController.edit_page)
_route("/support/teams/{team_id}/edit", SupportTeamsController.update, "POST")
_route("/support/teams/{team_id}/status", SupportTeamsController.set_status, "POST")

# Members (Manager, or Super Admin with ?team=)
_route("/support/members", SupportMembersController.list_page)
_route("/support/members/new", SupportMembersController.new_page)
_route("/support/members/new", SupportMembersController.create, "POST")
_route("/support/members/{member_id}/edit", SupportMembersController.edit_page)
_route("/support/members/{member_id}/edit", SupportMembersController.update, "POST")
_route("/support/members/{member_id}/status", SupportMembersController.set_status, "POST")

# Roles and permissions (Manager, or Super Admin with ?team=)
_route("/support/roles", SupportRolesController.list_page)
_route("/support/roles/new", SupportRolesController.new_page)
_route("/support/roles/new", SupportRolesController.create, "POST")
_route("/support/roles/{role_id}/edit", SupportRolesController.edit_page)
_route("/support/roles/{role_id}/edit", SupportRolesController.update, "POST")
