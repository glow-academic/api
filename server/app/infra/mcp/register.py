"""MCP tool registration — introspects route handlers to build MCP tools dynamically.

Given a tool graph of (artifact, operation) pairs, this module:
  1. Registers a tool for each pair with name = {operation}_{artifact}
  2. At call time, imports app.routes.v5.{artifact}.{operation}
  3. Finds the handler function via the module's router
  4. Extracts the Pydantic request model from its signature
  5. Calls the handler with proper Identity(is_mcp=True) context
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, get_type_hints

from fastapi import Response
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from starlette.requests import Request as StarletteRequest

from app.infra.globals import get_db

logger = logging.getLogger(__name__)

# Cache imported handlers + models to avoid repeated imports
_handler_cache: dict[str, Any] = {}
_model_cache: dict[str, type[BaseModel] | None] = {}


def _import_handler(module_path: str) -> Any:
    """Import the route handler from a module.

    Strategy: look at the module's router.routes to find the actual endpoint
    function (not utility imports). Falls back to first public async function.
    """
    if module_path in _handler_cache:
        return _handler_cache[module_path]

    mod = importlib.import_module(module_path)

    # Strategy 1: Find the endpoint registered on the router
    router = getattr(mod, "router", None)
    if router and hasattr(router, "routes"):
        for route in router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint and inspect.iscoroutinefunction(endpoint):
                _handler_cache[module_path] = endpoint
                return endpoint

    # Strategy 2: Fall back to first public async function defined in the module
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        if inspect.iscoroutinefunction(obj) and obj.__module__ == mod.__name__:
            _handler_cache[module_path] = obj
            return obj

    raise ValueError(f"No async handler found in {module_path}")


def _get_request_model(handler: Any) -> type[BaseModel] | None:
    """Extract the Pydantic request model from a handler's first parameter."""
    try:
        hints = get_type_hints(handler)
        sig = inspect.signature(handler)
        first_param = list(sig.parameters.values())[0]
        model = hints.get(first_param.name, first_param.annotation)
        if isinstance(model, type) and issubclass(model, BaseModel):
            return model
    except Exception:
        pass
    return None


def _build_tool_args(
    request_model: type[BaseModel],
) -> list[dict[str, Any]]:
    """Extract arg definitions from Pydantic model fields.

    Returns a list of dicts with name, type, description, required, default.
    Filters out internal fields like 'mcp'.
    """
    args = []
    schema = request_model.model_json_schema()
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_schema in properties.items():
        # Skip internal fields
        if field_name in ("mcp",):
            continue

        args.append(
            {
                "name": field_name,
                "description": field_schema.get("description", ""),
                "type": field_schema.get("type", "string"),
                "required": field_name in required_fields,
                "default": field_schema.get("default"),
                "schema": field_schema,
            }
        )

    return args


def _resolve_handler_and_model(
    module_path: str,
) -> tuple[Any, type[BaseModel]]:
    """Import handler and extract request model. Raises on failure."""
    handler = _import_handler(module_path)

    if module_path not in _model_cache:
        _model_cache[module_path] = _get_request_model(handler)

    model = _model_cache[module_path]
    if model is None:
        raise ValueError(f"No Pydantic request model for {module_path}")

    return handler, model


async def _call_handler(
    handler: Any,
    request_model: type[BaseModel],
    payload: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    """Call an endpoint handler with proper Request/Response/DB context.

    Creates a request with an Identity(is_mcp=True) — no synthetic X-MCP header.
    """
    from uuid import UUID

    from app.infra.identity.resolve_identity import Identity

    try:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v5/mcp",
            "headers": [],
            "query_string": b"",
            "server": ("localhost", 8000),
        }
        http_request = StarletteRequest(scope)

        # Set identity with is_mcp=True — single source of truth
        identity = Identity(
            profile_id=UUID(profile_id),
            session_id=UUID(int=0),
            is_mcp=True,
        )
        http_request.state.identity = identity
        http_request.state.profile_id = profile_id
        http_request.state.session_id = None

        http_response = Response()

        # Auto-inject mcp: true if request model has mcp field
        if "mcp" in request_model.model_fields:
            payload = {**payload, "mcp": True}

        # Filter out None values to let Pydantic defaults apply
        payload = {k: v for k, v in payload.items() if v is not None}

        api_request = request_model(**payload)

        # Detect if handler expects conn parameter
        handler_params = inspect.signature(handler).parameters
        if "conn" in handler_params:
            result = None
            async for conn in get_db():
                result = await handler(
                    request=api_request,
                    http_request=http_request,
                    response=http_response,
                    conn=conn,
                )
            if result is None:
                return {"error": "Database connection not available", "status": "error"}
        else:
            result = await handler(
                request=api_request,
                http_request=http_request,
                response=http_response,
            )

        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        elif hasattr(result, "dict"):
            return result.dict()
        else:
            return {"data": result}

    except Exception as e:
        return {"error": str(e), "status": "error", "type": type(e).__name__}


def register_tools(
    server: FastMCP,
    tool_graph: list[tuple[str, str]],
) -> None:
    """Register MCP tools from a tool graph.

    Handler import and model introspection are deferred to call time
    to avoid circular imports at module load. Each tool is registered
    with a generic (kwargs, **kw) signature.
    """
    for artifact, operation in tool_graph:
        module_path = f"app.routes.v5.{artifact}.{operation}"
        tool_name = f"{operation}_{artifact}"
        description = f"{operation} {artifact}"

        # Capture in closure via default args
        async def make_tool(
            kwargs: dict[str, Any] | None = None,
            *,
            mod_path: str = module_path,
            **kw: Any,
        ) -> dict[str, Any]:
            from app.utils.mcp.get_mcp_profile_id import get_mcp_profile_id

            handler, model = _resolve_handler_and_model(mod_path)
            profile_id = get_mcp_profile_id()
            payload = {**(kwargs or {}), **kw}
            return await _call_handler(handler, model, payload, profile_id)

        # Set function metadata for FastMCP
        make_tool.__name__ = tool_name
        make_tool.__qualname__ = tool_name
        make_tool.__doc__ = description

        # Register with FastMCP
        server.tool()(make_tool)

        logger.debug(f"Registered MCP tool: {tool_name}")
