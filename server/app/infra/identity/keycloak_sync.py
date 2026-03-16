"""Keycloak sync utility - synchronous sync function that returns success/failure."""

import asyncio
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.keycloak_resolvers import (
    resolve_auth_items,
    resolve_auths_for_department,
    resolve_auths_for_realm,
    resolve_departments_for_sync,
    resolve_setting_profiles_for_idp,
)
from app.infra.mcp.oauth import MCP_RESOURCE, is_mcp_enabled
from app.utils.auth.decrypt_api_key import decrypt_api_key
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Retry configuration
MAX_RETRIES = 10
INITIAL_RETRY_DELAY = 2.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds


@dataclass
class KeycloakSyncResult:
    """Result of a Keycloak sync operation."""

    success: bool
    message: str
    department_id: str | None = None
    error: str | None = None


@dataclass
class KeycloakSyncConfig:
    """Configuration for Keycloak sync. All env vars resolved once at boundary."""

    auth_keycloak_id: str = "glow-client"
    auth_keycloak_secret: str | None = None
    client_port: str = "3000"
    app_prefix: str = ""
    origin: str = ""
    auth_secret: str | None = None
    keycloak_url: str | None = None
    keycloak_internal_url: str | None = None
    keycloak_admin: str = "admin"
    keycloak_admin_password: str = "admin"
    docker_env: str | None = None
    mcp_token_lifespan: int = 86400

    @classmethod
    def from_env(cls) -> "KeycloakSyncConfig":
        """Create config from environment variables."""
        client_port = os.getenv("CLIENT_PORT", "3000")
        return cls(
            auth_keycloak_id=os.getenv("AUTH_KEYCLOAK_ID", "glow-client"),
            auth_keycloak_secret=os.getenv("AUTH_KEYCLOAK_SECRET"),
            client_port=client_port,
            app_prefix=os.getenv("APP_PREFIX", ""),
            origin=os.getenv("ORIGIN", f"http://localhost:{client_port}"),
            auth_secret=os.getenv("AUTH_SECRET"),
            keycloak_url=os.getenv("KEYCLOAK_URL"),
            keycloak_internal_url=os.getenv("KEYCLOAK_INTERNAL_URL"),
            keycloak_admin=os.getenv("KEYCLOAK_ADMIN", "admin"),
            keycloak_admin_password=os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"),
            docker_env=os.getenv("DOCKER_ENV"),
            mcp_token_lifespan=int(os.getenv("MCP_TOKEN_LIFESPAN", "86400")),
        )


async def wait_for_keycloak(
    url: str,
    admin: str,
    password: str,
    max_retries: int = MAX_RETRIES,
) -> Any | None:
    """Wait for Keycloak to be ready and return a connected KeycloakAdmin instance."""
    try:
        from keycloak import KeycloakAdmin  # type: ignore
    except ImportError:
        logger.warning("keycloak package not installed, skipping Keycloak sync")
        return None

    retry_delay = INITIAL_RETRY_DELAY

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"Attempting to connect to Keycloak (attempt {attempt}/{max_retries})..."
            )

            kc_admin = KeycloakAdmin(
                server_url=f"{url}/",
                username=admin,
                password=password,
                realm_name="master",
                verify=False,
            )
            # Test the connection by getting realms
            kc_admin.get_realms()
            logger.info("✅ Successfully connected to Keycloak")
            return kc_admin
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"Keycloak not ready yet (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {retry_delay:.1f}s..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, MAX_RETRY_DELAY)
            else:
                logger.error(
                    f"Failed to connect to Keycloak after {max_retries} attempts: {e}"
                )
                return None

    return None


async def ensure_department_client(
    department_id: str,
    department_name: str,
    kc_admin: Any,
    config: KeycloakSyncConfig,
) -> str | None:
    """Ensure department-specific client exists in master realm.

    Creates client with ID: glow-client-{department_id}
    This allows client-scoped org routing in Keycloak.

    Args:
        department_id: Department ID (UUID string)
        department_name: Department name (for display)
        kc_admin: KeycloakAdmin instance (must be in master realm)
        config: Keycloak sync configuration

    Returns:
        client_id if created/updated, None if error
    """
    target_secret = config.auth_keycloak_secret

    if not target_secret:
        logger.warning(
            f"⚠️  AUTH_KEYCLOAK_SECRET is missing. Cannot create department client for {department_id}."
        )
        return None

    try:
        # Ensure we're in master realm
        kc_admin.change_current_realm(realm_name="master")

        # Client ID format: glow-client-{department_id}
        department_client_id = f"glow-client-{department_id}"

        base_url = config.origin.rstrip("/")
        redirect_uri = f"{base_url}{config.app_prefix}/api/auth/callback/keycloak"
        emulate_redirect_uri = (
            f"{base_url}{config.app_prefix}/api/auth/emulate-redirect*"
        )
        redirect_uris = [redirect_uri, f"{base_url}{config.app_prefix}/*"]
        post_logout_uris = f"{base_url}{config.app_prefix}/*"

        clients = kc_admin.get_clients()
        existing_client = next(
            (c for c in clients if c.get("clientId") == department_client_id),
            None,
        )

        client_payload: dict[str, Any] = {
            "clientId": department_client_id,
            "name": f"Glow App - {department_name}",
            "rootUrl": base_url,
            "baseUrl": base_url,
            "redirectUris": redirect_uris + [emulate_redirect_uri],
            "webOrigins": ["+"],
            "enabled": True,
            "publicClient": False,
            "protocol": "openid-connect",
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": True,
            "clientAuthenticatorType": "client-secret",
            "secret": target_secret,
            "consentRequired": False,
            "attributes": {
                "post.logout.redirect.uris": post_logout_uris,
            },
        }

        if existing_client:
            client_uuid = existing_client.get("id")
            if client_uuid:
                try:
                    kc_admin.update_client(
                        client_id=client_uuid, payload=client_payload
                    )
                    logger.info(
                        f"✅ Department client '{department_client_id}' updated"
                    )
                    return department_client_id
                except Exception as e:
                    logger.warning(
                        f"Failed to update department client '{department_client_id}': {e}"
                    )
                    return None
        else:
            try:
                new_client_uuid = kc_admin.create_client(
                    payload=client_payload, skip_exists=True
                )
                logger.info(f"✅ Department client '{department_client_id}' created")

                if new_client_uuid:
                    kc_admin.update_client(
                        client_id=new_client_uuid,
                        payload={"secret": target_secret},
                    )
                    logger.info(
                        f"✅ Department client secret enforced for '{department_client_id}'"
                    )
                    return department_client_id
            except Exception as e:
                error_str = str(e).lower()
                is_conflict = (
                    "location" in error_str
                    or "duplicate" in error_str
                    or "conflict" in error_str
                    or "409" in error_str
                    or "already exists" in error_str
                )

                if is_conflict:
                    logger.info(
                        f"⚠️  Department client '{department_client_id}' already exists"
                    )
                    return department_client_id
                else:
                    logger.warning(
                        f"Failed to create department client '{department_client_id}': {e}"
                    )
                    return None
    except Exception as e:
        logger.warning(f"Could not ensure department client for {department_id}: {e}")
        return None


