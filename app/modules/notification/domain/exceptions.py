"""
Notification Exceptions

Python 3.13+
"""

from __future__ import annotations

from app.core.exceptions.base import ApplicationException


class NotificationValidationException(ApplicationException):

    code = "NOTIFICATION_VALIDATION_ERROR"
    message = "Invalid notification data."
    status_code = 422


class DeviceRegistrationDeniedException(ApplicationException):

    code = "NOTIFICATION_DEVICE_DENIED"
    message = "This account cannot register a device for notifications."
    status_code = 403
