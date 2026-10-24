from app.core.exceptions.base import ApplicationException


class ExcelJobNotFoundException(ApplicationException):

    code = "EXCEL_JOB_NOT_FOUND"
    message = "Import / export job not found."
    status_code = 404


class ExcelJobConflictException(ApplicationException):

    code = "EXCEL_JOB_ALREADY_RUNNING"
    message = "An import / export of this type is already running. Please wait for it to finish."
    status_code = 409
    retry_after = 30


class ExcelJobCapacityException(ApplicationException):

    code = "EXCEL_JOB_QUEUE_FULL"
    message = "The server is busy with other imports / exports. Please try again shortly."
    status_code = 429
    retry_after = 30


class ExcelJobFinishedException(ApplicationException):

    code = "EXCEL_JOB_FINISHED"
    message = "This import / export has already finished."
    status_code = 409


class ExcelJobFileNotReadyException(ApplicationException):

    code = "EXCEL_JOB_FILE_NOT_READY"
    message = "The file for this job is not ready yet."
    status_code = 409


class ExcelUploadNotFoundException(ApplicationException):

    code = "EXCEL_UPLOAD_NOT_FOUND"
    message = "Upload not found or expired. Please upload the file again."
    status_code = 404


class ExcelUploadIncompleteException(ApplicationException):

    code = "EXCEL_UPLOAD_INCOMPLETE"
    message = "The upload is not complete yet."
    status_code = 409


class InvalidExcelFileException(ApplicationException):

    code = "INVALID_EXCEL_FILE"
    message = "The uploaded file is not a valid Excel (.xlsx) workbook."
    status_code = 422


class ExcelFileTooLargeException(ApplicationException):

    code = "EXCEL_FILE_TOO_LARGE"
    message = "The uploaded file is larger than the allowed limit."
    status_code = 413


class ExcelStorageFullException(ApplicationException):

    code = "EXCEL_STORAGE_FULL"
    message = "Not enough free disk space on the server for this import / export."
    status_code = 507
