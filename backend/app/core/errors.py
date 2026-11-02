from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class DomainError(HTTPException):
    status_code: int
    code: str

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.message = message
        self.context = context or {}
        super().__init__(status_code=self.status_code, detail=self.message)

    def as_codec(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "context": self.context,
            }
        }


class SystemNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "system_not_found"


class RunNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "run_not_found"


class JobNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "job_not_found"


class CatalogEntryNotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "catalog_entry_not_found"


class InvalidPython(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_python"


class UnsafeImport(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "unsafe_import"


class InvalidMetadata(DomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_metadata"


class InvalidParameters(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "invalid_parameters"


class CapabilityNotSupported(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "capability_not_supported"


class JobNotCancellable(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "job_not_cancellable"


class OptimizationInProgress(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "optimization_in_progress"


class PayloadTooLarge(DomainError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "payload_too_large"


class UnsupportedMediaType(DomainError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"


class JobQueueFull(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "job_queue_full"


class RateLimited(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class EngineError(DomainError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "engine_error"


class StorageError(DomainError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "storage_error"


class ServiceNotReady(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_not_ready"
