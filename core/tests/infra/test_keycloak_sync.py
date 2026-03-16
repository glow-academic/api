from __future__ import annotations

import sys
import types
import uuid

import pytest

from app.infra.identity import keycloak_sync
from app.infra.identity.keycloak_sync import KeycloakSyncConfig


def make_config(**overrides) -> KeycloakSyncConfig:
    """Create a test config with sensible defaults."""
    defaults = {
        "auth_keycloak_id": "glow-client",
        "auth_keycloak_secret": "secret",
        "client_port": "3000",
        "app_prefix": "",
        "origin": "http://localhost:3000",
        "auth_secret": "test-secret",
        "keycloak_url": None,
        "keycloak_internal_url": None,
        "keycloak_admin": "admin",
        "keycloak_admin_password": "admin",
        "docker_env": None,
        "mcp_token_lifespan": 86400,
    }
    defaults.update(overrides)
    return KeycloakSyncConfig(**defaults)


class FakeConn:
    def __init__(self, fetch_result=None):
        self.fetch_result = fetch_result or []
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, sql, *args):
        self.executed.append((sql, args))

    async def fetch(self, sql, *args):
        self.executed.append((sql, args))
        return self.fetch_result


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


class FakeKCAdmin:
    def __init__(self):
        self.current_realm = None
        self.updated_clients: list[tuple[str, dict]] = []
        self.created_clients: list[tuple[dict, bool]] = []
        self.updated_realms: list[tuple[str, dict]] = []
        self.deleted_components: list[str] = []
        self.added_mapper_payloads: list[tuple[str, dict]] = []
        self.updated_mapper_payloads: list[tuple[str, str, dict]] = []
        self.added_realm_default_scope_ids: list[str] = []
        self.added_client_default_scope_ids: list[tuple[str, str, dict]] = []
        self.updated_client_scopes: list[tuple[str, dict]] = []
        self.idps_created: list[dict] = []
        self.idps_updated: list[tuple[str, dict]] = []
        self.deleted_idps: list[str] = []
        self.deleted_realms: list[str] = []
        self.copied_flows: list[tuple[dict, str]] = []
        self.updated_flow_executions: list[tuple[str, dict]] = []
        self.updated_client_mappers: list[tuple[str, str, dict]] = []
        self.added_client_mappers: list[tuple[str, dict]] = []
        self.updated_idp_mappers: list[tuple[str, str, dict]] = []
        self.added_idp_mappers: list[tuple[str, dict]] = []
        self.clients = []
        self.client_scopes = []
        self.realm_default_scopes = []
        self.client_default_scopes = []
        self.components = []
        self.realms = [{"realm": "master"}]
        self.auth_flows = []
        self.flow_executions: dict[str, list[dict]] = {}
        self.client_mappers: dict[str, list[dict]] = {}
        self.idp_mappers: dict[str, list[dict]] = {}
        self.realm = {
            "id": "realm-id",
            "accessTokenLifespan": 60,
            "sslRequired": "EXTERNAL",
        }
        self.scope_mappers: dict[str, list[dict]] = {}
        self.idps: dict[str, dict] = {}

    def get_realms(self):
        return list(self.realms)

    def change_current_realm(self, realm_name):
        self.current_realm = realm_name

    def get_realm(self, realm_name):
        return dict(self.realm)

    def update_realm(self, realm_name, payload):
        self.updated_realms.append((realm_name, payload))
        self.realm.update(payload)

    def get_clients(self):
        return list(self.clients)

    def update_client(self, client_id, payload):
        self.updated_clients.append((client_id, payload))

    def create_client(self, payload, skip_exists=True):
        self.created_clients.append((payload, skip_exists))
        return "new-client-uuid"

    def get_client_scopes(self):
        return list(self.client_scopes)

    def create_client_scope(self, payload, skip_exists=True):
        self.client_scopes.append({"id": "scope-id", "name": payload["name"]})
        return "scope-id"

    def update_client_scope(self, client_scope_id, payload):
        self.updated_client_scopes.append((client_scope_id, payload))

    def get_mappers_from_client_scope(self, scope_id):
        return list(self.scope_mappers.get(scope_id, []))

    def update_mapper_in_client_scope(
        self, client_scope_id, protocol_mapper_id, payload
    ):
        self.updated_mapper_payloads.append(
            (client_scope_id, protocol_mapper_id, payload)
        )

    def add_mapper_to_client_scope(self, client_scope_id, payload):
        self.added_mapper_payloads.append((client_scope_id, payload))

    def get_realm_default_client_scopes(self):
        return list(self.realm_default_scopes)

    def add_default_default_client_scope(self, scope_id):
        self.added_realm_default_scope_ids.append(scope_id)

    def get_client_default_client_scopes(self, client_id):
        return list(self.client_default_scopes)

    def add_client_default_client_scope(self, client_id, client_scope_id, payload):
        self.added_client_default_scope_ids.append(
            (client_id, client_scope_id, payload)
        )

    def get_components(self, query=None):
        return list(self.components)

    def delete_component(self, component_id):
        self.deleted_components.append(component_id)

    def get_idp(self, idp_alias):
        if idp_alias not in self.idps:
            raise KeyError(idp_alias)
        return self.idps[idp_alias]

    def update_idp(self, idp_alias, payload):
        self.idps_updated.append((idp_alias, payload))

    def create_idp(self, payload):
        self.idps_created.append(payload)
        self.idps[payload["alias"]] = payload

    def get_idps(self):
        return [{"alias": alias} for alias in self.idps]

    def delete_idp(self, idp_alias):
        self.deleted_idps.append(idp_alias)
        self.idps.pop(idp_alias, None)

    def delete_realm(self, realm_name):
        self.deleted_realms.append(realm_name)

    def get_authentication_flows(self):
        return list(self.auth_flows)

    def copy_authentication_flow(self, payload, flow_alias):
        self.copied_flows.append((payload, flow_alias))
        self.auth_flows.append({"alias": payload["newName"]})

    def get_authentication_flow_executions(self, flow_alias):
        return [dict(ex) for ex in self.flow_executions.get(flow_alias, [])]

    def update_authentication_flow_executions(self, payload, flow_alias):
        self.updated_flow_executions.append((flow_alias, dict(payload)))

    def get_idp_mappers(self, idp_alias):
        return list(self.idp_mappers.get(idp_alias, []))

    def update_mapper_in_idp(self, idp_alias, mapper_id, payload):
        self.updated_idp_mappers.append((idp_alias, mapper_id, payload))

    def add_mapper_to_idp(self, idp_alias, payload):
        self.added_idp_mappers.append((idp_alias, payload))

    def get_mappers_from_client(self, client_id):
        return list(self.client_mappers.get(client_id, []))

    def update_client_mapper(self, client_id, mapper_id, payload):
        self.updated_client_mappers.append((client_id, mapper_id, payload))

    def add_mapper_to_client(self, client_id, payload):
        self.added_client_mappers.append((client_id, payload))


