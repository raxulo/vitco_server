from app.core.exceptions.base import ApplicationException


class RateChartNotFoundException(ApplicationException):

    code = "RATE_CHART_NOT_FOUND"
    message = "Rate chart not found."
    status_code = 404


class RateChartAlreadyExistsException(ApplicationException):

    code = "RATE_CHART_ALREADY_EXISTS"
    message = "Rate chart name already exists."
    status_code = 409


class InvalidRateChartException(ApplicationException):

    code = "INVALID_RATE_CHART"
    message = "Invalid rate chart configuration."
    status_code = 400


class RateChartPermissionException(ApplicationException):

    code = "RATE_CHART_PERMISSION_DENIED"
    message = "You do not have permission to create or modify rate charts. You can only view them."
    status_code = 403


class RateChartLimitReachedException(ApplicationException):

    code = "RATE_CHART_LIMIT_REACHED"
    message = "Rate chart limit reached."
    status_code = 403


class RateChartAssignmentNotFoundException(ApplicationException):

    code = "RATE_CHART_ASSIGNMENT_NOT_FOUND"
    message = "Rate chart assignment not found."
    status_code = 404