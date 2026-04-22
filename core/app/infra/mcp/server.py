"""FastMCP subclass that scopes tools/prompts per authenticated caller.

FastMCP registers tools once at startup (stateless_http). To give each
caller only their agent's tools without dropping the shared registry,
we override list_tools/list_prompts/get_prompt to read the current
request's profile_id, resolve the MCP context, and filter accordingly.

Per-call enforcement in register.py._dispatch is still the source of
truth; this class only shapes what the MCP client sees.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import GetPromptResult, Prompt as MCPPrompt, Tool as MCPTool

from app.infra.mcp.resolve import (
    McpContext,
    allowed_tool_names,
    resolve_mcp_context,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_NAME = "agent_system_prompt"


def _current_profile_id() -> UUID | None:
    """Best-effort lookup of the caller's profile_id from the OAuth middleware.

    McpOAuthMiddleware resolves the bearer token and calls set_profile_id(),
    which writes profile_id_context — a ContextVar that propagates through
    the async task into FastMCP's list_tools / list_prompts / prompt handlers.
    """
    from app.utils.logging.db_logger import profile_id_context

    value = profile_id_context.get(None)
    if not value:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


async def _current_mcp_context() -> McpContext | None:
    """Resolve the MCP context for the caller of the current request."""
    from app.infra.globals import get_pool, get_redis_client

    profile_id = _current_profile_id()
    if profile_id is None:
        return None
    pool = get_pool()
    redis = get_redis_client()
    if pool is None or redis is None:
        return None
    try:
        return await resolve_mcp_context(pool, redis, profile_id)
    except Exception:
        logger.exception("resolve_mcp_context failed during MCP discovery")
        return None


class ScopedFastMCP(FastMCP):
    """FastMCP that filters discovery by the authenticated caller's MCP scope."""

    async def _ensure_catalog(self) -> None:
        """Lazy-register the DB-driven tool catalog on first MCP request."""
        from app.infra.mcp.register import ensure_registered

        await ensure_registered(self)

    async def list_tools(self) -> list[MCPTool]:
        await self._ensure_catalog()
        tools = await super().list_tools()
        ctx = await _current_mcp_context()
        if ctx is None or ctx.agent_id is None:
            # No context → advertise nothing. Clients see an empty tool list
            # rather than a menu of tools that will fail at call time.
            return []
        allowed = allowed_tool_names(ctx)
        return [t for t in tools if t.name in allowed]

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        await self._ensure_catalog()
        return await super().call_tool(name, arguments)

    async def list_prompts(self) -> list[MCPPrompt]:
        prompts = await super().list_prompts()
        ctx = await _current_mcp_context()
        # Hide the system_prompt prompt if the caller has no agent.
        if ctx is None or ctx.agent_id is None:
            return [p for p in prompts if p.name != SYSTEM_PROMPT_NAME]
        return prompts

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> GetPromptResult:
        # Default path — FastMCP will invoke the registered prompt function,
        # which itself resolves the caller's MCP context.
        return await super().get_prompt(name, arguments)
