from app.core.exceptions.base import ApplicationException

class BankAccountNotFoundException(ApplicationException):
    code = "BANK_ACCOUNT_NOT_FOUND"
    message = "Bank account not found."
    status_code = 404

class InvalidBankAccountException(ApplicationException):
    code = "INVALID_BANK_ACCOUNT"
    message = "Invalid bank account."
    status_code = 400