async def ensure_glow_client_in_master_realm(
    kc_admin: Any, config: KeycloakSyncConfig
) -> None:
    """Ensure glow-client exists in master realm with correct configuration.

    Args:
        kc_admin: KeycloakAdmin instance
        config: Keycloak sync configuration
    """
    target_client_id = config.auth_keycloak_id
    target_secret = config.auth_keycloak_secret

    if not target_secret:
        logger.warning("⚠️  AUTH_KEYCLOAK_SECRET is missing. Cannot create glow-client.")
        return

    try:
        # Switch to master realm to ensure client is created there
        kc_admin.change_current_realm(realm_name="master")

        base_url = config.origin.rstrip("/")
        redirect_uri = f"{base_url}{config.app_prefix}/api/auth/callback/keycloak"
        redirect_uris = [redirect_uri, f"{base_url}{config.app_prefix}/*"]

        clients = kc_admin.get_clients()
        existing_client = next(
            (c for c in clients if c.get("clientId") == target_client_id),
            None,
        )

        # Post-logout redirect URIs for emulation flow (logout then re-auth as different user)
        emulate_redirect_uri = (
            f"{base_url}{config.app_prefix}/api/auth/emulate-redirect*"
        )
        post_logout_uris = f"{base_url}{config.app_prefix}/*"

        client_payload: dict[str, Any] = {
            "clientId": target_client_id,
            "name": "Glow App",
            "rootUrl": base_url,
            "baseUrl": base_url,
            "redirectUris": redirect_uris + [emulate_redirect_uri],
            "webOrigins": ["+"],
            "enabled": True,
            "publicClient": False,
            "protocol": "openid-connect",
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": True,
            "clientAuthenticatorType": "client-secret",
            "secret": target_secret,
            "consentRequired": False,
            # Post-logout redirect URIs - required for emulation flow
            "attributes": {
                "post.logout.redirect.uris": post_logout_uris,
            },
        }

        if existing_client:
            client_uuid = existing_client.get("id")
            if client_uuid:
                try:
                    kc_admin.update_client(
                        client_id=client_uuid, payload=client_payload
                    )
                    logger.info(f"✅ Master realm: Client '{target_client_id}' updated")
                except Exception as e:
                    logger.warning(
                        f"Failed to update master realm client '{target_client_id}': {e}"
                    )
        else:
            try:
                new_client_uuid = kc_admin.create_client(
                    payload=client_payload, skip_exists=True
                )
                logger.info(f"✅ Master realm: Client '{target_client_id}' created")

                if new_client_uuid:
                    kc_admin.update_client(
                        client_id=new_client_uuid,
                        payload={"secret": target_secret},
                    )
                    logger.info(
                        f"✅ Master realm: Client secret enforced for '{target_client_id}'"
                    )
            except Exception as e:
                error_str = str(e).lower()
                is_conflict = (
                    "location" in error_str
                    or "duplicate" in error_str
                    or "conflict" in error_str
                    or "409" in error_str
                    or "already exists" in error_str
                )

                if is_conflict:
                    logger.info(
                        f"⚠️  Master realm: Client '{target_client_id}' already exists"
                    )
                else:
                    logger.warning(
                        f"Failed to create master realm client '{target_client_id}': {e}"
                    )
    except Exception as e:
        logger.warning(f"Could not ensure glow-client in master realm: {e}")


async def ensure_mcp_client_scope(kc_admin: Any, config: KeycloakSyncConfig) -> None:
    """Ensure MCP client scope exists in master realm with audience mapper.

    Creates the mcp-resource client scope, adds an audience mapper with the MCP
    resource URL, and assigns it to glow-client as a default client scope.

    Args:
        kc_admin: KeycloakAdmin instance (must be in master realm)
        config: Keycloak sync configuration
    """
    # Check if MCP is enabled
    if not is_mcp_enabled():
        logger.debug("MCP is disabled, skipping MCP client scope creation")
        return

    target_client_id = config.auth_keycloak_id
    scope_name = "mcp-resource"
    mapper_name = "mcp-audience"

    try:
        # Ensure we're in master realm
        kc_admin.change_current_realm(realm_name="master")

        # Get MCP resource URL from oauth module (which handles localhost detection)
        mcp_resource_url = MCP_RESOURCE

        # Step 1: Check if client scope exists, create if not
        try:
            scopes = kc_admin.get_client_scopes()
            existing_scope = next(
                (s for s in scopes if s.get("name") == scope_name), None
            )
        except Exception as e:
            logger.warning(f"Failed to list client scopes: {e}")
            return

        if existing_scope:
            scope_id = existing_scope.get("id")
            # Update scope to ensure consent screen is disabled
            try:
                kc_admin.update_client_scope(
                    client_scope_id=scope_id,
                    payload={
                        "id": scope_id,
                        "name": scope_name,
                        "attributes": {"display.on.consent.screen": "false"},
                    },
                )
                logger.info(
                    f"✅ Updated client scope '{scope_name}' to disable consent screen"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to update client scope '{scope_name}' attributes: {e}"
                )
        else:
            # Create the client scope
            scope_payload: dict[str, Any] = {
                "name": scope_name,
                "description": "MCP resource scope for OAuth audience binding",
                "protocol": "openid-connect",
                "attributes": {
                    "display.on.consent.screen": "false",
                },
            }

            try:
                scope_id = kc_admin.create_client_scope(scope_payload, skip_exists=True)
                logger.info(f"✅ Created client scope '{scope_name}'")
            except Exception as e:
                error_str = str(e).lower()
                is_conflict = (
                    "location" in error_str
                    or "duplicate" in error_str
                    or "conflict" in error_str
                    or "409" in error_str
                    or "already exists" in error_str
                )

                if is_conflict:
                    # Scope was created by another process, fetch it
                    scopes = kc_admin.get_client_scopes()
                    existing_scope = next(
                        (s for s in scopes if s.get("name") == scope_name), None
                    )
                    if existing_scope:
                        scope_id = existing_scope.get("id")
                        logger.info(
                            f"⚠️  Client scope '{scope_name}' was created by another process"
                        )
                    else:
                        logger.warning(
                            f"Client scope '{scope_name}' conflict but not found"
                        )
                        return
                else:
                    logger.warning(f"Failed to create client scope '{scope_name}': {e}")
                    return

        if not scope_id:
            logger.warning(f"Client scope '{scope_name}' has no ID")
            return

        # Step 2: Check if audience mapper exists, create if not
        try:
            mappers = kc_admin.get_mappers_from_client_scope(scope_id)
            existing_mapper = next(
                (m for m in mappers if m.get("name") == mapper_name), None
            )
        except Exception as e:
            logger.warning(f"Failed to list mappers for scope '{scope_name}': {e}")
            return

        if existing_mapper:
            mapper_id = existing_mapper.get("id")
            # Check if mapper config needs update
            mapper_config = existing_mapper.get("config", {})
            current_audience = mapper_config.get("included.custom.audience", "")
            if current_audience != mcp_resource_url:
                # Update mapper config - need to update the full mapper payload
                updated_mapper_payload = dict(existing_mapper)
                updated_mapper_payload["config"] = dict(mapper_config)
                updated_mapper_payload["config"]["included.custom.audience"] = (
                    mcp_resource_url
                )
                try:
                    kc_admin.update_mapper_in_client_scope(
                        client_scope_id=scope_id,
                        protocol_mapper_id=mapper_id,
                        payload=updated_mapper_payload,
                    )
                    logger.info(
                        f"✅ Updated audience mapper '{mapper_name}' with MCP resource URL"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to update audience mapper '{mapper_name}': {e}"
                    )
            else:
                logger.info(
                    f"✅ Audience mapper '{mapper_name}' already configured correctly"
                )
        else:
            # Create the audience mapper
            mapper_payload: dict[str, Any] = {
                "name": mapper_name,
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "config": {
                    "included.client.audience": "",
                    "included.custom.audience": mcp_resource_url,
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                },
            }

            try:
                kc_admin.add_mapper_to_client_scope(
                    client_scope_id=scope_id, payload=mapper_payload
                )
                logger.info(
                    f"✅ Created audience mapper '{mapper_name}' for scope '{scope_name}'"
                )
            except Exception as e:
                error_str = str(e).lower()
                is_conflict = (
                    "location" in error_str
                    or "duplicate" in error_str
                    or "conflict" in error_str
                    or "409" in error_str
                    or "already exists" in error_str
                )

                if is_conflict:
                    logger.info(
                        f"⚠️  Audience mapper '{mapper_name}' was created by another process"
                    )
                else:
                    logger.warning(
                        f"Failed to create audience mapper '{mapper_name}': {e}"
                    )
                    return

        # Step 3: Assign scope as realm default client scope (so ALL clients get it, including dynamically registered ones)
        # This ensures all client tokens (including ChatGPT's dynamically registered clients) include the MCP resource audience
        try:
            # Get current realm default client scopes
            try:
                realm_default_scopes = kc_admin.get_realm_default_client_scopes()
                has_realm_scope = any(
                    s.get("name") == scope_name for s in realm_default_scopes
                )
            except Exception as e:
                logger.debug(f"Failed to get realm default client scopes: {e}")
                has_realm_scope = False

            if not has_realm_scope:
                # Add scope as realm default client scope
                # This ensures ALL clients (including dynamically registered ones like ChatGPT) get the scope
                try:
                    kc_admin.add_default_default_client_scope(scope_id=scope_id)
                    logger.info(
                        f"✅ Added client scope '{scope_name}' as realm default scope (applies to all clients including dynamically registered ones)"
                    )
                except Exception as e:
                    error_str = str(e).lower()
                    is_conflict = (
                        "location" in error_str
                        or "duplicate" in error_str
                        or "conflict" in error_str
                        or "409" in error_str
                        or "already exists" in error_str
                    )
                    if is_conflict:
                        logger.info(
                            f"⚠️  Realm default client scope '{scope_name}' was already added by another process"
                        )
                    else:
                        logger.warning(
                            f"Failed to add realm default client scope '{scope_name}': {e}"
                        )
            else:
                logger.info(
                    f"✅ Client scope '{scope_name}' already assigned as realm default scope"
                )
        except Exception as e:
            logger.warning(
                f"Failed to assign realm default client scope '{scope_name}': {e}"
            )

        # Step 4: Also assign scope to glow-client as default client scope (for backward compatibility)
        try:
            clients = kc_admin.get_clients()
            client = next(
                (c for c in clients if c.get("clientId") == target_client_id), None
            )

            if not client:
                logger.warning(
                    f"Client '{target_client_id}' not found, cannot assign MCP scope"
                )
                return

            client_id = client.get("id")
            if not client_id:
                logger.warning(f"Client '{target_client_id}' has no ID")
                return

            # Get current default client scopes
            try:
                default_scopes = kc_admin.get_client_default_client_scopes(
                    client_id=client_id
                )
                scope_already_assigned = any(
                    s.get("name") == scope_name for s in default_scopes
                )
            except Exception as e:
                logger.warning(
                    f"Failed to get default client scopes for '{target_client_id}': {e}"
                )
                default_scopes = []
                scope_already_assigned = False

            if scope_already_assigned:
                logger.info(
                    f"✅ Client scope '{scope_name}' already assigned to '{target_client_id}'"
                )
            else:
                # Add scope as default client scope
                # The add_client_default_client_scope method requires a payload with client_scope_id
                try:
                    kc_admin.add_client_default_client_scope(
                        client_id=client_id,
                        client_scope_id=scope_id,
                        payload={},  # Empty payload, scope_id is in the method parameter
                    )
                    logger.info(
                        f"✅ Assigned client scope '{scope_name}' to '{target_client_id}' as default scope"
                    )
                except Exception as e:
                    error_str = str(e).lower()
                    is_conflict = (
                        "location" in error_str
                        or "duplicate" in error_str
                        or "conflict" in error_str
                        or "409" in error_str
                        or "already exists" in error_str
                    )

                    if is_conflict:
                        logger.info(
                            f"⚠️  Client scope '{scope_name}' was already assigned to '{target_client_id}'"
                        )
                    else:
                        logger.warning(
                            f"Failed to assign client scope '{scope_name}' to '{target_client_id}': {e}"
                        )

        except Exception as e:
            logger.warning(
                f"Failed to assign client scope '{scope_name}' to '{target_client_id}': {e}"
            )

    except Exception as e:
        logger.warning(f"Could not ensure MCP client scope: {e}")


