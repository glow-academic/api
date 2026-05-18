#!/usr/bin/env python3
"""Get MCP access token from Keycloak for Cursor IDE."""

import os
import sys

# Add core to path for app imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import requests
from dotenv import load_dotenv

load_dotenv()


def _get_client_secret() -> str:
    """Get AUTH_KEYCLOAK_SECRET from env, or derive from SECRET_KEY when unset."""
    secret = os.getenv("AUTH_KEYCLOAK_SECRET", "").strip('"')
    if secret:
        return secret
    secret_key = os.getenv("SECRET_KEY")
    if secret_key:
        from app.utils.auth.derive_key import derive_from_secret_key
        return derive_from_secret_key(secret_key, "keycloak-client")
    return ""


def get_mcp_token():
    """Get access token from Keycloak."""
    client_id = os.getenv("AUTH_KEYCLOAK_ID", "glow-client")
    client_secret = _get_client_secret()

    if not client_secret:
        print("Error: AUTH_KEYCLOAK_SECRET or SECRET_KEY not found", file=sys.stderr)
        sys.exit(1)

    # Get token from Keycloak
    token_url = "http://localhost:8080/auth/realms/master/protocol/openid-connect/token"
    try:
        response = requests.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )

        if response.status_code != 200:
            print(f"Error: Failed to get token: {response.text}", file=sys.stderr)
            sys.exit(1)

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            print(f"Error: No access token in response: {token_data}", file=sys.stderr)
            sys.exit(1)

        print(access_token)
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Keycloak: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    get_mcp_token()
