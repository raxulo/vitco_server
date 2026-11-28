"""
Support Exceptions

Python 3.13+
"""

from __future__ import annotations

from app.core.exceptions.base import ApplicationException


class SupportAccessDeniedException(ApplicationException):

    code = "SUPPORT_ACCESS_DENIED"
    message = "You do not have access to Technical Support."
    status_code = 403


class SupportPermissionDeniedException(ApplicationException):

    code = "SUPPORT_PERMISSION_DENIED"
    message = "You do not have permission to do this."
    status_code = 403


class TeamNotFoundException(ApplicationException):

    code = "SUPPORT_TEAM_NOT_FOUND"
    message = "Support team not found."
    status_code = 404


class TeamCodeAlreadyExistsException(ApplicationException):

    code = "SUPPORT_TEAM_CODE_EXISTS"
    message = "A support team with this code already exists."
    status_code = 409


class MemberNotFoundException(ApplicationException):

    code = "SUPPORT_MEMBER_NOT_FOUND"
    message = "Support member not found."
    status_code = 404


class RoleNotFoundException(ApplicationException):

    code = "SUPPORT_ROLE_NOT_FOUND"
    message = "Support role not found."
    status_code = 404


class RoleNameAlreadyExistsException(ApplicationException):

    code = "SUPPORT_ROLE_NAME_EXISTS"
    message = "This team already has a role with this name."
    status_code = 409


class ManagerNotEditableException(ApplicationException):

    code = "SUPPORT_MANAGER_NOT_EDITABLE"
    message = "The team manager cannot be changed here."
    status_code = 409


class SupportValidationException(ApplicationException):

    code = "SUPPORT_VALIDATION_ERROR"
    message = "Invalid support data."
    status_code = 422


class CategoryNotFoundException(ApplicationException):

    code = "SUPPORT_CATEGORY_NOT_FOUND"
    message = "Support category not found."
    status_code = 404


class CategoryNameAlreadyExistsException(ApplicationException):

    code = "SUPPORT_CATEGORY_NAME_EXISTS"
    message = "A category with this name already exists."
    status_code = 409


class TicketNotFoundException(ApplicationException):

    code = "SUPPORT_TICKET_NOT_FOUND"
    message = "Ticket not found."
    status_code = 404


class InvalidTicketTransitionException(ApplicationException):

    code = "SUPPORT_INVALID_TRANSITION"
    message = "This ticket cannot be moved to that status."
    status_code = 409


class TicketClosedException(ApplicationException):

    code = "SUPPORT_TICKET_CLOSED"
    message = "This ticket is closed. Reopen it to continue."
    status_code = 409


class MessageNotFoundException(ApplicationException):

    code = "SUPPORT_MESSAGE_NOT_FOUND"
    message = "Message not found."
    status_code = 404


class MessageNotDeletableException(ApplicationException):

    code = "SUPPORT_MESSAGE_NOT_DELETABLE"
    message = "This message cannot be deleted."
    status_code = 409


class InvalidAssigneeException(ApplicationException):

    code = "SUPPORT_INVALID_ASSIGNEE"
    message = "The ticket can only be assigned to an active member of its team."
    status_code = 422


class TicketNotRoutedException(ApplicationException):

    code = "SUPPORT_TICKET_NOT_ROUTED"
    message = "Send the ticket to a team first."
    status_code = 409


class CallNotFoundException(ApplicationException):

    code = "SUPPORT_CALL_NOT_FOUND"
    message = "Call not found."
    status_code = 404


class CallAlreadyOpenException(ApplicationException):

    code = "SUPPORT_CALL_OPEN"
    message = "Record the outcome of your last call first."
    status_code = 409


class DuplicateClientRequestException(ApplicationException):
    """Another request with the same `client_request_id` saved first (a retry racing the original).

    The handlers catch it and answer with the record that was saved; it reaches a client only if that
    record cannot be read back.
    """

    code = "SUPPORT_DUPLICATE_REQUEST"
    message = "This request was already received."
    status_code = 409
