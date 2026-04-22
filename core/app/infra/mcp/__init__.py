"""MCP server for artifacts, resources, and entries."""

import logging
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp.server.fastmcp.prompts.base import Message
from mcp.server.transport_security import TransportSecuritySettings

from app.infra.globals import get_client_origins

from .prompt import get_agent_system_prompt
from .register import register_tools
from .server import SYSTEM_PROMPT_NAME, ScopedFastMCP, _current_mcp_context
from .tool_graph import get_mcp_tool_graph

logger = logging.getLogger(__name__)

load_dotenv()

# Get origin and app prefix from environment
ORIGIN = os.getenv("ORIGIN", "http://localhost:3000")
APP_PREFIX = os.getenv("APP_PREFIX", "").strip("/")

parsed_origin = urlparse(ORIGIN)
public_host = parsed_origin.hostname or "localhost"
public_port = parsed_origin.port or (443 if parsed_origin.scheme == "https" else 80)

client_origins = get_client_origins()
client_origin_hosts = set()
for o in client_origins:
    parsed = urlparse(o)
    if parsed.hostname:
        client_origin_hosts.add(parsed.hostname)

# Configure FastMCP transport security to allow the public domain and internal hosts
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        public_host,
        f"{public_host}:*",
        f"{public_host}:{public_port}",
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
        "server",
        "server:*",
        "server:8000",
        # Internal Docker aliases — docs/client nginx proxy MCP via these
        "glow-api",
        "glow-api:*",
        "glow-api:8000",
        "glow-nginx",
        "glow-nginx:*",
        "nginx",
        "nginx:*",
        *client_origin_hosts,
        *(f"{h}:*" for h in client_origin_hosts),
    ],
    allowed_origins=client_origins if client_origins else ["*"],
)

# Create MCP server instance with transport security configured
mcp_server = ScopedFastMCP(
    "GLOW",
    stateless_http=True,
    streamable_http_path="/",
    transport_security=transport_security,
)

# Register the INFRA_OPS catalog. Per-caller scoping happens in ScopedFastMCP.
tool_graph = get_mcp_tool_graph()
register_tools(mcp_server, tool_graph)


@mcp_server.prompt(
    name=SYSTEM_PROMPT_NAME,
    title="Agent system prompt",
    description=(
        "Returns the MCP agent's system prompt for this caller, as "
        "configured on the caller's department setting."
    ),
)
async def _agent_system_prompt() -> list[Message]:
    """Resolve the caller's agent and return its system prompt, if any."""
    from app.infra.globals import get_pool, get_redis_client

    ctx = await _current_mcp_context()
    if ctx is None or ctx.agent_id is None:
        return [Message(role="user", content="No MCP agent configured for this caller.")]

    pool = get_pool()
    redis = get_redis_client()
    if pool is None or redis is None:
        return [Message(role="user", content="Server pool or redis unavailable.")]

    try:
        text = await get_agent_system_prompt(pool, redis, ctx.agent_id)
    except Exception:
        logger.exception("get_agent_system_prompt failed")
        text = None

    if not text:
        return [Message(role="user", content="Agent has no system prompt configured.")]
    return [Message(role="user", content=text)]


__all__ = ["mcp_server"]
