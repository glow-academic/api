from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.identity import keycloak_theme


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _Pool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AcquireContext(self._conn)


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


pytestmark = pytest.mark.asyncio


async def test_generate_keycloak_theme_providers_writes_department_mapping(
    monkeypatch,
    tmp_path,
):
    department_id = uuid4()
    auth_id = uuid4()
    profile_id = uuid4()

    monkeypatch.setattr(keycloak_theme, "UPLOAD_FOLDER", tmp_path)
    monkeypatch.setattr(keycloak_theme, "get_redis_client", lambda: object())
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_auths_for_realm",
        _async_return([SimpleNamespace(slug="realm-login")]),
    )
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_setting_profiles_for_idp",
        _async_return(
            [
                SimpleNamespace(
                    profile_id=profile_id,
                    department_id=department_id,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_departments_for_sync",
        _async_return(
            [
                SimpleNamespace(
                    department_id=department_id,
                    department_name="Operations",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_auths_for_department",
        _async_return(
            [SimpleNamespace(id=auth_id, slug="sso")]
        ),
    )

    await keycloak_theme.generate_keycloak_theme_providers(_Pool(object()))

    output = (
        tmp_path / "themes" / "glow" / "login" / "providers.ftl"
    ).read_text(encoding="utf-8")

    assert "Operations" in output
    assert f'"{department_id}"' in output
    assert f"auth_sso_{auth_id}" in output
    assert f"default-idp-profile-{profile_id}" in output
    assert "realm-login" in output


async def test_generate_keycloak_theme_providers_uses_platform_fallback_when_no_departments(
    monkeypatch,
    tmp_path,
):
    profile_id = uuid4()

    monkeypatch.setattr(keycloak_theme, "UPLOAD_FOLDER", tmp_path)
    monkeypatch.setattr(keycloak_theme, "get_redis_client", lambda: object())
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_auths_for_realm",
        _async_return([SimpleNamespace(slug="realm-login")]),
    )
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_setting_profiles_for_idp",
        _async_return(
            [
                SimpleNamespace(
                    profile_id=profile_id,
                    department_id=None,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_departments_for_sync",
        _async_return([]),
    )
    monkeypatch.setattr(
        keycloak_theme,
        "resolve_auths_for_department",
        _async_return([]),
    )

    await keycloak_theme.generate_keycloak_theme_providers(_Pool(object()))

    output_path = tmp_path / "themes" / "glow" / "login" / "providers.ftl"
    output = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert "platformProviders" in output
    assert "realm-login" in output
    assert f"default-idp-profile-{profile_id}" in output
    assert "<#assign departments = [" in output
