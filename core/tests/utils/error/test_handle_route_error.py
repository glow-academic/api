"""Tests for app.utils.error.handle_route_error."""

import pytest
from fastapi import HTTPException

from app.utils.error.handle_route_error import handle_route_error


def test_always_raises_http_exception():
    """handle_route_error always raises an HTTPException."""
    with pytest.raises(HTTPException):
        handle_route_error(
            error=RuntimeError("something broke"),
            route_path="/api/test",
            operation="test_op",
        )


def test_preserves_http_exception_status():
    """If original error is HTTPException, its status code is preserved."""
    original = HTTPException(status_code=404, detail="not found")
    with pytest.raises(HTTPException) as exc_info:
        handle_route_error(
            error=original,
            route_path="/api/test",
            operation="test_op",
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "not found"


def test_generic_error_becomes_500():
    """A plain RuntimeError becomes a 500 HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        handle_route_error(
            error=RuntimeError("oops"),
            route_path="/api/test",
            operation="test_op",
        )
    assert exc_info.value.status_code == 500


def test_error_detail_contains_message():
    """The HTTPException detail should contain the original error message."""
    with pytest.raises(HTTPException) as exc_info:
        handle_route_error(
            error=ValueError("bad input"),
            route_path="/api/test",
            operation="test_op",
        )
    assert "bad input" in str(exc_info.value.detail)
