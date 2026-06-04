"""Field-level write-authz tests: profile create/update role_id gate.

Regression coverage for the mass-assignment / privilege-escalation class:
the body-supplied ``role_id`` on profile create/update sets a
privilege-bearing attribute (the profile's role). A lower-privileged actor
must not be able to assign a role that outranks their own level (lower
``level`` number = higher privilege). The read surface already gates this
via ``compute_role_options``; these tests assert the write path matches.

Deps are injected as params (monkeypatched module-level collaborators):
  - actor identity         → resolve_profile_identity_context
  - requested role's level → roles get tool
  - the persistence calls  → create/update artifact (asserted on, never hit
                             for the escalation case)
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


def _conn_pool():
    """A pool whose acquire() yields a dummy connection (async cm + txn)."""
    conn = AsyncMock()

    @asynccontextmanager
    async def _txn():
        yield

    conn.transaction = MagicMock(side_effect=_txn)

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=_acquire)
    return pool, conn


def _actor(role_level: int):
    """Minimal actor identity context with create+update permission."""
    return SimpleNamespace(
        role_level=role_level,
        role_permissions=[("profile", "create"), ("profile", "update")],
        department_ids=[uuid4()],
    )


def _role(level: int | None):
    return SimpleNamespace(level=level)


# --------------------------------------------------------------------------
# assert_role_assignable — the shared gate (unit)
# --------------------------------------------------------------------------


async def test_assert_role_assignable_blocks_higher_privilege(monkeypatch):
    """A level-5 actor assigning a level-0 (admin) role is rejected."""
    import app.infra.profile.permissions_context as m

    monkeypatch.setattr(
        m, "get_roles", AsyncMock(return_value=[_role(0)]), raising=False
    )
    # get_roles is imported inside the function; patch at source module too.
    import app.tools.resources.roles.get as roles_get
    monkeypatch.setattr(roles_get, "get_roles", AsyncMock(return_value=[_role(0)]))

    with pytest.raises(HTTPException) as exc:
        await m.assert_role_assignable(
            AsyncMock(), AsyncMock(), role_id=uuid4(), actor_role_level=5
        )
    assert exc.value.status_code == 403


async def test_assert_role_assignable_allows_equal_or_lower_privilege(monkeypatch):
    """A level-5 actor assigning a level-5 (or higher number) role is allowed."""
    import app.tools.resources.roles.get as roles_get
    import app.infra.profile.permissions_context as m

    monkeypatch.setattr(roles_get, "get_roles", AsyncMock(return_value=[_role(5)]))

    # Should not raise.
    await m.assert_role_assignable(
        AsyncMock(), AsyncMock(), role_id=uuid4(), actor_role_level=5
    )


async def test_assert_role_assignable_level0_actor_unrestricted():
    """A level-0 actor may assign any role (no role lookup needed)."""
    import app.infra.profile.permissions_context as m

    # No monkeypatch of get_roles → if it were called the AsyncMock conn
    # would not return a usable role; the short-circuit must avoid it.
    await m.assert_role_assignable(
        AsyncMock(), AsyncMock(), role_id=uuid4(), actor_role_level=0
    )


async def test_assert_role_assignable_noop_without_role():
    """No role_id supplied → nothing to gate."""
    import app.infra.profile.permissions_context as m

    await m.assert_role_assignable(
        AsyncMock(), AsyncMock(), role_id=None, actor_role_level=9
    )


# --------------------------------------------------------------------------
# update_profile_impl — escalation blocked / in-range allowed (end-to-end)
#
# Update is the reachable exploit surface: a non-level-0 actor holding the
# ``profile:update`` permission can edit profiles in their department
# (``compute_can_edit`` passes), so without the gate they could patch a
# target's (or their own) ``role_id`` to a higher-privilege role. Create is
# effectively admin-only (the impl passes ``department_ids=None`` to
# ``compute_can_create``, which rejects any role_level>0), so its gate is
# defense-in-depth and exercised via ``assert_role_assignable`` above.
# --------------------------------------------------------------------------


def _patch_update_actor(monkeypatch, m, actor):
    monkeypatch.setattr(
        m, "resolve_profile_identity_context", AsyncMock(return_value=actor)
    )
    # Target profile exists & shares departments so can_edit passes.
    monkeypatch.setattr(
        m,
        "resolve_profile_permissions_context",
        AsyncMock(
            return_value=SimpleNamespace(
                exists=True, department_ids=[], active_cohort_count=0
            )
        ),
    )


async def test_update_blocks_role_escalation(monkeypatch):
    """Lower-priv actor patching a profile's role_id to an admin role is
    rejected before any artifact write."""
    import app.infra.profile.update as m
    from app.infra.profile.types import UpdateProfileApiRequest, UpdateProfileItem

    _patch_update_actor(monkeypatch, m, _actor(5))
    # Requested role outranks the actor (level 0 < 5).
    monkeypatch.setattr(
        m, "get_role_artifacts", AsyncMock(return_value=[_role(0)])
    )

    update_artifact = AsyncMock()
    monkeypatch.setattr(m, "update_profile_artifact", update_artifact)

    pool, _ = _conn_pool()
    redis = AsyncMock()

    req = UpdateProfileApiRequest(
        profiles=[UpdateProfileItem(profile_id=uuid4(), role_id=uuid4())]
    )

    with pytest.raises(HTTPException) as exc:
        await m.update_profile_impl(pool, redis, profile_id=uuid4(), request=req)

    assert exc.value.status_code == 403
    update_artifact.assert_not_awaited()


async def test_update_allows_in_range_role(monkeypatch):
    """Same actor assigning an at-or-below-level role is permitted (the
    legitimate path still works — the gate only blocks escalation)."""
    import app.infra.profile.update as m
    from app.infra.profile.types import UpdateProfileApiRequest, UpdateProfileItem

    _patch_update_actor(monkeypatch, m, _actor(5))
    # Requested role is at/below the actor's level (7 >= 5).
    monkeypatch.setattr(
        m, "get_role_artifacts", AsyncMock(return_value=[_role(7)])
    )

    # Stub value resolution + persistence so the happy path returns.
    monkeypatch.setattr(m, "resolve_profile_values", AsyncMock(return_value=[]))
    monkeypatch.setattr(m, "get_profile_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        m, "create_denormalized_snapshot", AsyncMock(return_value=uuid4())
    )
    monkeypatch.setattr(
        m, "resolve_primary_departments_id", AsyncMock(return_value=None)
    )
    update_artifact = AsyncMock()
    monkeypatch.setattr(m, "update_profile_artifact", update_artifact)
    monkeypatch.setattr(m, "refresh_profile_impl", AsyncMock())

    async def _no_hydrate(*a, **k):
        return None

    import app.infra.profile.hydrate_list_rows as hydrate_mod
    monkeypatch.setattr(hydrate_mod, "hydrate_profile_list_rows", _no_hydrate)

    pool, _ = _conn_pool()
    redis = AsyncMock()

    target = uuid4()
    req = UpdateProfileApiRequest(
        profiles=[UpdateProfileItem(profile_id=target, role_id=uuid4())]
    )

    resp = await m.update_profile_impl(pool, redis, profile_id=uuid4(), request=req)
    assert resp.results and resp.results[0].success
    assert resp.results[0].profile_id == target
    update_artifact.assert_awaited()