@pytest.mark.asyncio
async def test_wait_for_keycloak_connects(monkeypatch):
    kc_admin = FakeKCAdmin()

    class FakeKeycloakAdmin:
        def __new__(cls, *args, **kwargs):
            return kc_admin

    module = types.SimpleNamespace(KeycloakAdmin=FakeKeycloakAdmin)
    monkeypatch.setitem(sys.modules, "keycloak", module)

    result = await keycloak_sync.wait_for_keycloak(
        "http://keycloak:8080", "admin", "password", max_retries=1
    )

    assert result is kc_admin


@pytest.mark.asyncio
async def test_wait_for_keycloak_returns_none_when_package_missing(monkeypatch):
    monkeypatch.delitem(sys.modules, "keycloak", raising=False)
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "keycloak":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    assert (
        await keycloak_sync.wait_for_keycloak(
            "http://keycloak:8080", "admin", "password", max_retries=1
        )
        is None
    )


@pytest.mark.asyncio
async def test_ensure_department_client_updates_existing_client():
    admin = FakeKCAdmin()
    admin.clients = [{"clientId": "glow-client-dept-1", "id": "client-uuid"}]
    config = make_config()

    result = await keycloak_sync.ensure_department_client(
        "dept-1", "Operations", admin, config
    )

    assert result == "glow-client-dept-1"
    assert admin.updated_clients
    assert admin.updated_clients[0][0] == "client-uuid"


@pytest.mark.asyncio
async def test_ensure_department_client_creates_new_client():
    admin = FakeKCAdmin()
    config = make_config()

    result = await keycloak_sync.ensure_department_client(
        "dept-2", "People", admin, config
    )

    assert result == "glow-client-dept-2"
    assert admin.created_clients
    assert admin.updated_clients[-1][1] == {"secret": "secret"}


