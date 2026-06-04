"""Tests for ``app.infra.identity.keycloak_theme``.

This module generates two artifacts from the database:
  - ``login/providers.ftl`` (department → allowed-IdP-alias map), via
    ``generate_keycloak_theme_providers``.
  - ``login/resources/css/theme-vars.css`` (per-department palettes),
    via ``generate_keycloak_theme_styles``.

The DB resolvers are monkeypatched at module scope (mirroring the
keycloak_sync test precedent) and ``UPLOAD_FOLDER`` is redirected to a
tmp dir so the generators write into a sandbox. Theme *token* math
(``derive_theme_tokens``) is tested in ``tests/utils/settings/test_theme.py``;
here we own the FreeMarker/CSS *emission* contract.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.infra.identity import keycloak_theme


# ── FakePool (mirrors keycloak_sync test harness) ──


class FakeConn:
    async def execute(self, sql, *args):  # pragma: no cover - unused here
        return None


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn=None):
        self.conn = conn or FakeConn()

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.fixture
def theme_sandbox(monkeypatch, tmp_path):
    """Redirect UPLOAD_FOLDER + stub redis so generators write to tmp."""
    monkeypatch.setattr(keycloak_theme, "UPLOAD_FOLDER", tmp_path)
    monkeypatch.setattr(keycloak_theme, "get_redis_client", lambda: object())
    return tmp_path


# ── _escape_ftl_string (pure) ──


def test_escape_ftl_string_escapes_quotes_backslashes_and_newlines():
    raw = 'a "quote" and \\ slash\nnewline\rcarriage'
    escaped = keycloak_theme._escape_ftl_string(raw)
    # ``\`` → ``\\``, ``"`` → ``\"``, ``\n`` → single space, ``\r`` dropped.
    assert escaped == 'a \\"quote\\" and \\\\ slash newlinecarriage'
    # No raw double-quote, no bare newline/carriage survive.
    assert "\n" not in escaped
    assert "\r" not in escaped


def test_escape_ftl_string_is_noop_for_plain_text():
    assert keycloak_theme._escape_ftl_string("plain") == "plain"


# ── generate_keycloak_theme_providers ──


@pytest.mark.asyncio
async def test_generate_providers_maps_departments_to_allowed_idp_aliases(
    monkeypatch, theme_sandbox
):
    dept_id = "11111111-1111-1111-1111-111111111111"
    auth_id = "22222222-2222-2222-2222-222222222222"
    profile_id = "33333333-3333-3333-3333-333333333333"

    async def _realm_auths(conn, redis):
        return [SimpleNamespace(slug="okta")]

    async def _realm_logins(conn, redis):
        return []

    async def _setting_profiles(conn, redis):
        return [
            SimpleNamespace(
                profile_id=UUID(profile_id),
                department_id=UUID(dept_id),
            )
        ]

    async def _departments(conn, redis):
        return [
            SimpleNamespace(
                department_id=UUID(dept_id),
                department_name="Operations",
            )
        ]

    async def _dept_logins(conn, redis, department_id):
        return []

    async def _dept_auths(conn, redis, department_id):
        return [SimpleNamespace(slug="saml", id=UUID(auth_id))]

    monkeypatch.setattr(keycloak_theme, "resolve_auths_for_realm", _realm_auths)
    monkeypatch.setattr(keycloak_theme, "resolve_logins_for_realm", _realm_logins)
    monkeypatch.setattr(
        keycloak_theme, "resolve_setting_profiles_for_idp", _setting_profiles
    )
    monkeypatch.setattr(
        keycloak_theme, "resolve_departments_for_sync", _departments
    )
    monkeypatch.setattr(
        keycloak_theme, "resolve_logins_for_department", _dept_logins
    )
    monkeypatch.setattr(
        keycloak_theme, "resolve_auths_for_department", _dept_auths
    )

    await keycloak_theme.generate_keycloak_theme_providers(FakePool())

    out = (theme_sandbox / "themes/glow/login/providers.ftl").read_text()

    # Department appears in the picker array.
    assert f'{{"id": "{dept_id}", "title": "Operations"}}' in out
    # The department maps to BOTH its scoped auth alias and the
    # profile-scoped default-idp alias.
    assert f"auth_saml_{auth_id}" in out
    assert f"default-idp-profile-{profile_id}" in out
    # Realm-level (platform) auth slug is emitted as a platform provider.
    assert "platformProviders" in out
    assert '"okta"' in out
    # The lookup function is generated.
    assert "<#function getAllowedProvidersForDepartment deptId>" in out


@pytest.mark.asyncio
async def test_generate_providers_uses_platform_profiles_when_no_departments(
    monkeypatch, theme_sandbox
):
    profile_id = "44444444-4444-4444-4444-444444444444"

    async def _realm_auths(conn, redis):
        return []

    async def _realm_logins(conn, redis):
        return []

    async def _setting_profiles(conn, redis):
        # Platform-level profile (no department scope).
        return [SimpleNamespace(profile_id=UUID(profile_id), department_id=None)]

    async def _departments(conn, redis):
        return []

    monkeypatch.setattr(keycloak_theme, "resolve_auths_for_realm", _realm_auths)
    monkeypatch.setattr(keycloak_theme, "resolve_logins_for_realm", _realm_logins)
    monkeypatch.setattr(
        keycloak_theme, "resolve_setting_profiles_for_idp", _setting_profiles
    )
    monkeypatch.setattr(
        keycloak_theme, "resolve_departments_for_sync", _departments
    )

    await keycloak_theme.generate_keycloak_theme_providers(FakePool())

    out = (theme_sandbox / "themes/glow/login/providers.ftl").read_text()
    # With zero departments, the platform-level profile alias becomes a
    # platform provider.
    assert f"default-idp-profile-{profile_id}" in out
    assert "platformProviders" in out


# ── generate_keycloak_theme_styles ──


@pytest.mark.asyncio
async def test_generate_styles_emits_root_and_dark_blocks_from_active_setting(
    monkeypatch, theme_sandbox
):
    from app.utils.settings.theme import ThemePrimitives

    dept_id = "55555555-5555-5555-5555-555555555555"
    setting_resource_id = UUID("66666666-6666-6666-6666-666666666666")

    async def _departments(conn, redis):
        return [SimpleNamespace(department_id=UUID(dept_id))]

    async def _resolve_setting_id(conn, redis, department_artifact_id):
        return setting_resource_id

    light = ThemePrimitives(primary="#ff0000", background="#ffffff")
    dark = ThemePrimitives(primary="#ff0000", background="#000000")

    async def _resolve_theme(pool, redis, resource_id):
        assert resource_id == setting_resource_id
        return SimpleNamespace(is_active=True, light=light, dark=dark)

    monkeypatch.setattr(
        keycloak_theme, "resolve_departments_for_sync", _departments
    )
    monkeypatch.setattr(
        keycloak_theme,
        "_resolve_dept_setting_resource_id",
        _resolve_setting_id,
    )
    # resolve_settings_theme is lazily imported from app.infra.identity.settings.
    monkeypatch.setattr(
        "app.infra.identity.settings.resolve_settings_theme", _resolve_theme
    )

    await keycloak_theme.generate_keycloak_theme_styles(FakePool())

    out = (
        theme_sandbox / "themes/glow/login/resources/css/theme-vars.css"
    ).read_text()

    # Platform default :root block exists with kebab-cased CSS vars.
    assert ":root {" in out
    assert "--primary:" in out
    assert "--background:" in out
    # Dark variant emitted via prefers-color-scheme + explicit .dark class.
    assert "@media (prefers-color-scheme: dark)" in out
    assert ":root.dark {" in out
    # Per-department scoped block keyed by data-department-id.
    assert f'[data-department-id="{dept_id}"]' in out


@pytest.mark.asyncio
async def test_generate_styles_skips_inactive_or_primaryless_settings(
    monkeypatch, theme_sandbox
):
    from app.utils.settings.theme import ThemePrimitives

    dept_id = "77777777-7777-7777-7777-777777777777"

    async def _departments(conn, redis):
        return [SimpleNamespace(department_id=UUID(dept_id))]

    async def _resolve_setting_id(conn, redis, department_artifact_id):
        return UUID("88888888-8888-8888-8888-888888888888")

    async def _resolve_theme(pool, redis, resource_id):
        # Inactive setting → contributes no palette.
        return SimpleNamespace(
            is_active=False,
            light=ThemePrimitives(primary="#ff0000"),
            dark=ThemePrimitives(primary="#ff0000"),
        )

    monkeypatch.setattr(
        keycloak_theme, "resolve_departments_for_sync", _departments
    )
    monkeypatch.setattr(
        keycloak_theme,
        "_resolve_dept_setting_resource_id",
        _resolve_setting_id,
    )
    monkeypatch.setattr(
        "app.infra.identity.settings.resolve_settings_theme", _resolve_theme
    )

    await keycloak_theme.generate_keycloak_theme_styles(FakePool())

    out = (
        theme_sandbox / "themes/glow/login/resources/css/theme-vars.css"
    ).read_text()
    # No palette → no :root token block and no department block.
    assert ":root {" not in out
    assert f'[data-department-id="{dept_id}"]' not in out
