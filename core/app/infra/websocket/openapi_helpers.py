"""OpenAPI documentation helpers for WebSocket endpoints."""

import inspect
import re
from typing import TypeVar

from fastapi import APIRouter
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _generate_unique_function_name(router: APIRouter, path: str) -> str:
    """Generate a unique function name from router prefix, path, and calling module.

    Args:
        router: FastAPI router (may have prefix attribute)
        path: Endpoint path (e.g., "/generate")

    Returns:
        Normalized function name (e.g., "handle_socket_v4_agents_rubrics_generate")
    """
    # Get calling module path for uniqueness (go up 2 frames: current -> register_* -> caller)
    frame = inspect.currentframe()
    calling_module = ""
    if frame and frame.f_back and frame.f_back.f_back:
        caller_frame = frame.f_back.f_back
        calling_module = caller_frame.f_globals.get("__name__", "")

    # Extract relevant parts from module path (e.g., "app.socket.v4.agents.rubric.generate")
    # Remove "app." prefix and normalize
    if calling_module:
        module_parts = calling_module.replace("app.", "").split(".")
    else:
        module_parts = []

    # Get router prefix (defaults to empty string if None)
    prefix = getattr(router, "prefix", "") or ""

    # Combine module parts + prefix + path
    parts = []

    # Add relevant module parts (skip common prefixes like "socket", "v4")
    # Keep agent/resource names (e.g., "rubric", "scenario", "document")
    for part in module_parts:
        if part not in ["socket", "v4", "agents", "tools"]:
            parts.append(part)

    # Add router prefix if available
    if prefix:
        prefix_clean = prefix.strip("/").replace("/", "_")
        if prefix_clean:
            parts.append(prefix_clean)

    # Add path
    path_clean = path.strip("/").replace("/", "_")
    if path_clean:
        parts.append(path_clean)

    # Combine and normalize
    full_path = "_".join(parts)

    # Normalize: remove special chars, lowercase
    normalized = re.sub(r"[^a-z0-9_]", "", full_path.lower())
    normalized = normalized.strip("_")

    # Create function name
    return f"handle_{normalized}" if normalized else "handle_endpoint"


def register_client_endpoint(
    router: APIRouter,
    path: str,
    request_type: type[T],
    description: str,
) -> None:
    """Register a client-to-server endpoint for OpenAPI documentation.

    All WebSocket client endpoints follow the same pattern:
    - POST method
    - Request body with typed model
    - Response: {"success": True}

    Args:
        router: FastAPI router to register endpoint on
        path: Endpoint path (e.g., "/generate")
        request_type: Auto-generated ApiRequest type
        description: Endpoint description for OpenAPI docs
    """
    # Generate unique operation ID from router prefix and path
    operation_id = _generate_unique_function_name(router, path)

    @router.post(path, response_model=dict[str, bool], operation_id=operation_id)
    async def endpoint_handler(request: BaseModel) -> dict[str, bool]:  # type: ignore[arg-type]
        """Client-to-server event: {description}"""
        return {"success": True}

    # Update docstring with actual description
    endpoint_handler.__doc__ = f"Client-to-server event: {description}"


def register_server_endpoint(
    router: APIRouter,
    path: str,
    response_type: type[T],
    description: str,
) -> None:
    """Register a server-to-client endpoint for OpenAPI documentation.

    All WebSocket server endpoints follow the same pattern:
    - POST method
    - Request body with typed response model (what server sends to client)
    - Response: {"success": True}

    Args:
        router: FastAPI router to register endpoint on
        path: Endpoint path (e.g., "/generation_complete")
        response_type: Auto-generated SqlRow type (what server emits)
        description: Endpoint description for OpenAPI docs
    """
    # Generate unique operation ID from router prefix and path
    operation_id = _generate_unique_function_name(router, path)

    @router.post(path, response_model=dict[str, bool], operation_id=operation_id)
    async def endpoint_handler(request: BaseModel) -> dict[str, bool]:  # type: ignore[arg-type]
        """Server-to-client event: {description}"""
        return {"success": True}

    # Update docstring with actual description
    endpoint_handler.__doc__ = f"Server-to-client event: {description}"
