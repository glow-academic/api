"""Tests for auth update — profile check, permission check."""

from dataclasses import dataclass
from uuid import uuid4
import pytest
from app.infra.auth.update import update_auth_impl
from app.infra.auth.types import UpdateAuthApiRequest, UpdateAuthItem

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeProfileU:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


class _FakeTxU:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _FakeConnU:
    def transaction(self):
        return _FakeTxU()


class _FakePoolConnU:
    async def __aenter__(self):
        return _FakeConnU()
    async def __aexit__(self, *a):
        pass


class _FakePoolU:
    def acquire(self):
        return _FakePoolConnU()


async def test_update_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_auth_impl(None, None, profile_id=uuid4(), request=UpdateAuthApiRequest(auths=[UpdateAuthItem(id=uuid4())]))
    assert exc_info.value.status_code == 401


async def test_update_raises_400_for_no_items(monkeypatch):
    from dataclasses import dataclass
    @dataclass
    class P:
        profiles_id: object = None
        role: str = "superadmin"
        name: str = "U"
        group_id: object = None
        department_ids: list = None
        role_level: int = 0
        role_permissions: list = None
    async def mock_resolve(pool, pid, redis, **kw):
        return P(profiles_id=uuid4())
    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_auth_impl(
            None, None, profile_id=uuid4(),
            request=UpdateAuthApiRequest(auths=[]),
        )
    assert exc_info.value.status_code == 400


async def test_update_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_auth_impl(None, None, profile_id=uuid4(), request=UpdateAuthApiRequest(auths=[UpdateAuthItem(id=uuid4())]))
    assert "sign in" in exc_info.value.detail.lower()