@pytest.mark.asyncio
async def test_ensure_glow_client_in_master_realm_creates_client():
    admin = FakeKCAdmin()
    config = make_config()

    await keycloak_sync.ensure_glow_client_in_master_realm(admin, config)

    assert admin.created_clients
    assert admin.updated_clients[-1][1] == {"secret": "secret"}


@pytest.mark.asyncio
async def test_ensure_mcp_client_scope_creates_scope_mapper_and_assignments(
    monkeypatch,
):
    admin = FakeKCAdmin()
    admin.clients = [{"clientId": "glow-client", "id": "client-1"}]
    config = make_config()
    monkeypatch.setattr(keycloak_sync, "is_mcp_enabled", lambda: True)

    await keycloak_sync.ensure_mcp_client_scope(admin, config)

    assert admin.added_mapper_payloads
    assert admin.added_realm_default_scope_ids == ["scope-id"]
    assert admin.added_client_default_scope_ids == [("client-1", "scope-id", {})]


@pytest.mark.asyncio
async def test_ensure_mcp_token_lifespan_updates_master_realm(monkeypatch):
    admin = FakeKCAdmin()
    config = make_config(mcp_token_lifespan=7200)
    monkeypatch.setattr(keycloak_sync, "is_mcp_enabled", lambda: True)

    await keycloak_sync.ensure_mcp_token_lifespan(admin, config)

    assert ("master", {"accessTokenLifespan": 7200}) in admin.updated_realms


@pytest.mark.asyncio
async def test_ensure_client_registration_policies_removes_blocking_components():
    admin = FakeKCAdmin()
    admin.components = [
        {
            "id": "trusted-1",
            "providerId": "trusted-hosts",
            "subType": "anonymous",
            "providerType": "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy",
        },
        {
            "id": "consent-1",
            "providerId": "consent-required",
            "subType": "anonymous",
            "providerType": "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy",
        },
    ]

    await keycloak_sync.ensure_client_registration_policies(admin)

    assert admin.deleted_components == ["trusted-1", "consent-1"]


@pytest.mark.asyncio
async def test_ensure_dynamic_clients_no_consent_updates_matching_clients(monkeypatch):
    admin = FakeKCAdmin()
    admin.clients = [
        {
            "clientId": "ChatGPT-123",
            "id": "chatgpt-id",
            "consentRequired": True,
            "redirectUris": ["https://chatgpt.com/callback"],
        },
        {
            "clientId": "glow-client",
            "id": "managed-id",
            "consentRequired": True,
            "redirectUris": [],
        },
        {
            "clientId": "123e4567-e89b-12d3-a456-426614174000",
            "id": "uuid-id",
            "consentRequired": True,
            "redirectUris": ["cursor://callback"],
        },
    ]
    monkeypatch.setattr(keycloak_sync, "is_mcp_enabled", lambda: True)

    await keycloak_sync.ensure_dynamic_clients_no_consent(admin)

    updated_ids = [client_id for client_id, _ in admin.updated_clients]
    assert "chatgpt-id" in updated_ids
    assert "uuid-id" in updated_ids
    assert "managed-id" not in updated_ids


@pytest.mark.asyncio
async def test_ensure_default_scopes_no_consent_updates_scope_attributes():
    admin = FakeKCAdmin()
    admin.client_scopes = [
        {"id": "scope-1", "name": "profile", "attributes": {}},
        {"id": "scope-2", "name": "email", "attributes": {}},
        {"id": "scope-3", "name": "custom-unrelated", "attributes": {}},
    ]

    await keycloak_sync.ensure_default_scopes_no_consent(admin)

    # Should update profile and email scopes (they're in the target set)
    updated_scope_ids = [scope_id for scope_id, _ in admin.updated_client_scopes]
    assert "scope-1" in updated_scope_ids
    assert "scope-2" in updated_scope_ids
    # Should NOT update custom-unrelated (not in the target set)
    assert "scope-3" not in updated_scope_ids


