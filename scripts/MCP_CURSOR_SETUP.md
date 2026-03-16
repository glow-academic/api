# MCP Cursor IDE Setup

Quick setup for connecting Cursor IDE to your local GLOW MCP server.

## Quick Setup

Run the setup command:

```bash
make mcp
```

This will:
1. Configure Keycloak access token lifespan (default: 24 hours)
2. Get a fresh access token from Keycloak
3. Update your Cursor MCP configuration at `~/.cursor/mcp.json`

## Configuration

The setup adds this server to your Cursor config:

```json
{
  "mcpServers": {
    "glow-local": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

## Token Lifetime

Tokens are valid for **24 hours** by default. To change this, set `MCP_TOKEN_LIFESPAN` in your `.env` file (value in seconds).

Example for 12 hours:
```
MCP_TOKEN_LIFESPAN=43200
```

## Manual Token Retrieval

If you need to get a token manually:

```bash
python3 scripts/get-mcp-token.py
```

## Troubleshooting

- **Keycloak not running**: Start services with `make run`
- **Token expired**: Run `make mcp` again to refresh
- **Cursor not connecting**: Restart Cursor IDE after running `make mcp`