async def test_update_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed Keycloak IdP re-sync after update must NOT report unqualified success.

    ``perform_keycloak_sync`` returns ``KeycloakSyncResult(success=False)`` on
    failure rather than raising. Before the fix that ``False`` was dropped (the
    ``except Exception`` was dead code) and every result still said "Auth
    updated successfully", even though the IdP config in Keycloak is now stale.
    This proves the warning reaches the caller (fails before, passes after).
    Mirrors #249's create fix.
    """
    from app.infra.auth.permissions_context import AuthPermissionsContext
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.auth.types import UpdateAuthResponse

    auth_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfileU(profiles_id=uuid4(), role_permissions=[("auth", "update")])

    async def mock_perms(conn, _id):
        return AuthPermissionsContext(exists=True, department_ids=[], active_settings_count=0)

    async def mock_resolve_values(conn, redis, item, **kw):
        return []  # no validation errors

    async def mock_get_artifacts(conn, ids, **kw):
        return []

    async def mock_snapshot(pool, redis, **kw):
        return uuid4()

    async def mock_update_artifact(conn, _id, **kw):
        return UpdateAuthResponse(id=auth_id)

    async def mock_refresh(pool, redis, **kw):
        return None

    async def mock_hydrate(pool, redis, **kw):
        return []

    async def mock_keycloak(**kw):
        return KeycloakSyncResult(
            success=False,
            message="Keycloak sync did not complete (Keycloak unavailable)",
            error="keycloak_unavailable",
        )

    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.update.resolve_auth_permissions_context", mock_perms)
    monkeypatch.setattr("app.infra.auth.update.resolve_auth_values", mock_resolve_values)
    monkeypatch.setattr("app.infra.auth.update.get_auth_artifacts", mock_get_artifacts)
    monkeypatch.setattr("app.infra.auth.update.create_denormalized_snapshot", mock_snapshot)
    monkeypatch.setattr("app.infra.auth.update.update_auth_artifact", mock_update_artifact)
    monkeypatch.setattr("app.infra.auth.update.refresh_auth_impl", mock_refresh)
    monkeypatch.setattr("app.infra.auth.hydrate_list_rows.hydrate_auth_list_rows", mock_hydrate)
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await update_auth_impl(
        _FakePoolU(), None, profile_id=uuid4(),
        request=UpdateAuthApiRequest(auths=[UpdateAuthItem(id=auth_id)]),
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    # The swallowed sync failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert item.message != "Auth updated successfully"


async def test_accept_reactivates_the_soft_updated_row(monkeypatch):
    """A1 regression: accepting a soft auth-update must re-activate the row.

    The soft (propose) write forces ``active=False`` (``soft=True`` does), which
    hides the row from ``search_auth`` (filters ``a.active = true``). Before the
    fix the accept path called ``update_auth_artifact(conn, target_id, soft=False)``
    with NO ``active`` arg → the tool's ``active`` defaulted to ``_UNSET`` → the
    else-branch only touched ``updated_at``/``mcp`` and the row stayed
    ``active=False`` FOREVER (the accepted change permanently invisible).

    This test captures the kwargs the accept path hands to the artifact tool and
    asserts ``active=True`` is now passed. (The old test mocked the tool and only
    checked the no-op default, which is exactly why A1 slipped through.)
    """
    from app.tools.artifacts.auth.types import UpdateAuthResponse
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import datetime, timezone

    auth_id = uuid4()
    idem_key = uuid4()
    captured: dict = {}

    async def mock_get_soft_call(conn, call_id, redis, *, artifact=None):
        return GetSoftCallResponse(
            id=uuid4(),
            call_id=call_id,
            artifact="auth",
            operation="update",
            status="pending",
            artifact_id=auth_id,
            patch=None,
            created_at=datetime.now(timezone.utc),
        )

    async def mock_update_artifact(conn, _id, **kw):
        captured["id"] = _id
        captured["kwargs"] = kw
        return UpdateAuthResponse(id=auth_id)

    async def mock_create_soft_call(conn, redis, **kw):
        return None

    async def mock_resolve_soft_call(conn, redis, **kw):
        # Atomic transition won the race (A3/A4) → returns a terminal entry so
        # the accept side effect (re-activate) proceeds.
        return GetSoftCallResponse(
            id=uuid4(), call_id=idem_key, artifact="auth", operation="update",
            status="accepted", artifact_id=auth_id, patch=None,
            created_at=datetime.now(timezone.utc),
        )

    async def mock_refresh_soft_calls(conn):
        return None

    async def mock_refresh(pool, redis, **kw):
        return None

    monkeypatch.setattr("app.infra.auth.update.get_soft_call", mock_get_soft_call)
    monkeypatch.setattr("app.infra.auth.update.update_auth_artifact", mock_update_artifact)
    monkeypatch.setattr("app.infra.auth.update.create_soft_call", mock_create_soft_call)
    monkeypatch.setattr("app.infra.auth.update.resolve_soft_call", mock_resolve_soft_call)
    monkeypatch.setattr("app.infra.auth.update.refresh_soft_calls", mock_refresh_soft_calls)
    monkeypatch.setattr("app.infra.auth.update.refresh_auth_impl", mock_refresh)

    result = await update_auth_impl(
        _FakePoolU(), None, profile_id=uuid4(),
        request=UpdateAuthApiRequest(),
        idempotency_key=idem_key,
        accept=True,
    )

    assert result.results[0].success is True
    assert captured["id"] == auth_id
    # The crux of A1: accept must re-activate the row, not leave active=_UNSET.
    assert captured["kwargs"].get("active") is True
    assert captured["kwargs"].get("soft") is False


async def test_double_ack_skips_reactivation(monkeypatch):
    """A3: a concurrent double-ack (resolve_soft_call returns None) must SKIP the
    re-activation AND the soft-call / auth refreshes — no double side effect."""
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import datetime, timezone

    auth_id = uuid4()
    idem_key = uuid4()
    calls = {"update": 0, "refresh_soft": 0, "refresh_auth": 0}

    async def mock_get_soft_call(conn, call_id, redis, *, artifact=None):
        return GetSoftCallResponse(
            id=uuid4(), call_id=call_id, artifact="auth", operation="update",
            status="pending", artifact_id=auth_id, patch=None,
            created_at=datetime.now(timezone.utc),
        )

    async def mock_resolve_soft_call(conn, redis, **kw):
        return None  # already resolved by a concurrent ack

    async def mock_update_artifact(conn, _id, **kw):
        calls["update"] += 1

    async def mock_refresh_soft_calls(conn):
        calls["refresh_soft"] += 1

    async def mock_refresh(pool, redis, **kw):
        calls["refresh_auth"] += 1

    monkeypatch.setattr("app.infra.auth.update.get_soft_call", mock_get_soft_call)
    monkeypatch.setattr("app.infra.auth.update.resolve_soft_call", mock_resolve_soft_call)
    monkeypatch.setattr("app.infra.auth.update.update_auth_artifact", mock_update_artifact)
    monkeypatch.setattr("app.infra.auth.update.refresh_soft_calls", mock_refresh_soft_calls)
    monkeypatch.setattr("app.infra.auth.update.refresh_auth_impl", mock_refresh)

    result = await update_auth_impl(
        _FakePoolU(), None, profile_id=uuid4(),
        request=UpdateAuthApiRequest(),
        idempotency_key=idem_key,
        accept=True,
    )

    # Idempotent success, but no second side effect.
    assert result.results[0].success is True
    assert calls["update"] == 0
    assert calls["refresh_soft"] == 0
    assert calls["refresh_auth"] == 0


async def test_ack_resolve_and_activate_share_one_transaction(monkeypatch):
    """A4: the resolve (ledger write) and the re-activation run inside ONE open
    transaction; the refreshes run only AFTER it commits."""
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import datetime, timezone

    auth_id = uuid4()
    idem_key = uuid4()
    order: list[str] = []

    # A conn whose transaction() flips a flag the mocks can observe.
    class _Tx:
        def __init__(self, conn):
            self._c = conn

        async def __aenter__(self):
            self._c.in_tx = True
            return None

        async def __aexit__(self, *a):
            self._c.in_tx = False
            return False

    class _Conn:
        in_tx = False

        def transaction(self):
            return _Tx(self)

    class _PoolConn:
        def __init__(self, conn):
            self._c = conn

        async def __aenter__(self):
            return self._c

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def __init__(self):
            self.conn = _Conn()

        def acquire(self):
            return _PoolConn(self.conn)

    pool = _Pool()

    async def mock_get_soft_call(conn, call_id, redis, *, artifact=None):
        return GetSoftCallResponse(
            id=uuid4(), call_id=call_id, artifact="auth", operation="update",
            status="pending", artifact_id=auth_id, patch=None,
            created_at=datetime.now(timezone.utc),
        )

    async def mock_resolve_soft_call(conn, redis, **kw):
        order.append(f"resolve:in_tx={conn.in_tx}")
        return GetSoftCallResponse(
            id=uuid4(), call_id=idem_key, artifact="auth", operation="update",
            status="accepted", artifact_id=auth_id, patch=None,
            created_at=datetime.now(timezone.utc),
        )

    async def mock_update_artifact(conn, _id, **kw):
        order.append(f"activate:in_tx={conn.in_tx}")

    async def mock_refresh_soft_calls(conn):
        order.append(f"refresh_soft:in_tx={conn.in_tx}")

    async def mock_refresh(pool_, redis, **kw):
        order.append(f"refresh_auth:in_tx={pool.conn.in_tx}")

    monkeypatch.setattr("app.infra.auth.update.get_soft_call", mock_get_soft_call)
    monkeypatch.setattr("app.infra.auth.update.resolve_soft_call", mock_resolve_soft_call)
    monkeypatch.setattr("app.infra.auth.update.update_auth_artifact", mock_update_artifact)
    monkeypatch.setattr("app.infra.auth.update.refresh_soft_calls", mock_refresh_soft_calls)
    monkeypatch.setattr("app.infra.auth.update.refresh_auth_impl", mock_refresh)

    await update_auth_impl(
        pool, None, profile_id=uuid4(),
        request=UpdateAuthApiRequest(),
        idempotency_key=idem_key,
        accept=True,
    )

    # resolve + activate inside the txn; both refreshes after it closed.
    assert order == [
        "resolve:in_tx=True",
        "activate:in_tx=True",
        "refresh_soft:in_tx=False",
        "refresh_auth:in_tx=False",
    ]
