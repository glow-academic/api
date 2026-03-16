#!/usr/bin/env python3
"""Inspect Keycloak flow execution structure to see actual API response format."""

import json
import os
import sys

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from keycloak import KeycloakAdmin  # type: ignore


def main():
    """Inspect Keycloak flow execution structure."""
    # Get Keycloak connection details from environment
    keycloak_url = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    app_prefix = os.getenv("APP_PREFIX", "")

    if app_prefix:
        keycloak_url = f"{keycloak_url.rstrip('/')}{app_prefix}/auth"
    else:
        keycloak_url = f"{keycloak_url.rstrip('/')}/auth"

    keycloak_admin = os.getenv("KEYCLOAK_ADMIN", "admin")
    keycloak_password = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")

    print(f"Connecting to Keycloak at {keycloak_url}...")

    try:
        kc_admin = KeycloakAdmin(
            server_url=f"{keycloak_url}/",
            username=keycloak_admin,
            password=keycloak_password,
            realm_name="master",
            verify=False,
        )

        # Test connection
        kc_admin.get_realms()
        print("✅ Connected to Keycloak\n")

        # Get the flow we're interested in
        flow_alias = "First Broker Login - Silent Email AutoLink"

        # Get flow executions using raw API call (same as our code)
        import urllib.parse

        encoded_alias = urllib.parse.quote(flow_alias, safe="")
        path = (
            f"/auth/admin/realms/master/authentication/flows/{encoded_alias}/executions"
        )

        print(f"Fetching executions for flow: {flow_alias}")
        print(f"API path: {path}\n")

        resp = kc_admin.connection.raw_get(path)
        resp.raise_for_status()
        execs = resp.json()

        print(f"Found {len(execs)} executions\n")
        print("=" * 80)
        print("RAW API RESPONSE STRUCTURE:")
        print("=" * 80)
        print(json.dumps(execs, indent=2))
        print("\n" + "=" * 80)
        print("FIELD ANALYSIS:")
        print("=" * 80)

        for idx, e in enumerate(execs):
            print(f"\n--- Execution {idx + 1} ---")
            print(f"All keys: {list(e.keys())}")
            print(f"id: {e.get('id')}")
            print(f"displayName: {e.get('displayName')}")
            print(f"providerId: {e.get('providerId')}")
            print(f"requirement: {e.get('requirement')}")
            print(f"priority: {e.get('priority')}")
            print(f"flowId: {e.get('flowId')}")
            print(f"authFlowId: {e.get('authFlowId')}")
            print(f"auth_flow_id: {e.get('auth_flow_id')}")
            print(f"authenticatorFlow: {e.get('authenticatorFlow')}")
            print(f"authenticator_flow: {e.get('authenticator_flow')}")
            print("Full object:")
            print(json.dumps(e, indent=2))

        # Also check subflows
        print("\n" + "=" * 80)
        print("CHECKING SUBFLOWS:")
        print("=" * 80)

        flows = kc_admin.get_authentication_flows()
        flow_id_to_alias = {
            f.get("id"): f.get("alias") for f in flows if f.get("id") and f.get("alias")
        }

        for e in execs:
            flow_id = e.get("flowId")
            auth_flow_id = e.get("authFlowId") or e.get("auth_flow_id")
            is_subflow = e.get("authenticatorFlow", False) or e.get(
                "authenticator_flow", False
            )

            if flow_id and flow_id in flow_id_to_alias:
                print(
                    f"\nExecution {e.get('id')} references flow: {flow_id_to_alias[flow_id]}"
                )
            if auth_flow_id and auth_flow_id in flow_id_to_alias:
                print(
                    f"Execution {e.get('id')} references authFlow: {flow_id_to_alias[auth_flow_id]} (is_subflow={is_subflow})"
                )

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
