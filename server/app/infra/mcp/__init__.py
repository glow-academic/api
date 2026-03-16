"""MCP server for artifacts, resources, and entries."""

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .register import register_tools
from .tool_graph import get_mcp_tool_graph

load_dotenv()

# Get origin and app prefix from environment
ORIGIN = os.getenv("ORIGIN", "http://localhost:3000")
APP_PREFIX = os.getenv("APP_PREFIX", "").strip("/")

# Extract hostname from ORIGIN (e.g., "https://company.ashoksaravanan.com" -> "company.ashoksaravanan.com")
from urllib.parse import urlparse

parsed_origin = urlparse(ORIGIN)
public_host = parsed_origin.hostname or "localhost"
public_port = parsed_origin.port or (443 if parsed_origin.scheme == "https" else 80)

# Configure FastMCP transport security to allow the public domain and internal hosts
# This fixes the 421 "Invalid Host header" error from FastMCP's DNS rebinding protection
# Note: Host header from nginx is "company.ashoksaravanan.com" (no port), so we need
# to allow both the hostname alone and with port patterns
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        public_host,  # Exact hostname without port (what nginx sends)
        f"{public_host}:*",  # Public domain with any port (wildcard)
        f"{public_host}:{public_port}",  # Public domain with explicit port
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
        "server",  # Docker service name without port
        "server:*",  # Docker service name with any port
        "server:8000",  # Docker service name with explicit port
    ],
    allowed_origins=[
        "*",  # Allow all origins - OAuth tokens provide the real security
    ],
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