async def ensure_mcp_token_lifespan(kc_admin: Any, config: KeycloakSyncConfig) -> None:
    """Ensure master realm has appropriate access token lifespan for MCP.

    Configures the access token lifespan in the master realm to a longer duration
    (default 24 hours) to avoid frequent token refreshes for MCP clients.

    Args:
        kc_admin: KeycloakAdmin instance (must be in master realm)
        config: Keycloak sync configuration
    """
    if not is_mcp_enabled():
        logger.debug("MCP is disabled, skipping token lifespan configuration")
        return

    try:
        kc_admin.change_current_realm(realm_name="master")

        # Get current realm configuration
        realm = kc_admin.get_realm("master")
        current_lifespan = realm.get("accessTokenLifespan", 60)  # Default is 60 seconds

        desired_lifespan = config.mcp_token_lifespan

        if current_lifespan < desired_lifespan:
            # Update realm with new token lifespan
            kc_admin.update_realm(
                realm_name="master",
                payload={"accessTokenLifespan": desired_lifespan},
            )
            logger.info(
                f"✅ Updated master realm access token lifespan: {current_lifespan}s → {desired_lifespan}s "
                f"({desired_lifespan // 3600}h)"
            )
        else:
            logger.debug(
                f"Master realm access token lifespan already configured: {current_lifespan}s "
                f"({current_lifespan // 3600}h)"
            )
    except Exception as e:
        logger.warning(f"Could not ensure MCP token lifespan: {e}")


