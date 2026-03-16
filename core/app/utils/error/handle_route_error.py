"""Convenience wrapper for log_and_raise_error that always raises."""

from typing import Any, NoReturn

from fastapi import Request

from app.utils.error.log_and_raise_error import log_and_raise_error


def handle_route_error(
    error: Exception,
    route_path: str,
    operation: str,
    sql_query: str | None = None,
    sql_params: tuple[Any, ...] | list[Any] | None = None,
    request: Request | None = None,
) -> NoReturn:
    """
    Convenience wrapper for log_and_raise_error that always raises.

    This is a non-returning function that logs and raises, making it
    easier to use in except blocks.

    Args:
        error: The exception that occurred
        route_path: API route path
        operation: Operation name (function name)
        sql_query: SQL query string if applicable
        sql_params: SQL parameters if applicable
        request: FastAPI Request object if available

    Raises:
        HTTPException: Always raises an HTTPException
    """
    log_and_raise_error(
        error=error,
        route_path=route_path,
        operation=operation,
        sql_query=sql_query,
        sql_params=sql_params,
        request=request,
    )
    raise AssertionError("handle_route_error should never return")  # pragma: no cover
