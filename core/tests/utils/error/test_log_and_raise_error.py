"""Tests for app.utils.error.log_and_raise_error."""

import asyncpg
import pytest
from fastapi import HTTPException

from app.utils.error.log_and_raise_error import (
    _GENERIC_500_DETAIL,
    log_and_raise_error,
)


def test_raises_http_exception_for_generic_error():
    """A generic exception raises HTTPException with status 500."""
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(
            error=RuntimeError("something failed"),
            route_path="/api/test",
            operation="test_op",
        )
    assert exc_info.value.status_code == 500


def test_generic_error_detail_does_not_leak_internal_message():
    """The raw exception string must NOT reach the client on a generic 500.

    ``str(error)`` can carry file paths, infra/connection details, or
    secrets; the client should see only a generic message while the real
    error is logged server-side.
    """
    secret_internal = (
        'connection to /var/run/postgresql failed: '
        'FATAL: role "glow_app" does not exist'
    )
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(
            error=RuntimeError(secret_internal),
            route_path="/api/v3/auths/create",
            operation="create_auth",
        )
    detail = str(exc_info.value.detail)
    assert detail == _GENERIC_500_DETAIL
    assert "glow_app" not in detail
    assert "/var/run/postgresql" not in detail


def test_sql_error_detail_does_not_leak_schema():
    """A raw asyncpg error must NOT reach the client on a SQL 500.

    The asyncpg message leaks internal table/column/constraint names and
    the failing SQL; the client should see only a generic message.
    """
    err = asyncpg.exceptions.UniqueViolationError(
        'duplicate key value violates unique constraint '
        '"emails_resource_email_key"'
    )
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(
            error=err,
            route_path="/api/v3/auths/create",
            operation="create_auth",
            sql_query="INSERT INTO emails_resource (email) VALUES ($1)",
            sql_params=("a@b.com",),
        )
    detail = str(exc_info.value.detail)
    assert exc_info.value.status_code == 500
    assert detail == _GENERIC_500_DETAIL
    assert "emails_resource_email_key" not in detail
    assert "Database error" not in detail


def test_department_permission_denied_message_still_surfaced():
    """The curated DEPARTMENT_PERMISSION_DENIED message is still user-facing."""
    err = asyncpg.exceptions.RaiseError(
        "DEPARTMENT_PERMISSION_DENIED: You cannot edit this department."
    )
    with pytest.raises(HTTPException) as exc_info:
        log_and_raise_error(error=err, route_path="/api/test", operation="op")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "You cannot edit this department."


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
