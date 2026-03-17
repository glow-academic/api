"""MCP server for artifacts, resources, and entries."""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.infra.globals import get_client_origins

from .register import register_tools
from .tool_graph import get_mcp_tool_graph

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
        *client_origin_hosts,
        *(f"{h}:*" for h in client_origin_hosts),
    ],
    allowed_origins=client_origins if client_origins else ["*"],
)

# Create MCP server instance with transport security configured
mcp_server = FastMCP(
    "GLOW",
    stateless_http=True,
    transport_security=transport_security,
)

# Register tools from the tool graph (introspection-based)
tool_graph = get_mcp_tool_graph()
register_tools(mcp_server, tool_graph)

__all__ = ["mcp_server"]
