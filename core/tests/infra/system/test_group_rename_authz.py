"""R3 — system-group rename ownership gate moved INTO the shared impls.

``title_group_impl`` (``group/title.py``) and ``name_group_impl``
(``group/name.py``) are shared across ~20 artifact wrappers. The per-artifact
*test*/*attempt* title wrappers gate ownership themselves, but the *system*
wrappers did not: ``title_system_impl`` (``POST /system/title`` + INFRA_OPS
dispatch) delegated straight to ``title_group_impl`` with no gate, and the WS
``system.group_name`` handler reached ``name_group_impl`` (which did only an
existence check). A system group chain is per-session-private
(``group → session → owner``), so this was a write-IDOR: any authenticated
profile could rename another user's system group.

R3 moves the gate INTO the shared impls (keyed on owner-scoped ``artifact_type``
for ``title_group_impl``; unconditional for ``name_group_impl``, which is only
ever the system rename), so no wrapper can omit it. These tests drive the REAL
shared impls (the gate is no longer mockable away in a wrapper) and assert that
renaming *another* user's system group is denied — while the legitimate owner
is allowed and the write still fires (idempotent with the existing test/attempt
wrapper gates).

Owner-resolution wiring mirrors
``core/tests/infra/test/test_test_mutation_authz_class.py``: fake the
``group → session → owner`` resolvers at their *source* modules (the gate's
``enforce_attempt_access_by_group`` imports them lazily) so the REAL gate
decides 403-vs-allow.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


# ── Actors / fakes ───────────────────────────────────────────────────────────


def _profile(profiles_id: UUID, role: str, role_level: int):
    from app.infra.profile_identity_context import ProfileIdentityContext

    return ProfileIdentityContext(
        profiles_id=profiles_id,
        name="actor",
        role=role,
        role_name=role,
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=None,
        department_ids=[],
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=role_level,
        role_permissions=[],
    )


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConn()


def _wire_owner_resolution(monkeypatch, *, owner_profile_id, department_in_scope):
    """Fake the ``group → session → owner`` chain at its source modules so the
    REAL gate (``enforce_attempt_access_by_group``) decides."""
    import app.infra.dashboard.visibility as vis_mod
    import app.tools.entries.groups.get as groups_mod
    import app.tools.entries.sessions.get as sessions_mod

    session_id = uuid4()

    async def fake_get_groups(conn, ids, redis, *a, **k):
        from app.tools.entries.groups.types import GetGroupResponse

        return [GetGroupResponse.model_construct(group_id=ids[0], session_id=session_id)]

    async def fake_get_sessions(conn, ids, redis, *a, **k):
        from app.tools.entries.sessions.types import GetSessionResponse

        return [GetSessionResponse.model_construct(
            session_id=ids[0], profile_id=owner_profile_id,
        )]

    async def fake_dept_scope(pool, caller, owner_profiles_id, *a, **k):
        return department_in_scope

    monkeypatch.setattr(groups_mod, "get_groups", fake_get_groups)
    monkeypatch.setattr(sessions_mod, "get_sessions", fake_get_sessions)
    monkeypatch.setattr(vis_mod, "is_profile_in_department_scope", fake_dept_scope)


def _wire_title(monkeypatch, actor):
    """Patch the shared title impl's module-scope dependencies so the REAL gate
    runs but the write/refresh never touch a DB. Returns the list of renamed
    group_ids (proves a deny did NOT delegate to the write)."""
    import app.infra.group.title as mod

    renamed: list[UUID] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_create_group_name(conn, redis, *, group_id, **k):
        renamed.append(group_id)

        class _R:
            id = uuid4()

        return _R()

    async def fake_refresh(*a, **k):
        return None

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "create_group_name", fake_create_group_name)
    monkeypatch.setattr(mod, "refresh_group_impl", fake_refresh)
    return renamed


def _wire_name(monkeypatch, actor):
    """Same as :func:`_wire_title` for the shared ``name_group_impl``."""
    import app.infra.group.name as mod

    renamed: list[UUID] = []

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_create_group_name(conn, redis, *, group_id, **k):
        renamed.append(group_id)

        class _R:
            id = uuid4()

        return _R()

    async def fake_refresh(*a, **k):
        return None

    async def fake_invalidate(*a, **k):
        return None

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "create_group_name", fake_create_group_name)
    monkeypatch.setattr(mod, "refresh_group_impl", fake_refresh)
    monkeypatch.setattr(mod, "invalidate_tags", fake_invalidate)
    return renamed


async def _run_system_title(group_id, actor_id):
    from app.infra.system.title import TitleSystemApiRequest, title_system_impl

    return await title_system_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        request=TitleSystemApiRequest(group_id=group_id, title="renamed"),
    )


async def _run_system_name(group_id, actor_id):
    from app.infra.group.name import name_group_impl

    return await name_group_impl(
        _FakePool(), object(),
        profile_id=actor_id, session_id=uuid4(),
        group_id=group_id, name="renamed",
    )


# ── system/title (POST /system/title + INFRA_OPS dispatch) ────────────────────


async def test_system_title_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    renamed = _wire_title(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    with pytest.raises(HTTPException) as exc:
        await _run_system_title(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert renamed == []  # the foreign system group was never renamed


async def test_system_title_blocks_cross_department_instructor(monkeypatch):
    instructor, owner = uuid4(), uuid4()
    renamed = _wire_title(monkeypatch, _profile(instructor, "instructional", 2))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    with pytest.raises(HTTPException) as exc:
        await _run_system_title(uuid4(), instructor)
    assert exc.value.status_code == 403
    assert renamed == []


async def test_system_title_allows_owner(monkeypatch):
    owner, gid = uuid4(), uuid4()
    renamed = _wire_title(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    result = await _run_system_title(gid, owner)
    assert result.group_id == gid
    assert renamed == [gid]  # legitimate owner write fires (gate is idempotent)


# ── WS system.group_name → name_group_impl ────────────────────────────────────


async def test_system_name_blocks_peer_member(monkeypatch):
    attacker, owner = uuid4(), uuid4()
    renamed = _wire_name(monkeypatch, _profile(attacker, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=True)
    with pytest.raises(HTTPException) as exc:
        await _run_system_name(uuid4(), attacker)
    assert exc.value.status_code == 403
    assert renamed == []


async def test_system_name_allows_owner(monkeypatch):
    owner, gid = uuid4(), uuid4()
    renamed = _wire_name(monkeypatch, _profile(owner, "member", 1))
    _wire_owner_resolution(monkeypatch, owner_profile_id=owner, department_in_scope=False)
    result = await _run_system_name(gid, owner)
    assert result.success is True
    assert renamed == [gid]