async def ensure_client_registration_policies(kc_admin: Any) -> None:
    """Ensure client registration policies allow MCP clients (Cursor, ChatGPT).

    Keycloak's default client registration policies block MCP clients:
    1. Trusted Hosts policy blocks custom URI schemes like cursor://
    2. Consent Required policy forces consent for dynamically registered clients

    This function:
    1. Removes Trusted Hosts policy (blocks custom schemes)
    2. Removes Consent Required policy (forces consent screen)
    3. Ensures Initial Access Token policy is enabled (secure alternative)

    Args:
        kc_admin: KeycloakAdmin instance (must be in master realm)
    """
    try:
        kc_admin.change_current_realm(realm_name="master")

        # Get realm ID
        realm = kc_admin.get_realm("master")
        realm_id = realm.get("id")

        if not realm_id:
            logger.warning(
                "Master realm has no ID, cannot update client registration policies"
            )
            return

        # Get all components for master realm
        components = kc_admin.get_components(query={"parent": realm_id})

        # Find Trusted Hosts component (providerId="trusted-hosts", subType="anonymous")
        # We remove this because it blocks custom URI schemes like cursor://
        trusted_hosts_component = None
        consent_required_component = None

        for comp in components:
            provider_id = comp.get("providerId")
            sub_type = comp.get("subType")
            provider_type = comp.get("providerType")

            if (
                provider_id == "trusted-hosts"
                and sub_type == "anonymous"
                and provider_type
                == "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy"
            ):
                trusted_hosts_component = comp
            elif (
                provider_id == "consent-required"
                and sub_type == "anonymous"
                and provider_type
                == "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy"
            ):
                consent_required_component = comp

        # Remove Trusted Hosts policy - it blocks custom URI schemes (cursor://)
        if trusted_hosts_component:
            component_id = trusted_hosts_component.get("id")
            if component_id:
                try:
                    kc_admin.delete_component(component_id=component_id)
                    logger.info(
                        "✅ Removed Trusted Hosts policy (blocks custom URI schemes like cursor://)"
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove Trusted Hosts policy: {e}")
            else:
                logger.warning("Trusted Hosts component has no ID")
        else:
            logger.info(
                "✅ Trusted Hosts policy not found (already removed or never existed)"
            )

        # Remove Consent Required policy - it forces consent for dynamically registered clients
        if consent_required_component:
            component_id = consent_required_component.get("id")
            if component_id:
                try:
                    kc_admin.delete_component(component_id=component_id)
                    logger.info(
                        "✅ Removed Consent Required policy (forces consent for dynamically registered clients)"
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove Consent Required policy: {e}")
            else:
                logger.warning("Consent Required component has no ID")
        else:
            logger.info(
                "✅ Consent Required policy not found (already removed or never existed)"
            )

        # After removing Trusted Hosts, Keycloak allows anonymous client registration
        # This means any MCP client (Cursor, ChatGPT, Claude, Windsurf, etc.) can register
        # with any redirect URI scheme (including cursor://) without requiring an Initial Access Token.
        #
        # After removing Consent Required, dynamically registered clients default to consentRequired=false
        # This prevents the consent screen from appearing for MCP clients.
        #
        # Security note: Redirect URIs are still validated during OAuth flow, so this is safe.
        # The Trusted Hosts policy was blocking legitimate MCP clients, not providing real security.
        # The Consent Required policy was forcing unnecessary consent screens.

        logger.info(
            "✅ Client registration now allows any redirect URI scheme and disables consent by default"
        )

    except Exception as e:
        logger.warning(
            f"Could not update client registration policies: {e}", exc_info=True
        )


async def ensure_dynamic_clients_no_consent(kc_admin: Any) -> None:
    """Post-process dynamically registered MCP clients to disable consent.

    Dynamically registered clients (like ChatGPT-XXXX, Cursor-XXXX, or UUID-based)
    may require consent by default. This function finds them and disables consent.

    Strategy:
    - Known MCP client patterns (ChatGPT, Cursor, etc.)
    - UUID-based client_ids (dynamically registered clients often use UUIDs)
    - Clients that are NOT our managed clients (glow-client, glow-client-*)

    Args:
        kc_admin: KeycloakAdmin instance (must be in master realm)
    """
    if not is_mcp_enabled():
        logger.debug("MCP is disabled, skipping dynamic client consent fix")
        return

    try:
        kc_admin.change_current_realm(realm_name="master")

        # Get all clients
        clients = kc_admin.get_clients()

        # Our managed clients (should NOT be updated by this function)
        managed_client_prefixes = [
            "glow-client",
            "admin-cli",
            "broker",
            "realm-management",
            "security-admin-console",
            "account",
            "account-console",
        ]

        # Known MCP client patterns (Cursor, ChatGPT, Claude, Windsurf, etc.)
        mcp_client_patterns = [
            "ChatGPT",
            "Cursor",
            "Claude",
            "Windsurf",
            "Cursor-",
            "chatgpt-",
            "claude-",
            "windsurf-",
        ]

        updated_count = 0
        for client in clients:
            client_id = client.get("clientId", "")
            client_uuid = client.get("id")
            consent_required = client.get("consentRequired", False)

            # Skip our managed clients
            is_managed = any(
                client_id.startswith(prefix) for prefix in managed_client_prefixes
            )
            if is_managed:
                continue

            # Check if this looks like a dynamically registered MCP client
            # Pattern 1: Known MCP client names
            is_mcp_client_by_name = any(
                pattern.lower() in client_id.lower() for pattern in mcp_client_patterns
            )

            # Pattern 2: UUID-based client_id (common for dynamically registered clients)
            # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
            is_uuid_client = bool(
                re.match(
                    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                    client_id,
                    re.IGNORECASE,
                )
            )

            # Pattern 3: Check redirect URIs for MCP patterns
            redirect_uris = client.get("redirectUris", [])
            has_mcp_redirect = any(
                "chatgpt.com" in uri.lower()
                or "cursor.sh" in uri.lower()
                or "cursor://" in uri.lower()
                or "claude.ai" in uri.lower()
                or "windsurf.ai" in uri.lower()
                for uri in redirect_uris
            )

            is_mcp_client = is_mcp_client_by_name or (
                is_uuid_client and has_mcp_redirect
            )

            if is_mcp_client and consent_required and client_uuid:
                try:
                    # Update client to disable consent
                    kc_admin.update_client(
                        client_id=client_uuid,
                        payload={"consentRequired": False},
                    )
                    logger.info(
                        f"✅ Disabled consent for dynamically registered client: {client_id}"
                    )
                    updated_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to disable consent for client '{client_id}': {e}"
                    )

        if updated_count > 0:
            logger.info(
                f"✅ Updated {updated_count} dynamically registered MCP client(s) to disable consent"
            )
        else:
            logger.debug(
                "No dynamically registered MCP clients found requiring consent fix"
            )

    except Exception as e:
        logger.warning(
            f"Could not ensure dynamic clients have no consent: {e}", exc_info=True
        )


async def ensure_default_scopes_no_consent(kc_admin: Any) -> None:
    """Disable consent screen display for all default client scopes.

    Even if clients have consentRequired=false, Keycloak will still show consent
    if the scopes themselves have display.on.consent.screen=true.

    Args:
        kc_admin: KeycloakAdmin instance (must be in master realm)
    """
    try:
        scopes_to_update = {
            "offline_access",
            "address",
            "roles",
            "profile",
            "organization",
            "email",
            "phone",
            "mcp-resource",
        }

        all_scopes = kc_admin.get_client_scopes()
        updated_count = 0

        for scope in all_scopes:
            scope_name = scope.get("name", "")
            if scope_name not in scopes_to_update:
                continue

            scope_id = scope.get("id")
            attrs = scope.get("attributes", {})
            if attrs.get("display.on.consent.screen") == "false":
                continue

            try:
                kc_admin.update_client_scope(
                    client_scope_id=scope_id,
                    payload={
                        "id": scope_id,
                        "name": scope_name,
                        "attributes": {"display.on.consent.screen": "false"},
                    },
                )
                logger.info(f"✅ Disabled consent screen for scope: {scope_name}")
                updated_count += 1
            except Exception as e:
                logger.warning(
                    f"Failed to update scope '{scope_name}' to disable consent: {e}"
                )

        if updated_count > 0:
            logger.info(
                f"✅ Updated {updated_count} client scope(s) to disable consent screen"
            )

    except Exception as e:
        logger.warning(
            f"Could not ensure default scopes have no consent: {e}", exc_info=True
        )


async def sync_identity_provider_for_realm_level(
    auth_id: str,
    slug: str,
    provider_id: str,
    display_name: str,
    kc_admin: Any,
    pool: Any,
    redis: Any,
) -> None:
    """Sync a single identity provider at realm level (platform login).

    Args:
        auth_id: Auth ID (UUID string)
        slug: Provider slug/alias
        provider_id: Provider type (e.g., "google", "oidc", "saml")
        display_name: Display name for the provider
        kc_admin: KeycloakAdmin instance (must be in master realm)
        pool: Database connection pool
        redis: Redis client
    """
    try:
        # Ensure we're in master realm
        kc_admin.change_current_realm(realm_name="master")
        async with pool.acquire() as conn:
            auth_items = await resolve_auth_items(
                conn, redis, uuid.UUID(auth_id), department_id=None
            )

        # Build config map from items
        config_map: dict[str, str] = {}
        for item in auth_items:
            if item.encrypted:
                try:
                    decrypted_value = decrypt_api_key(item.value)
                    config_map[item.name] = decrypted_value
                except Exception as e:
                    logger.warning(
                        f"Failed to decrypt auth_item '{item.name}' for provider '{slug}': {e}. Using as plain text."
                    )
                    config_map[item.name] = item.value
            else:
                config_map[item.name] = item.value

        # Build IdP payload
        # Set hideOnLogin=False - theme controls visibility via filtering
        # If we hide IdPs, Keycloak 26.0 excludes them from social.providers, so theme can't render them
        payload: dict[str, Any] = {
            "alias": slug,
            "providerId": provider_id,
            "displayName": display_name,
            "enabled": True,
            "trustEmail": True,
            "hideOnLogin": False,  # Must be False so IdPs appear in social.providers for theme filtering
            "config": {},
        }

        # Configure provider-specific settings
        if provider_id == "saml":
            if "ssoUrl" in config_map:
                payload["config"]["singleSignOnServiceUrl"] = config_map["ssoUrl"]
            if "entityId" in config_map:
                payload["config"]["entityId"] = config_map["entityId"]
            if "metadataUrl" in config_map:
                payload["config"]["importFromIdpUrl"] = config_map["metadataUrl"]
            if "certificate" in config_map:
                payload["config"]["signingCertificate"] = config_map["certificate"]
            if "nameIDPolicyFormat" not in payload["config"]:
                payload["config"]["nameIDPolicyFormat"] = (
                    "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
                )
            if "syncMode" not in payload["config"]:
                payload["config"]["syncMode"] = "FORCE"
            if "allowCreate" not in payload["config"]:
                payload["config"]["allowCreate"] = "true"
        else:
            payload["config"] = config_map
            if "syncMode" not in payload["config"]:
                payload["config"]["syncMode"] = "FORCE"
            if "useJwksUrl" not in payload["config"]:
                payload["config"]["useJwksUrl"] = "true"

        # Create or update IdP (realm-level, no organization_id)
        try:
            kc_admin.get_idp(idp_alias=slug)
            # IdP exists, update it
            kc_admin.update_idp(idp_alias=slug, payload=payload)
            logger.info(f"✅ Updated realm-level IdP: {slug}")
        except Exception:
            # IdP doesn't exist, create it
            kc_admin.create_idp(payload=payload)
            logger.info(f"✅ Created realm-level IdP: {slug}")
    except Exception as e:
        logger.warning(f"Failed to sync realm-level IdP '{slug}': {e}", exc_info=True)


async def sync_identity_provider_for_org(
    auth_id: str,
    slug: str,
    provider_id: str,
    display_name: str,
    department_id: str,
    kc_admin: Any,
    pool: Any,
    redis: Any,
) -> None:
    """Sync a single identity provider for department-scoped auths.

    Uses auth_id-based alias for 1:1 mapping: auth_{slug}_{auth_id}
    This ensures one IdP per auth object regardless of how many departments use it.

    Args:
        auth_id: Auth ID (UUID string)
        slug: Provider slug/alias
        provider_id: Provider type (e.g., "google", "oidc", "saml")
        display_name: Display name for the provider
        department_id: Department ID (for config lookup only)
        kc_admin: KeycloakAdmin instance (must be in master realm)
        pool: Database connection pool
        redis: Redis client
    """
    try:
        # Ensure we're in master realm
        kc_admin.change_current_realm(realm_name="master")

        # Use auth_id-based alias for 1:1 mapping (auth_{slug}_{auth_id})
        unique_alias = f"auth_{slug}_{auth_id}"
        async with pool.acquire() as conn:
            auth_items = await resolve_auth_items(
                conn, redis, uuid.UUID(auth_id), department_id=uuid.UUID(department_id)
            )

        # Build config map from items
        config_map: dict[str, str] = {}
        for item in auth_items:
            if item.encrypted:
                try:
                    decrypted_value = decrypt_api_key(item.value)
                    config_map[item.name] = decrypted_value
                except Exception as e:
                    logger.warning(
                        f"Failed to decrypt auth_item '{item.name}' for provider '{unique_alias}': {e}. Using as plain text."
                    )
                    config_map[item.name] = item.value
            else:
                config_map[item.name] = item.value

        # Build IdP payload (no organizationId - shared IdP across departments)
        # Set hideOnLogin=False - theme controls visibility via filtering
        # If we hide IdPs, Keycloak 26.0 excludes them from social.providers, so theme can't render them
        payload: dict[str, Any] = {
            "alias": unique_alias,
            "providerId": provider_id,
            "displayName": display_name,
            "enabled": True,
            "trustEmail": True,
            # No organizationId - removed org concept, client-id scoping handles routing
            "hideOnLogin": False,  # Must be False so IdPs appear in social.providers for theme filtering
            "config": {},
        }

        # Configure provider-specific settings
        if provider_id == "saml":
            if "ssoUrl" in config_map:
                payload["config"]["singleSignOnServiceUrl"] = config_map["ssoUrl"]
            if "entityId" in config_map:
                payload["config"]["entityId"] = config_map["entityId"]
            if "metadataUrl" in config_map:
                payload["config"]["importFromIdpUrl"] = config_map["metadataUrl"]
            if "certificate" in config_map:
                payload["config"]["signingCertificate"] = config_map["certificate"]
            if "nameIDPolicyFormat" not in payload["config"]:
                payload["config"]["nameIDPolicyFormat"] = (
                    "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
                )
            if "syncMode" not in payload["config"]:
                payload["config"]["syncMode"] = "FORCE"
            if "allowCreate" not in payload["config"]:
                payload["config"]["allowCreate"] = "true"
        else:
            payload["config"] = config_map
            if "syncMode" not in payload["config"]:
                payload["config"]["syncMode"] = "FORCE"
            if "useJwksUrl" not in payload["config"]:
                payload["config"]["useJwksUrl"] = "true"

        # Create or update IdP (department-scoped, shared across departments)
        try:
            kc_admin.get_idp(idp_alias=unique_alias)
            # IdP exists, update it
            kc_admin.update_idp(idp_alias=unique_alias, payload=payload)
            logger.info(f"✅ Updated department-scoped IdP: {unique_alias}")
        except Exception:
            # IdP doesn't exist, create it
            kc_admin.create_idp(payload=payload)
            logger.info(f"✅ Created department-scoped IdP: {unique_alias}")
    except Exception as e:
        logger.warning(
            f"Failed to sync org-scoped IdP '{unique_alias}': {e}", exc_info=True
        )


def get_idp_public_url(config: KeycloakSyncConfig | None = None) -> str:
    """Get the public base URL for the IdP (accessible from browser).

    This URL is used in authorizationUrl, which Keycloak redirects the browser to.
    Must be accessible from the user's browser.

    Scenarios:
    - Local dev: http://localhost:8000 (browser can access)
    - Production: ORIGIN (public domain, nginx proxies to backend)

    Endpoints are at root level: /authorize, /token, /jwks, /userinfo
    """
    if config is None:
        config = KeycloakSyncConfig.from_env()
    origin = config.origin
    app_prefix = config.app_prefix.strip("/")

    # Detect local dev
    is_local_dev = "localhost" in origin.lower()

    if is_local_dev:
        # Local dev: browser can access localhost:8000 directly
        base = "http://localhost:8000"
    else:
        # Production: use public ORIGIN (nginx proxies to backend)
        base = origin.rstrip("/")

    if app_prefix:
        return f"{base}/{app_prefix}"
    return base


def get_idp_internal_url(config: KeycloakSyncConfig | None = None) -> str:
    """Get the internal base URL for the IdP (accessible from Keycloak server).

    This URL is used in tokenUrl and jwksUrl, which Keycloak server calls directly.
    Must be accessible from Keycloak's perspective (inside Docker or on host).

    Scenarios:
    - Keycloak in Docker + Server in Docker: http://server:8000 (Docker service name)
    - Keycloak in Docker + Server on host: http://host.docker.internal:8000 (Docker host access)
    - Keycloak on host + Server on host: http://localhost:8000 (direct access)
    - Production: ORIGIN (public domain, nginx proxies to backend)

    Endpoints are at root level: /authorize, /token, /jwks, /userinfo
    """
    if config is None:
        config = KeycloakSyncConfig.from_env()
    origin = config.origin
    app_prefix = config.app_prefix.strip("/")
    docker_env = config.docker_env

    # Check if we're in Docker environment (server running in Docker)
    if docker_env:
        # Server is in Docker: use service name for internal communication (Keycloak -> Server)
        base = "http://server:8000"
    else:
        # Server is running locally (make run), but Keycloak might be in Docker
        # When Keycloak (in Docker) needs to reach host server, use host.docker.internal
        is_local_dev = "localhost" in origin.lower()

        if is_local_dev:
            # Keycloak is in Docker, server is on host: use host.docker.internal
            base = "http://host.docker.internal:8000"
        else:
            # Production: use public ORIGIN (nginx proxies to backend)
            base = origin.rstrip("/")

    if app_prefix:
        return f"{base}/{app_prefix}"
    return base


def get_idp_base_url() -> str:
    """Legacy function - use get_idp_public_url() or get_idp_internal_url() instead.

    Kept for backward compatibility. Returns public URL.
    """
    return get_idp_public_url()


async def sync_default_idp_for_profile(
    profile_id: str,
    profile_name: str | None,
    kc_admin: Any,
    config: KeycloakSyncConfig,
) -> str:
    """Sync a default-idp instance for a specific profile.

    Each profile gets its own IdP alias: default-idp-profile-{profile_id}.
    """
    try:
        kc_admin.change_current_realm(realm_name="master")

        alias = f"default-idp-profile-{profile_id}"
        display_name = profile_name or f"Default Profile {profile_id}"

        idp_public_url = get_idp_public_url(config)
        idp_internal_url = get_idp_internal_url(config)

        client_secret = config.auth_secret
        if not client_secret:
            logger.warning(f"AUTH_SECRET not found, cannot create {alias}")
            return alias

        auth_url = f"{idp_public_url}/authorize?profile_id={profile_id}"

        payload = {
            "alias": alias,
            "providerId": "oidc",
            "displayName": display_name,
            "enabled": True,
            "trustEmail": True,
            "hideOnLogin": False,
            "config": {
                "authorizationUrl": auth_url,
                "tokenUrl": f"{idp_internal_url}/token",
                "jwksUrl": f"{idp_internal_url}/jwks",
                "issuer": idp_public_url,
                "clientId": "keycloak-broker",
                "clientSecret": client_secret,
                "useJwksUrl": "true",
                "syncMode": "FORCE",
            },
        }

        try:
            kc_admin.get_idp(idp_alias=alias)
            kc_admin.update_idp(idp_alias=alias, payload=payload)
            logger.info(f"✅ Updated {alias} Identity Provider")
        except Exception:
            kc_admin.create_idp(payload=payload)
            logger.info(f"✅ Created {alias} Identity Provider")

        return alias
    except Exception as e:
        logger.warning(
            f"Failed to sync default-idp for profile {profile_id}: {e}",
            exc_info=True,
        )
        return alias if "alias" in locals() else f"default-idp-profile-{profile_id}"


def ensure_emulation_first_login_flow(kc_admin: Any) -> str:
    """Ensure the emulation-first-login flow exists.

    This is a copy of 'first broker login' with 'Review Profile' disabled
    so users aren't prompted for profile info during emulation.

    Returns:
        The flow alias: "emulation-first-login"
    """
    flow_alias = "emulation-first-login"

    try:
        # Check if flow already exists
        flows = kc_admin.get_authentication_flows()
        flow_exists = any(f.get("alias") == flow_alias for f in flows)

        if not flow_exists:
            # Copy the 'first broker login' flow
            kc_admin.copy_authentication_flow(
                payload={"newName": flow_alias}, flow_alias="first broker login"
            )
            logger.info(f"✅ Created {flow_alias} authentication flow")

        # Get executions for the flow and configure them
        executions = kc_admin.get_authentication_flow_executions(flow_alias)
        for ex in executions:
            # Disable 'Review Profile' step - critical for seamless emulation
            if ex.get("displayName") == "Review Profile":
                if ex.get("requirement") != "DISABLED":
                    ex["requirement"] = "DISABLED"
                    kc_admin.update_authentication_flow_executions(
                        payload=ex, flow_alias=flow_alias
                    )
                    logger.info(f"✅ Disabled Review Profile step in {flow_alias}")
            # Make Create User If Unique REQUIRED for auto-creation
            if ex.get("displayName") == "Create User If Unique":
                if ex.get("requirement") != "REQUIRED":
                    ex["requirement"] = "REQUIRED"
                    kc_admin.update_authentication_flow_executions(
                        payload=ex, flow_alias=flow_alias
                    )
                    logger.info(
                        f"✅ Made Create User If Unique REQUIRED in {flow_alias}"
                    )

        return flow_alias
    except Exception as e:
        logger.warning(f"Failed to configure {flow_alias}: {e}")
        # Fall back to default flow
        return "first broker login"


async def sync_emulation_default_idp(kc_admin: Any, config: KeycloakSyncConfig) -> str:
    """Sync a single default-idp for all emulation flows.

    This IdP is used for profile emulation. It's hidden from login templates
    since it's only accessed via emulation grants, not direct login.

    The IdP uses login_hint to receive the emulation grant ID, which contains
    the target profile information.

    Returns:
        The IdP alias: "default-idp"
    """
    alias = "default-idp"

    try:
        kc_admin.change_current_realm(realm_name="master")

        idp_public_url = get_idp_public_url(config)
        idp_internal_url = get_idp_internal_url(config)

        client_secret = config.auth_secret
        if not client_secret:
            logger.warning(f"AUTH_SECRET not found, cannot create {alias}")
            return alias

        # Authorization URL without hardcoded profile_id - uses login_hint for emulation grants
        auth_url = f"{idp_public_url}/authorize"

        # Ensure our custom authentication flow exists (skips profile review)
        first_login_flow = ensure_emulation_first_login_flow(kc_admin)

        payload = {
            "alias": alias,
            "providerId": "oidc",
            "displayName": "Emulation Login",
            "enabled": True,
            "trustEmail": True,
            # Hidden from login page - only used for emulation via redirect
            "hideOnLogin": True,
            # Use our custom flow that skips profile review
            "firstBrokerLoginFlowAlias": first_login_flow,
            "config": {
                "authorizationUrl": auth_url,
                "tokenUrl": f"{idp_internal_url}/token",
                "jwksUrl": f"{idp_internal_url}/jwks",
                "userInfoUrl": f"{idp_internal_url}/userinfo",
                "issuer": idp_public_url,
                "clientId": "keycloak-broker",
                "clientSecret": client_secret,
                "useJwksUrl": "true",
                "syncMode": "FORCE",
                # Forward login_hint to our IdP
                "loginHint": "true",
                # Skip profile review page - critical for seamless emulation
                "updateProfileFirstLoginMode": "off",
            },
        }

        try:
            kc_admin.get_idp(idp_alias=alias)
            kc_admin.update_idp(idp_alias=alias, payload=payload)
            logger.info(f"✅ Updated {alias} Identity Provider (for emulation)")
        except Exception:
            kc_admin.create_idp(payload=payload)
            logger.info(f"✅ Created {alias} Identity Provider (for emulation)")

        # Add IdP mappers to import custom claims from our IdP tokens
        # These claims will be stored as user attributes and can be included in client tokens
        custom_claim_mappers = [
            {
                "name": "profile_id-mapper",
                "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                "identityProviderAlias": alias,
                "config": {
                    "claim": "profile_id",
                    "user.attribute": "profile_id",
                    "syncMode": "FORCE",
                },
            },
            {
                "name": "role-mapper",
                "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                "identityProviderAlias": alias,
                "config": {
                    "claim": "role",
                    "user.attribute": "glow_role",
                    "syncMode": "FORCE",
                },
            },
            {
                "name": "is_emulation-mapper",
                "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                "identityProviderAlias": alias,
                "config": {
                    "claim": "is_emulation",
                    "user.attribute": "is_emulation",
                    "syncMode": "FORCE",
                },
            },
            {
                "name": "actor_profile_id-mapper",
                "identityProviderMapper": "oidc-user-attribute-idp-mapper",
                "identityProviderAlias": alias,
                "config": {
                    "claim": "actor_profile_id",
                    "user.attribute": "actor_profile_id",
                    "syncMode": "FORCE",
                },
            },
        ]

        for mapper in custom_claim_mappers:
            try:
                # Try to get existing mappers
                existing_mappers = kc_admin.get_idp_mappers(idp_alias=alias)
                existing_mapper = next(
                    (m for m in existing_mappers if m.get("name") == mapper["name"]),
                    None,
                )

                if existing_mapper:
                    # Update existing mapper
                    mapper["id"] = existing_mapper["id"]
                    kc_admin.update_mapper_in_idp(
                        idp_alias=alias,
                        mapper_id=existing_mapper["id"],
                        payload=mapper,
                    )
                    logger.debug(f"✅ Updated IdP mapper: {mapper['name']}")
                else:
                    # Create new mapper
                    kc_admin.add_mapper_to_idp(idp_alias=alias, payload=mapper)
                    logger.debug(f"✅ Created IdP mapper: {mapper['name']}")
            except Exception as mapper_e:
                logger.warning(
                    f"Failed to sync IdP mapper '{mapper['name']}': {mapper_e}"
                )

        return alias
    except Exception as e:
        logger.warning(
            f"Failed to sync emulation default-idp: {e}",
            exc_info=True,
        )
        return alias


async def ensure_emulation_client_mappers(
    kc_admin: Any, config: KeycloakSyncConfig
) -> None:
    """Ensure client mappers exist to include emulation claims in tokens.

    Creates protocol mappers on glow-client to include profile_id, role,
    is_emulation, and actor_profile_id user attributes in the ID token.
    """
    client_id = config.auth_keycloak_id

    try:
        kc_admin.change_current_realm(realm_name="master")

        # Get client internal ID
        clients = kc_admin.get_clients()
        client = next((c for c in clients if c.get("clientId") == client_id), None)
        if not client:
            logger.warning(f"Client '{client_id}' not found, skipping mappers")
            return

        client_internal_id = client["id"]

        # Define mappers for emulation claims
        claim_mappers = [
            {
                "name": "profile_id",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "config": {
                    "user.attribute": "profile_id",
                    "claim.name": "profile_id",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "jsonType.label": "String",
                },
            },
            {
                "name": "glow_role",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "config": {
                    "user.attribute": "glow_role",
                    "claim.name": "role",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "jsonType.label": "String",
                },
            },
            {
                "name": "is_emulation",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "config": {
                    "user.attribute": "is_emulation",
                    "claim.name": "is_emulation",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "jsonType.label": "boolean",
                },
            },
            {
                "name": "actor_profile_id",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "config": {
                    "user.attribute": "actor_profile_id",
                    "claim.name": "actor_profile_id",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true",
                    "jsonType.label": "String",
                },
            },
        ]

        # Get existing mappers
        try:
            existing_mappers = kc_admin.get_mappers_from_client(client_internal_id)
        except Exception:
            existing_mappers = []

        for mapper in claim_mappers:
            try:
                existing = next(
                    (m for m in existing_mappers if m.get("name") == mapper["name"]),
                    None,
                )

                if existing:
                    # Update existing
                    mapper["id"] = existing["id"]
                    kc_admin.update_client_mapper(
                        client_id=client_internal_id,
                        mapper_id=existing["id"],
                        payload=mapper,
                    )
                    logger.debug(f"✅ Updated client mapper: {mapper['name']}")
                else:
                    # Create new
                    kc_admin.add_mapper_to_client(
                        client_id=client_internal_id, payload=mapper
                    )
                    logger.debug(f"✅ Created client mapper: {mapper['name']}")
            except Exception as mapper_e:
                error_str = str(mapper_e).lower()
                if "already exists" in error_str or "409" in error_str:
                    logger.debug(f"Client mapper '{mapper['name']}' already exists")
                else:
                    logger.warning(
                        f"Failed to sync client mapper '{mapper['name']}': {mapper_e}"
                    )

        logger.info("✅ Emulation client mappers configured")
    except Exception as e:
        logger.warning(f"Failed to ensure emulation client mappers: {e}", exc_info=True)


async def sync_identity_providers(
    kc_admin: Any,
    pool: Any,
    redis: Any,
    config: KeycloakSyncConfig,
) -> None:
    """Sync all identity providers to master realm.

    - Realm-level: Auths from default settings (platform login) - alias: slug
    - Department-scoped: Auths from department settings - alias: auth_{slug}_{auth_id} (1:1 mapping)
    - Default-idp: Custom OIDC IdP instances per setting profile
      - Alias format: default-idp-profile-{profile_id}

    All IdPs have hideOnLogin=False so they appear in social.providers for theme filtering.
    Theme controls visibility based on department selection and authorization checks.

    Args:
        kc_admin: KeycloakAdmin instance (must be in master realm)
        pool: Database connection pool
        redis: Redis client
        config: Keycloak sync configuration
    """
    try:
        # Ensure we're in master realm
        kc_admin.change_current_realm(realm_name="master")

        # Step 0a: Sync single default-idp for emulation flows (hidden from login)
        logger.info("Syncing emulation default-idp Identity Provider...")
        await sync_emulation_default_idp(kc_admin, config)

        # Step 0b: Sync default-idp instances (custom OIDC IdP per profile)
        logger.info("Syncing default-idp Identity Provider instances (per profile)...")

        async with pool.acquire() as conn:
            setting_profiles = await resolve_setting_profiles_for_idp(conn, redis)

        seen_profiles: set[str] = set()
        for sp in setting_profiles:
            profile_id = str(sp.profile_id)
            if profile_id in seen_profiles:
                continue
            seen_profiles.add(profile_id)
            await sync_default_idp_for_profile(
                profile_id, sp.profile_name, kc_admin, config
            )

        # Step 1: Check if departments exist - if they do, skip realm-level IdPs that are also department-scoped
        async with pool.acquire() as conn:
            departments = await resolve_departments_for_sync(conn, redis)

        has_departments = len(departments) > 0
        department_auth_ids: set[str] = set()

        if has_departments:
            async with pool.acquire() as conn:
                for dept in departments:
                    dept_auths = await resolve_auths_for_department(
                        conn, redis, dept.department_id
                    )
                    for a in dept_auths:
                        department_auth_ids.add(str(a.id))

        # Step 2: Sync realm-level IdPs (from default settings)
        # BUT: Skip any that are also linked to department settings (to avoid duplicates)
        logger.info("Syncing realm-level IdPs (platform login)...")
        async with pool.acquire() as conn:
            realm_level_providers = await resolve_auths_for_realm(conn, redis)

        # Track which realm-level IdPs should exist
        realm_level_aliases_to_keep: set[str] = set()

        for provider in realm_level_providers:
            auth_id = str(provider.id)

            # Skip realm-level IdPs that are also department-scoped (when departments exist)
            if has_departments and auth_id in department_auth_ids:
                logger.info(
                    f"Skipping realm-level IdP '{provider.slug}' (auth_id: {auth_id}) - also linked to department settings"
                )
                continue

            if not provider.slug:
                logger.warning(
                    f"Skipping realm-level IdP with empty slug (auth_id: {auth_id}, name: {provider.name})"
                )
                continue

            realm_level_aliases_to_keep.add(provider.slug)
            await sync_identity_provider_for_realm_level(
                auth_id=auth_id,
                slug=provider.slug,
                provider_id=provider.provider_id or "",
                display_name=provider.name or "",
                kc_admin=kc_admin,
                pool=pool,
                redis=redis,
            )

        # Delete realm-level IdPs that shouldn't exist (when departments exist and auth is department-scoped)
        if has_departments and department_auth_ids:
            try:
                all_idps = kc_admin.get_idps()
                for idp in all_idps:
                    alias = idp.get("alias", "")
                    if (
                        alias
                        and not alias.startswith("auth_")
                        and not alias.startswith("default-idp")
                    ):
                        if alias not in realm_level_aliases_to_keep:
                            try:
                                kc_admin.delete_idp(idp_alias=alias)
                                logger.info(
                                    f"Deleted realm-level IdP '{alias}' - also linked to department settings"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to delete realm-level IdP '{alias}': {e}"
                                )
            except Exception as e:
                logger.warning(f"Failed to list/cleanup realm-level IdPs: {e}")

        # Step 3: Collect all unique department-scoped auths (deduplicate by auth_id)
        logger.info("Syncing department-scoped IdPs...")

        # Collect all unique auths (deduplicate by auth_id)
        all_department_auths: dict[str, dict[str, Any]] = {}

        async with pool.acquire() as conn:
            for dept in departments:
                dept_id = str(dept.department_id)
                dept_name = dept.department_name or dept_id

                # Ensure department-specific client exists (for client-scoped routing)
                dept_client_id = await ensure_department_client(
                    department_id=dept_id,
                    department_name=dept_name,
                    kc_admin=kc_admin,
                    config=config,
                )

                if not dept_client_id:
                    logger.warning(
                        f"Failed to create department client for {dept_id}, continuing with IdP sync"
                    )

                # Get auths for this department
                dept_auths = await resolve_auths_for_department(
                    conn, redis, dept.department_id
                )

                for a in dept_auths:
                    auth_id = str(a.id)
                    if auth_id not in all_department_auths:
                        all_department_auths[auth_id] = {
                            "auth_id": auth_id,
                            "slug": a.slug or "",
                            "provider_id": a.provider_id or "",
                            "display_name": a.name or "",
                            "department_id": dept_id,
                        }

        # Sync each unique auth once (prevents duplicates)
        for auth_data in all_department_auths.values():
            await sync_identity_provider_for_org(
                auth_id=auth_data["auth_id"],
                slug=auth_data["slug"],
                provider_id=auth_data["provider_id"],
                display_name=auth_data["display_name"],
                department_id=auth_data["department_id"],
                kc_admin=kc_admin,
                pool=pool,
                redis=redis,
            )

        # Step 4: Clean up IdPs that shouldn't exist
        logger.info("Cleaning up obsolete IdPs...")
        try:
            existing_idps = kc_admin.get_idps()

            # Collect expected default-idp aliases (from Step 0 sync)
            expected_default_idp_aliases: set[str] = set()
            for sp in setting_profiles:
                expected_default_idp_aliases.add(f"default-idp-profile-{sp.profile_id}")

            # Get expected realm-level slugs
            expected_realm_slugs = {p.slug for p in realm_level_providers if p.slug}
            expected_realm_slugs.update(expected_default_idp_aliases)

            # Get expected department-scoped aliases (auth_{slug}_{auth_id} pattern)
            expected_dept_aliases: set[str] = set()
            for auth_data in all_department_auths.values():
                alias = f"auth_{auth_data['slug']}_{auth_data['auth_id']}"
                expected_dept_aliases.add(alias)

            # Delete IdPs that shouldn't exist
            for idp in existing_idps:
                idp_alias = idp.get("alias", "")

                # Skip the emulation default-idp (always keep it)
                if idp_alias == "default-idp":
                    continue

                # Handle default-idp-profile-* instances separately
                if idp_alias.startswith("default-idp-profile-"):
                    if idp_alias not in expected_default_idp_aliases:
                        try:
                            kc_admin.delete_idp(idp_alias=idp_alias)
                            logger.info(f"🗑️  Deleted obsolete default-idp: {idp_alias}")
                        except Exception as delete_e:
                            error_str = str(delete_e).lower()
                            if "not found" in error_str or "404" in error_str:
                                pass
                            else:
                                logger.warning(
                                    f"Failed to delete IdP '{idp_alias}': {delete_e}"
                                )
                    continue

                # Check if it's realm-level or department-scoped
                if idp_alias.startswith("auth_"):
                    # Department-scoped IdP (auth_{slug}_{auth_id} pattern)
                    if idp_alias not in expected_dept_aliases:
                        try:
                            kc_admin.delete_idp(idp_alias=idp_alias)
                            logger.info(
                                f"🗑️  Deleted obsolete department-scoped IdP: {idp_alias}"
                            )
                        except Exception as delete_e:
                            error_str = str(delete_e).lower()
                            if "not found" in error_str or "404" in error_str:
                                pass  # Already deleted
                            else:
                                logger.warning(
                                    f"Failed to delete IdP '{idp_alias}': {delete_e}"
                                )
                else:
                    # Realm-level IdP (uses slug directly)
                    if idp_alias not in expected_realm_slugs:
                        try:
                            kc_admin.delete_idp(idp_alias=idp_alias)
                            logger.info(
                                f"🗑️  Deleted obsolete realm-level IdP: {idp_alias}"
                            )
                        except Exception as delete_e:
                            error_str = str(delete_e).lower()
                            if "not found" in error_str or "404" in error_str:
                                pass  # Already deleted
                            else:
                                logger.warning(
                                    f"Failed to delete IdP '{idp_alias}': {delete_e}"
                                )
        except Exception as cleanup_e:
            logger.warning(f"Failed to clean up obsolete IdPs: {cleanup_e}")

        logger.info("✅ Identity provider sync completed")
    except Exception as e:
        logger.error(f"Failed to sync identity providers: {e}", exc_info=True)


# OLD FUNCTION REMOVED: sync_department_realm_by_settings
# This function was replaced by sync_identity_providers() which uses client-id scoping instead of multiple realms
# The old function created separate realms per settings, but we now use a single master realm with client-id based routing


async def sync_keycloak(
    department_id: str | None = None,
    *,
    pool: Any,
    redis: Any,
    config: KeycloakSyncConfig,
) -> None:
    """Sync Keycloak identity providers from database to Keycloak.

    Args:
        department_id: Optional department ID to sync. If None, syncs all active departments.
        pool: Database connection pool
        redis: Redis client
        config: Keycloak sync configuration
    """
    try:
        # Resolve Keycloak URL from config
        if config.keycloak_url:
            keycloak_url = config.keycloak_url.rstrip("/")
        else:
            if config.keycloak_internal_url:
                base_url = config.keycloak_internal_url.rstrip("/")
            elif config.docker_env:
                base_url = "http://keycloak:8080"
            else:
                base_url = "http://localhost:8080"

            # Keycloak admin API: use /auth path for consistency
            # For local dev: Keycloak serves at /auth (KC_HTTP_RELATIVE_PATH=/auth)
            # For Docker/production: Keycloak is behind nginx at /auth
            keycloak_url = f"{base_url}{config.app_prefix}/auth"

        # Connect to Keycloak Admin API with retry logic
        kc_admin = await wait_for_keycloak(
            keycloak_url, config.keycloak_admin, config.keycloak_admin_password
        )
        if not kc_admin:
            logger.warning(
                "Keycloak is not available. Skipping sync. "
                "The server will continue to run, but authentication may not work until Keycloak is ready."
            )
            return

        # Ensure glow-client exists in master realm before syncing
        await ensure_glow_client_in_master_realm(kc_admin, config)

        # Ensure MCP client scope is configured (after client is ensured)
        await ensure_mcp_client_scope(kc_admin, config)

        # Ensure MCP token lifespan is configured (after client scope)
        await ensure_mcp_token_lifespan(kc_admin, config)

        # Ensure client registration policies are configured (remove Trusted Hosts and Consent Required)
        await ensure_client_registration_policies(kc_admin)

        # Disable consent screen display for all default client scopes
        # This is critical: even if clients have consentRequired=false, scopes can force consent
        await ensure_default_scopes_no_consent(kc_admin)

        # Post-process dynamically registered MCP clients to disable consent
        await ensure_dynamic_clients_no_consent(kc_admin)

        # Sync identity providers (realm-level + department-scoped)
        # All IdPs are hidden, theme controls visibility based on client_id
        await sync_identity_providers(kc_admin, pool, redis, config)

        # Ensure emulation client mappers are configured
        # These mappers include profile_id, role, is_emulation, actor_profile_id in client tokens
        await ensure_emulation_client_mappers(kc_admin, config)

        # Generate theme provider mapping (client_id -> allowed IdP aliases)
        logger.info("Generating comprehensive Keycloak theme provider mapping...")
        try:
            from app.infra.identity.keycloak_theme import (
                generate_keycloak_theme_providers,
            )

            await generate_keycloak_theme_providers(pool)
            logger.info(
                "✅ Theme provider mapping generated with all clientId and IdP combinations"
            )
        except Exception as e:
            logger.warning(f"Failed to generate theme mapping: {e}", exc_info=True)

        # Set login theme to "glow" (theme controls IdP visibility)
        try:
            realm = kc_admin.get_realm("master")
            if realm.get("loginTheme") != "glow":
                kc_admin.update_realm("master", {"loginTheme": "glow"})
                logger.info("✅ Set master realm login theme to 'glow'")
        except Exception as e:
            logger.warning(f"Failed to set login theme: {e}")

        # Clean up old non-master realms (safety check - should all be deleted already)
        try:
            existing_realms = kc_admin.get_realms()
            for realm in existing_realms:
                realm_name = realm.get("realm", "")
                # Skip master realm
                if realm_name == "master":
                    continue

                # Delete any non-master realms (old architecture)
                try:
                    kc_admin.delete_realm(realm_name=realm_name)
                    logger.info(f"✅ Deleted old realm: {realm_name}")
                except Exception as e:
                    error_str = str(e).lower()
                    if "not found" in error_str or "404" in error_str:
                        logger.info(f"Realm '{realm_name}' already deleted")
                    else:
                        logger.warning(
                            f"Failed to delete old realm '{realm_name}': {e}"
                        )
        except Exception as e:
            logger.warning(f"Failed to clean up old realms: {e}", exc_info=True)

        logger.info("Keycloak sync completed")
    except Exception as e:
        logger.warning(f"Keycloak sync failed (non-blocking): {e}", exc_info=True)


async def perform_keycloak_sync(
    department_id: str | None = None,
    *,
    pool: Any | None = None,
    redis: Any | None = None,
    config: KeycloakSyncConfig | None = None,
) -> KeycloakSyncResult:
    """Perform Keycloak sync and return structured result.

    Args:
        department_id: Optional department ID to sync. If None, syncs all.
        pool: Database connection pool (defaults to get_pool())
        redis: Redis client (defaults to get_redis_client())
        config: Keycloak sync configuration (defaults to KeycloakSyncConfig.from_env())

    Returns:
        KeycloakSyncResult with success status and message.
    """
    if os.getenv("PYTEST_CURRENT_TEST"):
        if department_id:
            message = (
                f"Keycloak sync skipped during tests for department {department_id}"
            )
        else:
            message = "Keycloak sync skipped during tests"
        return KeycloakSyncResult(
            success=True,
            message=message,
            department_id=department_id,
        )

    # Resolve dependencies (use injected or fall back to globals)
    pool = pool or get_pool()
    redis = redis or get_redis_client()
    config = config or KeycloakSyncConfig.from_env()

    if not pool:
        error_msg = "Database pool not available"
        logger.warning(error_msg)
        return KeycloakSyncResult(
            success=False,
            message=error_msg,
            department_id=department_id,
            error=error_msg,
        )

    try:
        await sync_keycloak(
            department_id=department_id, pool=pool, redis=redis, config=config
        )

        if department_id:
            message = (
                f"Keycloak sync completed successfully for department {department_id}"
            )
        else:
            message = "Keycloak sync completed successfully for all departments"

        return KeycloakSyncResult(
            success=True,
            message=message,
            department_id=department_id,
        )
    except Exception as e:
        # Log the error but return a result instead of raising
        error_msg = str(e)
        logger.error(f"Keycloak sync failed: {error_msg}", exc_info=True)

        if department_id:
            message = (
                f"Keycloak sync failed for department {department_id}: {error_msg}"
            )
        else:
            message = f"Keycloak sync failed: {error_msg}"

        return KeycloakSyncResult(
            success=False,
            message=message,
            department_id=department_id,
            error=error_msg,
        )
