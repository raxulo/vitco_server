from app.core.exceptions.base import ApplicationException

class InvalidPaymentAmount(ApplicationException):
    code = "PAYMENT_INVALID_AMOUNT"
    message = "Payment amount must be greater than zero."
    status_code = 400


class SelfTransferNotAllowed(ApplicationException):
    code = "PAYMENT_SELF_TRANSFER_NOT_ALLOWED"
    message = "Self transfer is not allowed."
    status_code = 400


class PaymentPostingFailed(ApplicationException):
    code = "PAYMENT_POSTING_FAILED"
    message = "Payment posting failed."
    status_code = 500
