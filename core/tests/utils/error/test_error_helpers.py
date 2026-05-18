"""Tests for route error helpers."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.utils.error.handle_route_error import handle_route_error
from app.utils.error.log_and_raise_error import log_and_raise_error


def _request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/test",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    request.state.user_id = "user-1"
    request.state.profile_id = "profile-1"
    return request


def test_log_and_raise_error_preserves_http_exception():
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(HTTPException(status_code=404, detail="missing"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "missing"


def test_log_and_raise_error_uses_custom_user_message_for_generic_errors():
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(
            ValueError("boom"),
            route_path="/api/test",
            operation="do_work",
            request=_request(),
            user_friendly_message="Something went wrong",
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Something went wrong"


def test_handle_route_error_raises_http_exception():
    with pytest.raises(HTTPException) as exc_info:
        handle_route_error(
            RuntimeError("failure"),
            route_path="/api/test",
            operation="save_item",
            sql_query="SELECT 1",
            sql_params=["a", "b"],
            request=_request(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "failure"
