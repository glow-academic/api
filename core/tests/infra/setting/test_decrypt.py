"""Tests for setting key reveal (decrypt) authorization.

The setting ``decrypt`` (reveal) path returns the RAW, decrypted secret
(provider API key or auth item). The HTTP route and WS handler only
guarantee an *authenticated* profile — neither gates by role.
``decrypt_setting_impl`` is the shared choke point for both transports,
so the permission gate lives here.

These tests pin that contract:
  - an under-privileged caller (no ``setting:update`` permission) is
    rejected with 403 before any key is decrypted (the fix);
  - an unknown profile is rejected with 401 (not silently decrypted);
  - an authorized caller passes the gate and reaches key resolution.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.profile_identity_context import ProfileIdentityContext

pytestmark = pytest.mark.asyncio

MODULE = "app.infra.setting.decrypt"


def _profile(*, role_permissions: list[tuple[str, str]]) -> ProfileIdentityContext:
    return ProfileIdentityContext(
        profiles_id=uuid4(),
        name="Tester",
        role="member",
        role_name="Member",
        role_description="",
        role_artifacts=[],
        primary_email="t@example.com",
        emails=["t@example.com"],
        primary_department_id=uuid4(),
        department_ids=[uuid4()],
        settings_id=uuid4(),
        request_limit=100,
        request_limit_interval=None,
        is_active=True,
        role_level=5,
        role_permissions=role_permissions,
    )


async def test_reveal_rejects_authenticated_but_unprivileged_caller(monkeypatch):
    """A signed-in caller WITHOUT setting:update cannot reveal a key (403)."""
    from app.infra.setting.decrypt import decrypt_setting_impl

    profile = _profile(role_permissions=[("persona", "update")])  # unrelated perm

    async def mock_resolve(pool, pid, redis, **kw):
        return profile

    decrypt_called = False

    async def mock_resolve_decrypt(*args, **kwargs):
        nonlocal decrypt_called
        decrypt_called = True
        raise AssertionError("decryption must not run for an unprivileged caller")

    async def mock_get_settings(*args, **kwargs):
        raise AssertionError("setting fetch must not run before the auth gate")

    monkeypatch.setattr(f"{MODULE}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{MODULE}.resolve_decrypt", mock_resolve_decrypt)
    monkeypatch.setattr(f"{MODULE}.get_settings", mock_get_settings)

    with pytest.raises(HTTPException) as exc_info:
        await decrypt_setting_impl(
            None, None, profile_id=uuid4(), setting_id=uuid4(), key_id=uuid4()
        )

    assert exc_info.value.status_code == 403
    assert "permission" in exc_info.value.detail.lower()
    assert decrypt_called is False


async def test_reveal_rejects_unknown_profile(monkeypatch):
    """A missing profile is rejected with 401 (not silently decrypted)."""
    from app.infra.setting.decrypt import decrypt_setting_impl

    async def mock_resolve(pool, pid, redis, **kw):
        return None

    monkeypatch.setattr(f"{MODULE}.resolve_profile_identity_context", mock_resolve)

    with pytest.raises(HTTPException) as exc_info:
        await decrypt_setting_impl(
            None, None, profile_id=uuid4(), setting_id=uuid4(), key_id=uuid4()
        )

    assert exc_info.value.status_code == 401


async def test_reveal_allows_authorized_caller(monkeypatch):
    """A caller WITH setting:update passes the gate and reaches decryption."""
    from app.infra.setting.decrypt import decrypt_setting_impl
    from app.infra.identity.decrypt import DecryptResult

    profile = _profile(role_permissions=[("setting", "update")])
    setting_id = uuid4()
    key_id = uuid4()

    class _Setting:
        provider_key_ids = [key_id]
        auth_item_keys_ids = []

    async def mock_resolve(pool, pid, redis, **kw):
        return profile

    async def mock_get_settings(pool, ids, **kwargs):
        assert ids == [setting_id]
        return [_Setting()]

    async def mock_resolve_decrypt(
        pool, redis, *, profile_id, key_id, bypass_cache=False
    ):
        return DecryptResult(key="sk-REAL-SECRET", name="My Key", actor_name="Tester")

    monkeypatch.setattr(f"{MODULE}.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr(f"{MODULE}.get_settings", mock_get_settings)
    monkeypatch.setattr(f"{MODULE}.resolve_decrypt", mock_resolve_decrypt)

    result = await decrypt_setting_impl(
        None, None, profile_id=uuid4(), setting_id=setting_id, key_id=key_id
    )

    assert result.key == "sk-REAL-SECRET"
    assert result.name == "My Key"