def test_get_idp_urls_cover_local_and_docker_variants():
    local = make_config(origin="http://localhost:3000", app_prefix="v5")
    prod = make_config(origin="https://glow.example.com", app_prefix="app")
    docker = make_config(origin="http://localhost:3000", docker_env="1")

    assert keycloak_sync.get_idp_public_url(local) == "http://localhost:8000/v5"
    assert (
        keycloak_sync.get_idp_internal_url(local)
        == "http://host.docker.internal:8000/v5"
    )
    assert (
        keycloak_sync.get_idp_public_url(prod) == "https://glow.example.com/app"
    )
    assert (
        keycloak_sync.get_idp_internal_url(prod) == "https://glow.example.com/app"
    )
    assert keycloak_sync.get_idp_internal_url(docker) == "http://server:8000"
    assert keycloak_sync.get_idp_base_url() == keycloak_sync.get_idp_public_url()


@pytest.mark.asyncio
async def test_sync_default_idp_for_profile_creates_profile_specific_idp():
    admin = FakeKCAdmin()
    config = make_config(auth_secret="broker-secret", app_prefix="auth")

    alias = await keycloak_sync.sync_default_idp_for_profile(
        "123e4567-e89b-12d3-a456-426614174000",
        "Ops Profile",
        admin,
        config,
    )

    assert alias == "default-idp-profile-123e4567-e89b-12d3-a456-426614174000"
    created = admin.idps_created[-1]
    assert created["alias"] == alias
    assert (
        created["config"]["authorizationUrl"]
        == "http://localhost:8000/auth/authorize?profile_id=123e4567-e89b-12d3-a456-426614174000"
    )
    assert created["config"]["tokenUrl"] == "http://host.docker.internal:8000/auth/token"


def test_ensure_emulation_first_login_flow_copies_and_reconfigures_review_steps():
    admin = FakeKCAdmin()
    admin.auth_flows = [{"alias": "first broker login"}]
    admin.flow_executions["emulation-first-login"] = [
        {"displayName": "Review Profile", "requirement": "REQUIRED"},
        {"displayName": "Create User If Unique", "requirement": "ALTERNATIVE"},
    ]

    alias = keycloak_sync.ensure_emulation_first_login_flow(admin)

    assert alias == "emulation-first-login"
    assert admin.copied_flows == [
        ({"newName": "emulation-first-login"}, "first broker login")
    ]
    updated = {(flow_alias, payload["displayName"], payload["requirement"]) for flow_alias, payload in admin.updated_flow_executions}
    assert ("emulation-first-login", "Review Profile", "DISABLED") in updated
    assert ("emulation-first-login", "Create User If Unique", "REQUIRED") in updated


@pytest.mark.asyncio
async def test_sync_emulation_default_idp_creates_idp_and_claim_mappers():
    admin = FakeKCAdmin()
    admin.auth_flows = [{"alias": "emulation-first-login"}]
    admin.flow_executions["emulation-first-login"] = []
    config = make_config(auth_secret="broker-secret")

    alias = await keycloak_sync.sync_emulation_default_idp(admin, config)

    assert alias == "default-idp"
    assert admin.idps_created[-1]["config"]["loginHint"] == "true"
    mapper_names = [payload["name"] for _, payload in admin.added_idp_mappers]
    assert mapper_names == [
        "profile_id-mapper",
        "role-mapper",
        "is_emulation-mapper",
        "actor_profile_id-mapper",
    ]


@pytest.mark.asyncio
async def test_ensure_emulation_client_mappers_creates_missing_mappers():
    admin = FakeKCAdmin()
    admin.clients = [{"clientId": "glow-client", "id": "client-1"}]
    config = make_config()

    await keycloak_sync.ensure_emulation_client_mappers(admin, config)

    assert [payload["name"] for _, payload in admin.added_client_mappers] == [
        "profile_id",
        "glow_role",
        "is_emulation",
        "actor_profile_id",
    ]


@pytest.mark.asyncio
async def test_sync_identity_provider_for_realm_level_builds_saml_payload(monkeypatch):
    admin = FakeKCAdmin()
    conn = FakeConn()
    pool = FakePool(conn)
    items = [
        types.SimpleNamespace(name="ssoUrl", value="https://sso", encrypted=False),
        types.SimpleNamespace(name="entityId", value="entity", encrypted=False),
        types.SimpleNamespace(name="metadataUrl", value="https://meta", encrypted=False),
        types.SimpleNamespace(name="certificate", value="cert", encrypted=False),
    ]
    async def _resolve_auth_items(conn, redis, auth_id, department_id=None):
        return items

    monkeypatch.setattr(keycloak_sync, "resolve_auth_items", _resolve_auth_items)

    await keycloak_sync.sync_identity_provider_for_realm_level(
        auth_id=str(uuid.uuid4()),
        slug="saml-login",
        provider_id="saml",
        display_name="SAML Login",
        kc_admin=admin,
        pool=pool,
        redis=None,
    )

    payload = admin.idps_created[-1]
    assert payload["alias"] == "saml-login"
    assert payload["config"]["singleSignOnServiceUrl"] == "https://sso"
    assert payload["config"]["entityId"] == "entity"
    assert payload["config"]["importFromIdpUrl"] == "https://meta"
    assert payload["config"]["signingCertificate"] == "cert"


