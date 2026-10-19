from app.core.exceptions.base import ApplicationException


class RouteNotFoundException(ApplicationException):

    code = "ROUTE_NOT_FOUND"
    message = "Route not found."
    status_code = 404


class RouteCodeAlreadyExistsException(ApplicationException):

    code = "ROUTE_CODE_ALREADY_EXISTS"
    message = "Route code already exists."
    status_code = 409


class InvalidRouteException(ApplicationException):

    code = "INVALID_ROUTE"
    message = "Invalid route configuration."
    status_code = 400