"""MCP route — mounts the Streamable-HTTP MCP app at /."""

from app.infra.mcp import mcp_server

mcp_app = mcp_server.streamable_http_app()