@pytest.mark.asyncio
async def test_sync_identity_provider_for_org_uses_auth_scoped_alias(monkeypatch):
    admin = FakeKCAdmin()
    conn = FakeConn()
    pool = FakePool(conn)
    auth_id = str(uuid.uuid4())
    department_id = str(uuid.uuid4())
    items = [types.SimpleNamespace(name="issuer", value="https://issuer", encrypted=False)]
    async def _resolve_auth_items(conn, redis, auth_uuid, department_id=None):
        return items

    monkeypatch.setattr(keycloak_sync, "resolve_auth_items", _resolve_auth_items)

    await keycloak_sync.sync_identity_provider_for_org(
        auth_id=auth_id,
        slug="google",
        provider_id="oidc",
        display_name="Google",
        department_id=department_id,
        kc_admin=admin,
        pool=pool,
        redis=None,
    )

    payload = admin.idps_created[-1]
    assert payload["alias"] == f"auth_google_{auth_id}"
    assert payload["config"]["issuer"] == "https://issuer"
    assert payload["config"]["syncMode"] == "FORCE"
    assert payload["config"]["useJwksUrl"] == "true"


@pytest.mark.asyncio
async def test_sync_keycloak_runs_full_orchestration(monkeypatch):
    admin = FakeKCAdmin()
    config = make_config(keycloak_url="http://kc/auth")
    calls: list[str] = []

    async def _wait(url, admin_user, password):
        calls.append(f"wait:{url}")
        return admin

    def _record(name):
        async def _inner(*args, **kwargs):
            calls.append(name)
            return None

        return _inner

    monkeypatch.setattr(keycloak_sync, "wait_for_keycloak", _wait)
    monkeypatch.setattr(keycloak_sync, "ensure_glow_client_in_master_realm", _record("glow"))
    monkeypatch.setattr(keycloak_sync, "ensure_mcp_client_scope", _record("mcp_scope"))
    monkeypatch.setattr(keycloak_sync, "ensure_mcp_token_lifespan", _record("mcp_lifespan"))
    monkeypatch.setattr(keycloak_sync, "ensure_client_registration_policies", _record("registration"))
    monkeypatch.setattr(keycloak_sync, "ensure_default_scopes_no_consent", _record("scopes"))
    monkeypatch.setattr(keycloak_sync, "ensure_dynamic_clients_no_consent", _record("dynamic"))
    monkeypatch.setattr(keycloak_sync, "sync_identity_providers", _record("idps"))
    monkeypatch.setattr(keycloak_sync, "ensure_emulation_client_mappers", _record("client_mappers"))

    async def _theme(pool):
        calls.append("theme")

    monkeypatch.setattr("app.infra.identity.keycloak_theme.generate_keycloak_theme_providers", _theme)

    await keycloak_sync.sync_keycloak(pool=object(), redis=None, config=config)

    assert calls[:3] == ["wait:http://kc/auth", "glow", "mcp_scope"]
    assert "idps" in calls
    assert "client_mappers" in calls
    assert "theme" in calls


@pytest.mark.asyncio
async def test_perform_keycloak_sync_handles_missing_pool_and_failure(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(keycloak_sync, "get_pool", lambda: None)

    result = await keycloak_sync.perform_keycloak_sync(
        department_id="dept-1",
        pool=None,
        redis=None,
        config=make_config(),
    )
    assert result.success is False
    assert result.error == "Database pool not available"

    async def _sync_keycloak(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(keycloak_sync, "sync_keycloak", _sync_keycloak)

    result = await keycloak_sync.perform_keycloak_sync(
        department_id="dept-2",
        pool=object(),
        redis=None,
        config=make_config(),
    )
    assert result.success is False
    assert result.error == "boom"
    assert "dept-2" in result.message
