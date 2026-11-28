"""
Technical Support web routes (Phase 25)

Everything under `/support`. Fixed paths (`/new`, `/_kit`) come before `{id}` paths.
"""

from fastapi import APIRouter

from app.web.support.activity_controller import SupportActivityController
from app.web.support.audit_controller import SupportAuditController
from app.web.support.calls_controller import SupportCallsController
from app.web.support.categories_controller import SupportCategoriesController
from app.web.support.controller import SupportHomeController
from app.web.support.members_controller import SupportMembersController
from app.web.support.roles_controller import SupportRolesController
from app.web.support.teams_controller import SupportTeamsController
from app.web.support.tickets_controller import SupportTicketsController

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

# Tickets (queues and ticket detail)
_route("/support/_live/counts", SupportTicketsController.live_counts)
_route("/support/tickets", SupportTicketsController.list_page)
_route("/support/tickets/{ticket_id}", SupportTicketsController.detail_page)
_route("/support/tickets/{ticket_id}/messages", SupportTicketsController.post_message, "POST")
_route("/support/tickets/{ticket_id}/assign", SupportTicketsController.assign, "POST")
_route("/support/tickets/{ticket_id}/status", SupportTicketsController.set_status, "POST")
_route("/support/tickets/{ticket_id}/priority", SupportTicketsController.set_priority, "POST")
_route("/support/tickets/{ticket_id}/category", SupportTicketsController.set_category, "POST")
_route("/support/tickets/{ticket_id}/route", SupportTicketsController.route, "POST")
_route("/support/attachments/{attachment_id}", SupportTicketsController.attachment)

# Categories (Super Admin)
_route("/support/categories", SupportCategoriesController.list_page)
_route("/support/categories/new", SupportCategoriesController.new_page)
_route("/support/categories/new", SupportCategoriesController.create, "POST")
_route("/support/categories/{category_id}/edit", SupportCategoriesController.edit_page)
_route("/support/categories/{category_id}/edit", SupportCategoriesController.update, "POST")
_route("/support/categories/{category_id}/status", SupportCategoriesController.set_status, "POST")

# Calls (Plan 29.1)
_route("/support/tickets/{ticket_id}/calls", SupportCallsController.start, "POST")
_route("/support/calls/{call_id}/finish", SupportCallsController.finish, "POST")

# Activity and audit (Plan 29.2)
_route("/support/activity", SupportActivityController.member_page)
_route("/support/activity/team", SupportActivityController.team_page)
_route("/support/audit", SupportAuditController.list_page)
