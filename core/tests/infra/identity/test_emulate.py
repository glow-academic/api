"""Tests for infra.auth.emulate using the real grant/emulation path."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.infra.identity.emulate import EmulationResult, resolve_emulation
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grants.search import search_grants
from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions

pytestmark = pytest.mark.asyncio


class TestResolveEmulation:
    async def test_superadmin_can_emulate_member(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        requester = await profile_identity_factory(
            name="Super",
            role=("superadmin", "Superadmin", "Superadmin role"),
            role_name_exact="Super Administrator",
        )
        target = await profile_identity_factory(
            name="Member",
            role=("member", "Member", "Member role"),
            role_name_exact="GTA",
        )

        async with pool.acquire() as conn:
            requester_session = await create_session(
                conn,
                redis_client, profile_id=requester.profile_resource_id,
            )
            target_session = await create_session(
                conn,
                redis_client, profile_id=target.profile_resource_id,
            )
            await refresh_sessions(conn)

        result = await resolve_emulation(
            pool,
            redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )

        assert isinstance(result, EmulationResult)
        assert result.allowed is True
        assert result.reason is None
        assert result.grant_id is not None
        assert result.expires_at is not None

        async with pool.acquire() as conn:
            grants = await search_grants(
                conn,
                redis_client, session_ids=[requester_session.id],
                bypass_mv=True,
                active=True,
            )
            emulations = await search_emulations(
                conn,
                redis_client, session_ids=[target_session.id],
                bypass_mv=True,
            )

        assert len(grants) == 1
        assert grants[0].id == result.grant_id
        assert grants[0].profiles_id == requester.profile_resource_id
        assert len(emulations) == 1
        assert emulations[0].grant_id == result.grant_id
        assert emulations[0].profile_id == target.profile_resource_id

    async def test_self_emulation_allowed(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        fixture = await profile_identity_factory(
            name="Self",
            role=("member", "Member", "Member role"),
        )

        async with pool.acquire() as conn:
            session = await create_session(
                conn,
                redis_client, profile_id=fixture.profile_resource_id,
            )
            await refresh_sessions(conn)

        result = await resolve_emulation(
            pool,
            redis_client,
            requester_profile_id=fixture.artifact_id,
            target_profile_id=fixture.artifact_id,
        )

        assert result.allowed is True
        assert result.grant_id is not None

        async with pool.acquire() as conn:
            grants = await search_grants(
                conn,
                redis_client, session_ids=[session.id],
                bypass_mv=True,
            )

        assert len(grants) == 1
        assert grants[0].id == result.grant_id

    async def test_member_cannot_emulate_admin(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        requester = await profile_identity_factory(
            role=("member", "Member", "Member role"),
        )
        target = await profile_identity_factory(
            role=("admin", "Admin", "Admin role"),
        )

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=requester.profile_resource_id)
            await create_session(conn, redis_client, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        result = await resolve_emulation(
            pool,
            redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )

        assert result.allowed is False
        assert result.reason == "You do not have permission to emulate this profile"
        assert result.grant_id is None

    async def test_requester_without_active_session_is_rejected(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        requester = await profile_identity_factory(
            role=("superadmin", "Superadmin", "Superadmin role"),
            role_name_exact="Super Administrator",
        )
        target = await profile_identity_factory(
            role=("member", "Member", "Member role"),
            role_name_exact="GTA",
        )

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        result = await resolve_emulation(
            pool,
            redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )

        assert result.allowed is False
        assert result.reason == "No active session found for requester"

    async def test_target_without_active_session_is_rejected(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        requester = await profile_identity_factory(
            role=("superadmin", "Superadmin", "Superadmin role"),
            role_name_exact="Super Administrator",
        )
        target = await profile_identity_factory(
            role=("member", "Member", "Member role"),
            role_name_exact="GTA",
        )

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=requester.profile_resource_id)
            await refresh_sessions(conn)

        result = await resolve_emulation(
            pool,
            redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )

        assert result.allowed is False
        assert result.reason == "No active session found for target"


# ── Department scope on emulation (#152/#148) ────────────────────────────────
# A non-super requester may only emulate a target whose role they may simulate
# AND who shares one of their departments (or is global/roleless). Self and
# super-admin are unaffected. We control the resolved identities (department +
# role) by monkeypatching the identity resolver — the same dependency-injection
# style the download IDOR tests use — so the authorization predicate is exercised
# deterministically. The ALLOW path still creates a real grant against real
# sessions; the DENY path short-circuits before any session lookup.


def _emu_ctx(profiles_id, *, role: str, role_level: int, department_ids):
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
        primary_department_id=(department_ids[0] if department_ids else None),
        department_ids=list(department_ids),
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=role_level,
    )


def _patch_identities(monkeypatch, mapping):
    """Patch emulate.resolve_profile_identity_context to return crafted contexts
    keyed by the profile-id argument."""
    import app.infra.identity.emulate as emulate_mod

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return mapping.get(profile_id)

    monkeypatch.setattr(emulate_mod, "resolve_profile_identity_context", fake_resolve)


class TestEmulationDepartmentScope:
    async def test_same_department_admin_can_emulate(
        self, pool, redis_client, monkeypatch, profile_identity_factory
    ):
        """(a) SAME-dept: an Administrator emulating a GTA in a shared
        department is ALLOWED (full grant created)."""
        requester = await profile_identity_factory(name="emu-req")
        target = await profile_identity_factory(name="emu-tgt")

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=requester.profile_resource_id)
            await create_session(conn, redis_client, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        dept = uuid4()
        _patch_identities(
            monkeypatch,
            {
                requester.artifact_id: _emu_ctx(
                    requester.profile_resource_id, role="Administrator", role_level=3,
                    department_ids=[dept],
                ),
                target.artifact_id: _emu_ctx(
                    target.profile_resource_id, role="GTA", role_level=1,
                    department_ids=[dept],
                ),
            },
        )

        result = await resolve_emulation(
            pool, redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )
        assert result.allowed is True
        assert result.grant_id is not None

    async def test_cross_department_admin_denied(
        self, pool, redis_client, monkeypatch
    ):
        """(b) CROSS-dept (critical): an Administrator whose department does NOT
        overlap the target's is DENIED — even though the role gate alone would
        have allowed the impersonation. Closes the cross-department gap."""
        req_id, tgt_id = uuid4(), uuid4()
        _patch_identities(
            monkeypatch,
            {
                req_id: _emu_ctx(
                    uuid4(), role="Administrator", role_level=3,
                    department_ids=[uuid4()],
                ),
                tgt_id: _emu_ctx(
                    uuid4(), role="GTA", role_level=1,
                    department_ids=[uuid4()],
                ),
            },
        )

        result = await resolve_emulation(
            pool, redis_client,
            requester_profile_id=req_id, target_profile_id=tgt_id,
        )
        assert result.allowed is False
        assert result.reason == "You do not have permission to emulate this profile"
        assert result.grant_id is None

    async def test_self_emulation_ignores_department(
        self, pool, redis_client, monkeypatch, profile_identity_factory
    ):
        """(c) SELF: emulating yourself is allowed irrespective of department."""
        me = await profile_identity_factory(name="emu-self")

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=me.profile_resource_id)
            await refresh_sessions(conn)

        _patch_identities(
            monkeypatch,
            {
                me.artifact_id: _emu_ctx(
                    me.profile_resource_id, role="Administrator", role_level=3,
                    department_ids=[uuid4()],
                ),
            },
        )

        result = await resolve_emulation(
            pool, redis_client,
            requester_profile_id=me.artifact_id, target_profile_id=me.artifact_id,
        )
        assert result.allowed is True
        assert result.grant_id is not None

    async def test_superadmin_emulates_cross_department(
        self, pool, redis_client, monkeypatch, profile_identity_factory
    ):
        """(d) SUPER-ADMIN: global — may emulate a target in a different
        department."""
        requester = await profile_identity_factory(name="emu-super-req")
        target = await profile_identity_factory(name="emu-super-tgt")

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=requester.profile_resource_id)
            await create_session(conn, redis_client, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        _patch_identities(
            monkeypatch,
            {
                requester.artifact_id: _emu_ctx(
                    requester.profile_resource_id, role="Super Administrator",
                    role_level=0, department_ids=[uuid4()],
                ),
                target.artifact_id: _emu_ctx(
                    target.profile_resource_id, role="GTA", role_level=1,
                    department_ids=[uuid4()],  # different department
                ),
            },
        )

        result = await resolve_emulation(
            pool, redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )
        assert result.allowed is True
        assert result.grant_id is not None

    async def test_global_target_emulatable(
        self, pool, redis_client, monkeypatch, profile_identity_factory
    ):
        """(e) GLOBAL target: a target with no department restriction is
        emulatable by a (role-permitted) non-super requester in any department."""
        requester = await profile_identity_factory(name="emu-glob-req")
        target = await profile_identity_factory(name="emu-glob-tgt")

        async with pool.acquire() as conn:
            await create_session(conn, redis_client, profile_id=requester.profile_resource_id)
            await create_session(conn, redis_client, profile_id=target.profile_resource_id)
            await refresh_sessions(conn)

        _patch_identities(
            monkeypatch,
            {
                requester.artifact_id: _emu_ctx(
                    requester.profile_resource_id, role="Administrator", role_level=3,
                    department_ids=[uuid4()],
                ),
                target.artifact_id: _emu_ctx(
                    target.profile_resource_id, role="GTA", role_level=1,
                    department_ids=[],  # global target
                ),
            },
        )

        result = await resolve_emulation(
            pool, redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )
        assert result.allowed is True
        assert result.grant_id is not None
