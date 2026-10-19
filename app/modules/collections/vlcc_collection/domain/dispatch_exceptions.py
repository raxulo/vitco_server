class DispatchException(Exception):
    pass


class DispatchNotFoundException(DispatchException):
    def __init__(self, message: str = "Dispatch record not found") -> None:
        super().__init__(message)
