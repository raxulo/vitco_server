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


class RateChartAssignmentNotFoundException(ApplicationException):

    code = "RATE_CHART_ASSIGNMENT_NOT_FOUND"
    message = "Rate chart assignment not found."
    status_code = 404