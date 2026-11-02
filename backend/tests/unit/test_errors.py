from __future__ import annotations

import pytest
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from app.core.errors import (
    CapabilityNotSupported,
    DomainError,
    EngineError,
    InvalidMetadata,
    InvalidPython,
    JobNotFound,
    OptimizationInProgress,
    PayloadTooLarge,
    RunNotFound,
    SystemNotFound,
    UnsafeImport,
)


@pytest.mark.parametrize(
    "exc_class,expected_status,expected_code",
    [
        (SystemNotFound, HTTP_404_NOT_FOUND, "system_not_found"),
        (RunNotFound, HTTP_404_NOT_FOUND, "run_not_found"),
        (JobNotFound, HTTP_404_NOT_FOUND, "job_not_found"),
        (InvalidPython, HTTP_400_BAD_REQUEST, "invalid_python"),
        (UnsafeImport, HTTP_400_BAD_REQUEST, "unsafe_import"),
        (InvalidMetadata, HTTP_400_BAD_REQUEST, "invalid_metadata"),
        (CapabilityNotSupported, HTTP_409_CONFLICT, "capability_not_supported"),
        (OptimizationInProgress, HTTP_409_CONFLICT, "optimization_in_progress"),
        (PayloadTooLarge, HTTP_413_CONTENT_TOO_LARGE, "payload_too_large"),
        (EngineError, HTTP_500_INTERNAL_SERVER_ERROR, "engine_error"),
    ],
)
def test_envelope_maps_to_canonical_codes(exc_class, expected_status, expected_code):
    error = exc_class("boom")
    assert error.status_code == expected_status
    assert error.as_codec() == {
        "error": {
            "code": expected_code,
            "message": "boom",
            "context": {},
        }
    }


def test_http_exception_base_class():
    with pytest.raises(DomainError):
        raise SystemNotFound("missing")


def test_context_is_included():
    error = InvalidMetadata("bad", context={"field": "name"})
    assert error.as_codec()["error"]["context"] == {"field": "name"}
