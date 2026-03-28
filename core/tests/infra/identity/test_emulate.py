"""Tests for infra.auth.emulate using the real grant/emulation path."""

from __future__ import annotations

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
        )
        target = await profile_identity_factory(
            name="Member",
            role=("member", "Member", "Member role"),
        )

        async with pool.acquire() as conn:
            requester_session = await create_session(
                conn,
                profile_id=requester.profile_resource_id,
            )
            target_session = await create_session(
                conn,
                profile_id=target.profile_resource_id,
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
                session_ids=[requester_session.id],
                bypass_mv=True,
                active=True,
            )
            emulations = await search_emulations(
                conn,
                session_ids=[target_session.id],
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
                profile_id=fixture.profile_resource_id,
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
                session_ids=[session.id],
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
            await create_session(conn, profile_id=requester.profile_resource_id)
            await create_session(conn, profile_id=target.profile_resource_id)
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
        )
        target = await profile_identity_factory(
            role=("member", "Member", "Member role"),
        )

        async with pool.acquire() as conn:
            await create_session(conn, profile_id=target.profile_resource_id)
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
        )
        target = await profile_identity_factory(
            role=("member", "Member", "Member role"),
        )

        async with pool.acquire() as conn:
            await create_session(conn, profile_id=requester.profile_resource_id)
            await refresh_sessions(conn)

        result = await resolve_emulation(
            pool,
            redis_client,
            requester_profile_id=requester.artifact_id,
            target_profile_id=target.artifact_id,
        )

        assert result.allowed is False
        assert result.reason == "No active session found for target"
