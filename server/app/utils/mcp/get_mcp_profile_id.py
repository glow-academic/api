"""MCP helper to get profile_id from request context."""

from collections.abc import Callable

from fastapi import HTTPException

from app.utils.logging.db_logger import profile_id_context


def resolve_mcp_profile_id(
    request: object | None, context_profile_id: str | None = None
) -> str:
    """Resolve the MCP profile ID from request state or fallback context."""
    if not request:
        if context_profile_id:
            return context_profile_id
        raise HTTPException(
            status_code=500,
            detail="MCP request context not available",
        )

    profile_id = getattr(getattr(request, "state", None), "profile_id", None)
    if not profile_id:
        raise HTTPException(
            status_code=401,
            detail="Profile ID not found. Authentication required.",
        )

    return profile_id


def get_mcp_profile_id(
    *,
    request_getter: Callable[[], object] | None = None,
) -> str:
    """Get profile_id from MCP request context.

    Uses FastMCP Context system to access HTTP request,
    then reads profile_id from request.state.profile_id
    (set by OAuth middleware).

    Returns:
        Profile ID UUID string

    Raises:
        HTTPException: If profile_id not available
    """
    try:
        if request_getter is None:
            from fastmcp.server.dependencies import get_http_request

            request_getter = get_http_request
        request = request_getter()
    except Exception:
        request = None

    return resolve_mcp_profile_id(request, profile_id_context.get(None))
