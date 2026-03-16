#!/usr/bin/env python3
"""Get MCP access token from Keycloak for Cursor IDE."""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def get_mcp_token():
    """Get access token from Keycloak."""
    client_id = os.getenv("AUTH_KEYCLOAK_ID", "glow-client")
    # The secret in .env is the actual secret (not encrypted for Keycloak client)
    client_secret = os.getenv("AUTH_KEYCLOAK_SECRET", "").strip('"')

    if not client_secret:
        print("Error: AUTH_KEYCLOAK_SECRET not found", file=sys.stderr)
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
