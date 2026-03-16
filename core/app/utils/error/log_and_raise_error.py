"""Log error with full context and raise HTTPException."""

from typing import Any

import asyncpg  # type: ignore
from fastapi import HTTPException, Request

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def log_and_raise_error(
    error: Exception,
    route_path: str | None = None,
    operation: str | None = None,
    sql_query: str | None = None,
    sql_params: tuple[Any, ...] | list[Any] | None = None,
    request: Request | None = None,
    user_friendly_message: str | None = None,
) -> None:
    """
    Log error with full context and raise HTTPException.

    This function provides comprehensive error logging:
    - SQL errors: Logs query, parameters, and asyncpg error details
    - Other errors: Logs exception type, message, and full stack trace
    - Route context: Includes path, operation, and request details when available

    Args:
        error: The exception that occurred
        route_path: API route path (e.g., "/api/v3/parameters/new")
        operation: Operation name (e.g., "get_parameter_new")
        sql_query: SQL query string if this was a SQL error
        sql_params: SQL parameters tuple/list if this was a SQL error
        request: FastAPI Request object for extracting additional context
        user_friendly_message: Custom user-facing error message (defaults to str(error))

    Returns:
        HTTPException with appropriate status code and detail message

    Raises:
        HTTPException: Always raises an HTTPException
    """
    # Determine if this is a SQL error
    is_sql_error = isinstance(
        error,
        (
            asyncpg.PostgresError,
            asyncpg.PostgresSyntaxError,
            asyncpg.PostgresConnectionError,
            asyncpg.PostgresWarning,
        ),
    )

    # Build error context for logging
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if route_path:
        error_context["route_path"] = route_path
    if operation:
        error_context["operation"] = operation

    # Add SQL-specific context
    if is_sql_error and sql_query:
        error_context["sql_query"] = sql_query
        if sql_params is not None:
            # Truncate long parameter lists for readability
            params_str = str(sql_params)
            if len(params_str) > 500:
                params_str = params_str[:500] + "... (truncated)"
            error_context["sql_params"] = params_str

    # Add request context if available
    if request:
        error_context["request_method"] = request.method
        error_context["request_url"] = str(request.url)
        # Try to get user info from request state if available
        if hasattr(request.state, "user_id"):
            error_context["user_id"] = request.state.user_id
        if hasattr(request.state, "profile_id"):
            error_context["profile_id"] = request.state.profile_id

    # Log error with appropriate detail level
    if is_sql_error:
        # SQL errors: Log query, params, and error details
        log_msg = f"SQL Error in {operation or route_path or 'unknown route'}: {error}"
        if sql_query:
            log_msg += f"\nQuery: {sql_query}"
        if sql_params is not None:
            log_msg += f"\nParams: {sql_params}"
        logger.error(log_msg, exc_info=True, extra=error_context)
    else:
        # Other errors: Log with full stack trace
        log_msg = f"Error in {operation or route_path or 'unknown route'}: {error}"
        logger.error(log_msg, exc_info=True, extra=error_context)

    # Determine HTTP status code
    if isinstance(error, HTTPException):
        # Preserve original HTTPException status
        status_code = error.status_code
        detail = error.detail
    elif is_sql_error:
        # Check for department permission denied errors
        error_msg = str(error)
        if "DEPARTMENT_PERMISSION_DENIED:" in error_msg:
            # Extract user-friendly message after the prefix
            detail = (
                error_msg.split("DEPARTMENT_PERMISSION_DENIED: ", 1)[1]
                if "DEPARTMENT_PERMISSION_DENIED: " in error_msg
                else error_msg
            )
            status_code = 403
        else:
            # Other SQL errors: 500 with database error message
            status_code = 500
            detail = user_friendly_message or f"Database error: {str(error)}"
    else:
        # Other errors: 500 with generic message
        status_code = 500
        detail = user_friendly_message or str(error)

    # Raise HTTPException
    raise HTTPException(status_code=status_code, detail=detail)
