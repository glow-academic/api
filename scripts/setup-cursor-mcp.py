#!/usr/bin/env python3
"""Setup Cursor IDE MCP configuration for GLOW server."""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_token():
    """Get MCP token from Keycloak."""
    script_dir = Path(__file__).parent
    token_script = script_dir / "get-mcp-token.py"
    result = subprocess.run(
        [sys.executable, str(token_script)],
        capture_output=True,
        text=True,
        cwd=script_dir.parent,
    )
    if result.returncode != 0:
        print(f"Error getting token: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def update_cursor_config(token: str):
    """Update Cursor MCP configuration."""
    config_path = Path.home() / ".cursor" / "mcp.json"

    # Read existing config
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {"mcpServers": {}}

    # Add GLOW server
    config["mcpServers"]["glow-local"] = {
        "url": "http://localhost:8000/mcp",
        "headers": {"Authorization": f"Bearer {token}"},
    }

    # Write updated config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Get token lifetime from environment or default
    token_lifespan = int(os.getenv("MCP_TOKEN_LIFESPAN", "86400"))
    token_lifespan_hours = token_lifespan // 3600

    print(f"✅ Updated Cursor MCP config at {config_path}")
    print("   Server: glow-local")
    print("   URL: http://localhost:8000/mcp")
    print(f"   Token: {token[:50]}...")
    print(f"   Token lifetime: {token_lifespan_hours} hours ({token_lifespan}s)")
    print()
    print("💡 Restart Cursor IDE to use the new configuration")


if __name__ == "__main__":
    token = get_token()
    update_cursor_config(token)
