"""SEC1 — live socket identity is re-validated per-event.

A WebSocket is authenticated once at connect; without per-event
re-validation an expired token / logout / revoked emulation would keep
full mutate privileges on the socket for the 24h cache TTL. These tests
exercise the chokepoint (``resolve_socket_identity``) that every mutate
handler funnels through.
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.infra.identity.resolve_identity import Identity
from app.infra.identity import socket as socket_mod

pytestmark = pytest.mark.asyncio


def _identity(**over):
    d = dict(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="t@example.com",
        role="admin",
        is_emulation=False,
        actor_profile_id=None,
        emulation_depth=0,
        is_mcp=False,
    )
    d.update(over)
    return Identity(**d)


class _FakeRedis:
    """Minimal Redis stand-in: get/setex/delete + SETNX-style set."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.setnx_keys: set[str] = set()

    async def setex(self, key, ttl, data):
        self.store[key] = data

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    async def set(self, key, val, nx=False, ex=None):
        if nx and key in self.setnx_keys:
            return None
        self.setnx_keys.add(key)
        return True


def _store_raw(redis, sid, identity, *, exp, token="tok"):
    """Write a socket_identity snapshot exactly like store_socket_identity."""
    redis.store[f"socket_identity:{sid}"] = json.dumps({
        "profile_id": str(identity.profile_id),
        "session_id": str(identity.session_id),
        "email": identity.email,
        "role": identity.role,
        "is_emulation": identity.is_emulation,
        "actor_profile_id": str(identity.actor_profile_id) if identity.actor_profile_id else None,
        "emulation_depth": identity.emulation_depth,
        "is_mcp": identity.is_mcp,
        "token": token,
        "exp": exp,
    })


async def test_expired_token_event_is_rejected_and_disconnected():
    """A past-exp socket: resolve returns None and the socket is disconnected."""
    redis = _FakeRedis()
    sid = "expired-sid"
    ident = _identity()
    _store_raw(redis, sid, ident, exp=int(time.time()) - 5)

    fake_sio = AsyncMock()
    with patch.object(socket_mod, "get_redis_client", return_value=redis), \
         patch("app.infra.globals.sio", fake_sio):
        result = await socket_mod.resolve_socket_identity(sid)

    assert result is None  # stale event must NOT run with the cached identity
    fake_sio.disconnect.assert_awaited_once_with(sid)
    assert f"socket_identity:{sid}" not in redis.store  # snapshot purged


async def test_valid_token_resolves_without_revalidation_when_throttled():
    """Within the throttle window the full reverify is skipped (cheap path)."""
    redis = _FakeRedis()
    sid = "live-sid"
    ident = _identity()
    _store_raw(redis, sid, ident, exp=int(time.time()) + 3600)
    # Pre-occupy the SETNX gate so _should_revalidate returns False.
    redis.setnx_keys.add(f"socket_revalidated:{sid}")

    with patch.object(socket_mod, "get_redis_client", return_value=redis):
        result = await socket_mod.resolve_socket_identity(sid)

    assert result is not None
    assert result.profile_id == ident.profile_id


async def test_revalidation_rejects_when_token_now_invalid():
    """When the window opens and resolve_identity raises, socket is dropped."""
    redis = _FakeRedis()
    sid = "revoked-sid"
    ident = _identity()
    _store_raw(redis, sid, ident, exp=int(time.time()) + 3600)

    fake_sio = AsyncMock()
    with patch.object(socket_mod, "get_redis_client", return_value=redis), \
         patch("app.infra.globals.sio", fake_sio), \
         patch("app.infra.globals.get_pool", return_value=object()), \
         patch(
             "app.infra.identity.resolve_identity.resolve_identity",
             AsyncMock(side_effect=ValueError("Token expired")),
         ):
        result = await socket_mod.resolve_socket_identity(sid)

    assert result is None
    fake_sio.disconnect.assert_awaited_once_with(sid)


async def test_revalidation_rejects_when_emulation_revoked():
    """Emulation flips off after connect → effective identity changed → drop."""
    redis = _FakeRedis()
    sid = "emu-sid"
    actor = uuid4()
    target = uuid4()
    # Cached snapshot: actively emulating `target` as `actor`.
    cached = _identity(profile_id=target, is_emulation=True, actor_profile_id=actor)
    _store_raw(redis, sid, cached, exp=int(time.time()) + 3600)

    # After grant revoke, resolve_identity now returns the actor's own,
    # non-emulated identity.
    fresh = _identity(profile_id=actor, is_emulation=False, actor_profile_id=None)

    fake_sio = AsyncMock()
    with patch.object(socket_mod, "get_redis_client", return_value=redis), \
         patch("app.infra.globals.sio", fake_sio), \
         patch("app.infra.globals.get_pool", return_value=object()), \
         patch(
             "app.infra.identity.resolve_identity.resolve_identity",
             AsyncMock(return_value=fresh),
         ):
        result = await socket_mod.resolve_socket_identity(sid)

    assert result is None  # must not keep acting as the victim
    fake_sio.disconnect.assert_awaited_once_with(sid)


async def test_revalidation_passes_when_identity_unchanged():
    """Token still valid + same effective identity → event proceeds."""
    redis = _FakeRedis()
    sid = "ok-sid"
    ident = _identity()
    _store_raw(redis, sid, ident, exp=int(time.time()) + 3600)
    fresh = _identity(
        profile_id=ident.profile_id,
        session_id=ident.session_id,
        is_emulation=False,
        actor_profile_id=None,
    )

    with patch.object(socket_mod, "get_redis_client", return_value=redis), \
         patch("app.infra.globals.get_pool", return_value=object()), \
         patch(
             "app.infra.identity.resolve_identity.resolve_identity",
             AsyncMock(return_value=fresh),
         ):
        result = await socket_mod.resolve_socket_identity(sid)

    assert result is not None
    assert result.profile_id == ident.profile_id


async def test_transient_revalidation_error_does_not_drop_socket():
    """A pool/Keycloak hiccup must not tear down an otherwise-valid socket."""
    redis = _FakeRedis()
    sid = "transient-sid"
    ident = _identity()
    _store_raw(redis, sid, ident, exp=int(time.time()) + 3600)

    with patch.object(socket_mod, "get_redis_client", return_value=redis), \
         patch("app.infra.globals.get_pool", return_value=object()), \
         patch(
             "app.infra.identity.resolve_identity.resolve_identity",
             AsyncMock(side_effect=RuntimeError("pool exhausted")),
         ):
        result = await socket_mod.resolve_socket_identity(sid)

    assert result is not None  # exp gate still bounds exposure; retry next event


async def test_store_caps_ttl_at_token_lifetime():
    """store_socket_identity persists exp + token and caps TTL to remaining life."""
    redis = AsyncMock()
    calls = []

    async def fake_setex(key, ttl, data):
        calls.append((key, ttl, data))

    redis.setex = fake_setex
    ident = _identity()
    exp = int(time.time()) + 100

    with patch.object(socket_mod, "get_redis_client", return_value=redis), \
         patch.object(socket_mod, "_extract_exp", return_value=exp):
        await socket_mod.store_socket_identity("s1", ident, token="thetoken")

    key, ttl, data = calls[0]
    parsed = json.loads(data)
    assert parsed["token"] == "thetoken"
    assert parsed["exp"] == exp
    assert ttl <= 100  # capped at remaining token lifetime, not 24h
