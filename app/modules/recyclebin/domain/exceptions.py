"""
Recycle Bin domain exceptions.

Python 3.13+
"""

from app.core.exceptions.base import ApplicationException


class DeletedRecordNotFoundException(ApplicationException):

    code = "DELETED_RECORD_NOT_FOUND"
    message = "Deleted record not found. It may be active or already removed."
    status_code = 404
