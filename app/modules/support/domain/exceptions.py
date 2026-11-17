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
