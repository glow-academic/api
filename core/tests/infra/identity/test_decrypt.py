"""Tests for infra.auth.decrypt using explicit collaborator boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.infra.identity.decrypt import DecryptResult, resolve_decrypt
from app.infra.profile_identity_context import ProfileIdentityContext
from app.tools.resources.keys.types import GetKeyResponse

NOW = datetime.now(UTC)


def _identity(*, name: str = "Alice") -> ProfileIdentityContext:
    return ProfileIdentityContext(
        profiles_id=uuid4(),
        name=name,
        role="admin",
        role_name="Admin",
        role_description="Administrator",
        role_artifacts=["agent", "persona"],
        primary_email="alice@example.com",
        emails=["alice@example.com"],
        primary_department_id=uuid4(),
        department_ids=[uuid4()],
        settings_id=uuid4(),
        requests_per_day=100,
        is_active=True,
    )


def _key_response(
    *, key_id=None, key="encrypted_value", name="My Key"
) -> GetKeyResponse:
    return GetKeyResponse(
        id=key_id or uuid4(),
        key=key,
        name=name,
        description="test key",
        created_at=NOW,
        active=True,
        mcp=False,
        generated=False,
    )


class _AcquireContext:
    def __init__(self, conn: object) -> None:
        self._conn = conn

    async def __aenter__(self) -> object:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, conn: object | None = None) -> None:
        self.conn = conn or object()

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self.conn)


@pytest.mark.asyncio
class TestResolveDecrypt:
    async def test_returns_decrypt_result(self) -> None:
        profile_id = uuid4()
        key_id = uuid4()
        identity = _identity(name="Bob")
        key = _key_response(key_id=key_id, key="enc_secret", name="API Key")

        async def fake_identity(pool, profile_id_arg, redis, *, bypass_cache=False):
            assert profile_id_arg == profile_id
            return identity

        async def fake_get_keys(conn, key_ids, redis, *, bypass_cache=False):
            assert key_ids == [key_id]
            return [key]

        result = await resolve_decrypt(
            FakePool(),
            None,
            profile_id=profile_id,
            key_id=key_id,
            resolve_profile_identity_fn=fake_identity,
            get_keys_fn=fake_get_keys,
            decrypt_api_key_fn=lambda encrypted: "decrypted_secret",
        )

        assert isinstance(result, DecryptResult)
        assert result.key == "decrypted_secret"
        assert result.name == "API Key"
        assert result.actor_name == "Bob"

    async def test_passes_correct_args_to_collaborators(self) -> None:
        profile_id = uuid4()
        key_id = uuid4()
        conn = object()
        pool = FakePool(conn)
        key = _key_response(key_id=key_id)
        calls: dict[str, object] = {}

        async def fake_identity(pool_arg, profile_id_arg, redis, *, bypass_cache=False):
            calls["identity"] = {
                "pool": pool_arg,
                "profile_id": profile_id_arg,
                "redis": redis,
                "bypass_cache": bypass_cache,
            }
            return _identity()

        async def fake_get_keys(conn_arg, key_ids, redis, *, bypass_cache=False):
            calls["keys"] = {
                "conn": conn_arg,
                "key_ids": key_ids,
                "redis": redis,
                "bypass_cache": bypass_cache,
            }
            return [key]

        def fake_decrypt(encrypted: str) -> str:
            calls["decrypt"] = encrypted
            return "plain"

        await resolve_decrypt(
            pool,
            "fake_redis",
            profile_id=profile_id,
            key_id=key_id,
            bypass_cache=True,
            resolve_profile_identity_fn=fake_identity,
            get_keys_fn=fake_get_keys,
            decrypt_api_key_fn=fake_decrypt,
        )

        assert calls == {
            "identity": {
                "pool": pool,
                "profile_id": profile_id,
                "redis": "fake_redis",
                "bypass_cache": True,
            },
            "keys": {
                "conn": conn,
                "key_ids": [key_id],
                "redis": "fake_redis",
                "bypass_cache": True,
            },
            "decrypt": "encrypted_value",
        }

    async def test_missing_profile_raises_value_error(self) -> None:
        async def fake_identity(pool, profile_id_arg, redis, *, bypass_cache=False):
            return None

        with pytest.raises(ValueError, match="Profile not found"):
            await resolve_decrypt(
                FakePool(),
                None,
                profile_id=uuid4(),
                key_id=uuid4(),
                resolve_profile_identity_fn=fake_identity,
            )

    async def test_missing_key_raises_value_error(self) -> None:
        async def fake_identity(pool, profile_id_arg, redis, *, bypass_cache=False):
            return _identity()

        async def fake_get_keys(conn, key_ids, redis, *, bypass_cache=False):
            return []

        with pytest.raises(ValueError, match="Key not found"):
            await resolve_decrypt(
                FakePool(),
                None,
                profile_id=uuid4(),
                key_id=uuid4(),
                resolve_profile_identity_fn=fake_identity,
                get_keys_fn=fake_get_keys,
            )

    async def test_decrypt_failure_propagates(self) -> None:
        key = _key_response(key="bad_encrypted_key")

        async def fake_identity(pool, profile_id_arg, redis, *, bypass_cache=False):
            return _identity()

        async def fake_get_keys(conn, key_ids, redis, *, bypass_cache=False):
            return [key]

        def fake_decrypt(encrypted: str) -> str:
            raise ValueError("bad key")

        with pytest.raises(ValueError, match="bad key"):
            await resolve_decrypt(
                FakePool(),
                None,
                profile_id=uuid4(),
                key_id=uuid4(),
                resolve_profile_identity_fn=fake_identity,
                get_keys_fn=fake_get_keys,
                decrypt_api_key_fn=fake_decrypt,
            )
