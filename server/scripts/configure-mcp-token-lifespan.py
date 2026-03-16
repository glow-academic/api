#!/usr/bin/env python3
"""Configure Keycloak master realm access token lifespan for MCP."""

import asyncio
import os
import socket
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Import Keycloak admin directly to avoid circular imports
try:
    from keycloak import KeycloakAdmin  # type: ignore
except ImportError:
    print("Error: python-keycloak package not installed", file=sys.stderr)
    sys.exit(1)


def _can_resolve_hostname(hostname: str) -> bool:
    """Check if hostname can be resolved (for Docker vs local detection)."""
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False


async def ensure_mcp_token_lifespan(kc_admin: Any) -> None:
    """Ensure master realm has appropriate access token lifespan for MCP.

    Configures the access token lifespan in the master realm to a longer duration
    (default 24 hours) to avoid frequent token refreshes for MCP clients.
    """
    # Check if MCP is enabled (simplified check - just check if ORIGIN is set)
    origin = os.getenv("ORIGIN", "http://localhost:3000")
    if not origin:
        print("⚠️  MCP appears to be disabled (no ORIGIN set)", file=sys.stderr)
        return

    try:
        kc_admin.change_current_realm(realm_name="master")

        # Get current realm configuration
        realm = kc_admin.get_realm("master")
        current_lifespan = realm.get("accessTokenLifespan", 60)  # Default is 60 seconds

        # Read desired lifespan from environment (default: 24 hours = 86400 seconds)
        desired_lifespan = int(os.getenv("MCP_TOKEN_LIFESPAN", "86400"))

        if current_lifespan < desired_lifespan:
            # Update realm with new token lifespan
            kc_admin.update_realm(
                realm_name="master",
                payload={"accessTokenLifespan": desired_lifespan},
            )
            print(
                f"✅ Updated master realm access token lifespan: {current_lifespan}s → {desired_lifespan}s "
                f"({desired_lifespan // 3600}h)"
            )
        else:
            print(
                f"✅ Master realm access token lifespan already configured: {current_lifespan}s "
                f"({current_lifespan // 3600}h)"
            )
    except Exception as e:
        print(f"⚠️  Could not ensure MCP token lifespan: {e}", file=sys.stderr)
        raise


async def wait_for_keycloak(
    url: str,
    admin: str,
    password: str,
    max_retries: int = 1,  # Fail fast - this is optional
) -> Any | None:
    """Wait for Keycloak to be ready and return a connected KeycloakAdmin instance.

    Returns None if connection fails - this is acceptable as token lifespan
    configuration is optional and MCP will work with default token settings.
    """
    # Check if we're in local dev mode
    origin_check = os.getenv("ORIGIN", "http://localhost:3000")
    is_local_dev = "localhost" in origin_check.lower()

    try:
        # Disable SSL verification for non-production environments
        verify_ssl = not is_local_dev

        # KeycloakAdmin expects base URL - it adds /auth itself
        base_url = url.rstrip("/")
        if base_url.endswith("/auth"):
            base_url = base_url[:-5]  # Remove /auth

        kc_admin = KeycloakAdmin(
            server_url=f"{base_url}/",
            username=admin,
            password=password,
            realm_name="master",
            verify=verify_ssl,
        )
        # Test the connection by getting realms
        kc_admin.get_realms()
        return kc_admin
    except Exception:
        # Fail silently - this is optional configuration
        # The python-keycloak library has known issues with Keycloak 26.0's relative path config
        # when KC_HTTP_RELATIVE_PATH=/auth is set
        return None


async def main() -> None:
    """Configure MCP token lifespan."""
    keycloak_url = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
    keycloak_admin = os.getenv("KEYCLOAK_ADMIN", "admin")
    keycloak_admin_password = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")

    # Detect local dev environment
    origin_check = os.getenv("ORIGIN", "http://localhost:3000")
    is_local_dev = "localhost" in origin_check.lower()

    # Try localhost if internal URL doesn't work or we're in local dev
    if is_local_dev or (
        "keycloak" in keycloak_url and not _can_resolve_hostname("keycloak")
    ):
        keycloak_url = "http://localhost:8080"

    kc_admin = await wait_for_keycloak(
        keycloak_url, keycloak_admin, keycloak_admin_password
    )

    if not kc_admin:
        print("⚠️  Could not connect to Keycloak admin API (this is optional)")
        print("   Token lifespan will use Keycloak's default settings")
        print(
            "   MCP will still work - you can configure token lifespan manually in Keycloak admin console"
        )
        return  # Exit gracefully - this is optional

    await ensure_mcp_token_lifespan(kc_admin)
    print("✅ MCP token lifespan configured")


if __name__ == "__main__":
    asyncio.run(main())
