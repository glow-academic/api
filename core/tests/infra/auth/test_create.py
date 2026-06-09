"""Tests for auth create — profile check, permission check, orchestration."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.auth.create import create_auth_impl
from app.infra.auth.types import CreateAuthApiRequest

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeProfile:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "Test User"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


class _FakeTx:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _FakeConn:
    def transaction(self):
        return _FakeTx()


class _FakePoolConn:
    async def __aenter__(self):
        return _FakeConn()
    async def __aexit__(self, *a):
        pass


class _FakePool:
    def acquire(self):
        return _FakePoolConn()


async def test_create_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=CreateAuthApiRequest(auths=[]))
    assert exc_info.value.status_code == 401


async def test_create_raises_403_for_non_superadmin(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4(), role="member", role_level=3, role_permissions=[])

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=CreateAuthApiRequest(auths=[]))
    assert exc_info.value.status_code == 403


async def test_create_returns_results_for_empty_items(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4(), role="superadmin", role_level=0, role_permissions=[("auth", "create"), ("auth", "update"), ("auth", "delete"), ("auth", "duplicate"), ("auth", "draft")])

    async def mock_keycloak(**kw):
        pass

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )
    # The empty-items path still calls refresh_auth_impl, which delegates to
    # enqueue_refreshes → its own permission check via the queue module's
    # resolve_profile_identity_context. Patch that too so the inner refresh
    # passes (cache invalidation now lives in enqueue_refreshes, not here).
    monkeypatch.setattr(
        "app.infra.refresh.queue.resolve_profile_identity_context", mock_resolve
    )
    # perform_keycloak_sync is imported lazily inside create_auth_impl, so it is
    # not a module attribute of app.infra.auth.create — patch it at its source.
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=CreateAuthApiRequest(auths=[]))
    assert hasattr(result, "results")
    assert len(result.results) == 0

    # The empty-items path still schedules the fire-and-forget Keycloak sync;
    # drain it so it doesn't leak into other tests.
    from app.utils.async_tasks import wait_for_pending
    await wait_for_pending(timeout=2.0)


def _patch_create_happy_path(monkeypatch, *, new_auth_id, keycloak):
    """Patch the create_auth_impl collaborators down to a single auth write.

    ``keycloak`` is injected as a parameter so each test can supply a slow,
    raising, or failing ``perform_keycloak_sync`` stub without re-stating the
    rest of the happy-path wiring (deps-as-params keeps the tests modular).
    """
    from app.tools.artifacts.auth.types import CreateAuthResponse

    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(
            profiles_id=uuid4(),
            role="superadmin",
            role_level=0,
            role_permissions=[
                ("auth", "create"), ("auth", "update"), ("auth", "delete"),
                ("auth", "duplicate"), ("auth", "draft"),
            ],
        )

    async def mock_resolve_values(conn, redis, item, **kw):
        return []  # no validation errors

    async def mock_snapshot(pool, redis, **kw):
        return uuid4()

    async def mock_create_artifact(conn, **kw):
        return CreateAuthResponse(id=new_auth_id)

    async def mock_refresh(pool, redis, **kw):
        return None

    async def mock_hydrate(pool, redis, **kw):
        return []

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )
    monkeypatch.setattr(
        "app.infra.auth.create.resolve_auth_values", mock_resolve_values
    )
    monkeypatch.setattr(
        "app.infra.auth.create.create_denormalized_snapshot", mock_snapshot
    )
    monkeypatch.setattr(
        "app.infra.auth.create.create_auth_artifact", mock_create_artifact
    )
    monkeypatch.setattr("app.infra.auth.create.refresh_auth_impl", mock_refresh)
    # hydrate_auth_list_rows is imported lazily inside create_auth_impl — patch
    # at its source module.
    monkeypatch.setattr(
        "app.infra.auth.hydrate_list_rows.hydrate_auth_list_rows", mock_hydrate
    )
    # perform_keycloak_sync is imported lazily inside create_auth_impl, so patch
    # it at its source module.
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", keycloak
    )


async def test_create_does_not_block_on_slow_keycloak_sync(monkeypatch):
    """A slow/stalled Keycloak IdP sync must NOT block the create response.

    The auth row is committed before the sync, and the sync is now scheduled
    fire-and-forget. Before the fix create_auth_impl AWAITED
    ``perform_keycloak_sync`` inline, so a slow sync (the fresh-deploy KC
    sync-race retries for ~90-150s) pushed /auth/create past nginx's 60s
    ``proxy_read_timeout`` → a 504 even though the row was already written.
    This proves the response returns promptly while the sync hangs, and that
    the sync was still scheduled (not dropped).
    """
    import asyncio

    from app.utils.async_tasks import wait_for_pending

    new_auth_id = uuid4()
    sync_started = asyncio.Event()
    release_sync = asyncio.Event()

    async def slow_keycloak(**kw):
        # Mimic a stalled sync: signal that it started, then hang until the
        # test releases it. If create_auth_impl awaited this inline the test
        # would deadlock on the wait_for below.
        sync_started.set()
        await release_sync.wait()

    _patch_create_happy_path(
        monkeypatch, new_auth_id=new_auth_id, keycloak=slow_keycloak
    )

    request = CreateAuthApiRequest(auths=[{"name": "Acme SSO"}])
    # Returns promptly despite the sync hanging — a generous bound that is
    # still far under nginx's 60s timeout.
    result = await asyncio.wait_for(
        create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=request),
        timeout=5.0,
    )

    # The auth row is written and reported as a clean success.
    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.auth_id == new_auth_id
    assert item.message == "Auth created successfully"

    # The sync was scheduled (fire-and-forget) and is still running — proves
    # the response did NOT wait for it to complete.
    await asyncio.wait_for(sync_started.wait(), timeout=2.0)
    assert not release_sync.is_set()

    # Let the background task finish so it doesn't leak into other tests.
    release_sync.set()
    await wait_for_pending(timeout=2.0)


async def test_create_returns_success_when_keycloak_sync_raises(monkeypatch):
    """If the background Keycloak sync raises, the create still returns 2xx.

    The failure is logged by ``schedule_background`` (never re-raised), so the
    caller gets a clean success with the auth row — the create is decoupled
    from the best-effort sync's outcome.
    """
    from app.utils.async_tasks import wait_for_pending

    new_auth_id = uuid4()

    async def raising_keycloak(**kw):
        raise RuntimeError("keycloak boom")

    _patch_create_happy_path(
        monkeypatch, new_auth_id=new_auth_id, keycloak=raising_keycloak
    )

    request = CreateAuthApiRequest(auths=[{"name": "Acme SSO"}])
    result = await create_auth_impl(
        _FakePool(), None, profile_id=uuid4(), request=request
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.auth_id == new_auth_id
    assert item.message == "Auth created successfully"

    # Drain the background task: it raised internally, schedule_background
    # logged it, and it did not surface to the caller or crash the test.
    await wait_for_pending(timeout=2.0)


async def test_create_returns_success_when_keycloak_sync_reports_failure(monkeypatch):
    """A ``success=False`` sync result no longer degrades the create response.

    ``perform_keycloak_sync`` returns ``KeycloakSyncResult(success=False)`` when
    Keycloak is unreachable. Since the sync now runs off the response critical
    path, that result is observed only in the background — the create returns a
    clean success with the row (the backstop resync reconciles KC later).
    """
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.utils.async_tasks import wait_for_pending

    new_auth_id = uuid4()

    async def failing_keycloak(**kw):
        return KeycloakSyncResult(
            success=False,
            message="Keycloak sync did not complete (Keycloak unavailable)",
            error="keycloak_unavailable",
        )

    _patch_create_happy_path(
        monkeypatch, new_auth_id=new_auth_id, keycloak=failing_keycloak
    )

    request = CreateAuthApiRequest(auths=[{"name": "Acme SSO"}])
    result = await create_auth_impl(
        _FakePool(), None, profile_id=uuid4(), request=request
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.auth_id == new_auth_id
    assert item.message == "Auth created successfully"

    await wait_for_pending(timeout=2.0)
