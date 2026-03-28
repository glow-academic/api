"""Tests for app.utils.error.log_and_raise_error."""

import pytest
from fastapi import HTTPException

from app.utils.error.log_and_raise_error import log_and_raise_error


def test_raises_http_exception_for_generic_error():
    """A generic exception raises HTTPException with status 500."""
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(
            error=RuntimeError("something failed"),
            route_path="/api/test",
            operation="test_op",
        )
    assert exc_info.value.status_code == 500
    assert "something failed" in str(exc_info.value.detail)


def test_preserves_original_http_exception():
    """An HTTPException input preserves its status code and detail."""
    original = HTTPException(status_code=403, detail="forbidden")
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(error=original, route_path="/test", operation="op")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "forbidden"


def test_user_friendly_message_used_in_detail():
    """When user_friendly_message is given, it appears in the detail."""
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(
            error=RuntimeError("internal detail"),
            route_path="/api/test",
            operation="op",
            user_friendly_message="Something went wrong, please try again.",
        )
    assert exc_info.value.detail == "Something went wrong, please try again."


def test_works_without_optional_params():
    """Calling with only the error still raises HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(error=ValueError("bad"))
    assert exc_info.value.status_code == 500
