"""Tests for infra.auth.email using the real profile/email lookup path."""

from __future__ import annotations

import pytest

from app.infra.identity.email import ProfileByEmailResult, resolve_profile_by_email
from app.tools.resources.emails.create import create_email

pytestmark = pytest.mark.asyncio


class TestResolveProfileByEmail:
    async def test_returns_full_result(
        self, pool, redis_client, profile_identity_factory
    ):
        fixture = await profile_identity_factory(
            name="Bob",
            role=("member", "Member", "Member role"),
            emails=["bob@example.com", "bob2@example.com"],
        )

        result = await resolve_profile_by_email(
            pool,
            redis_client,
            email=fixture.emails[0],
        )

        assert isinstance(result, ProfileByEmailResult)
        assert result is not None
        assert result.profile_id == fixture.artifact_id
        assert result.name == fixture.name
        assert result.role == fixture.role
        assert result.emails == fixture.emails
        assert result.active is True
        assert result.actor_name is None

    async def test_case_insensitive_email_match(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        fixture = await profile_identity_factory(emails=["Alice@example.com"])

        result = await resolve_profile_by_email(
            pool,
            redis_client,
            email=fixture.emails[0].upper(),
        )

        assert result is not None
        assert result.profile_id == fixture.artifact_id

    async def test_actor_name_resolved_from_actor_profile(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        target = await profile_identity_factory(
            name="Target",
            emails=["target@example.com"],
        )
        actor = await profile_identity_factory(
            name="Actor",
            emails=["actor@example.com"],
        )

        result = await resolve_profile_by_email(
            pool,
            redis_client,
            email=target.emails[0],
            actor_profile_id=actor.artifact_id,
        )

        assert result is not None
        assert result.name == target.name
        assert result.actor_name == actor.name

    async def test_no_email_match_returns_none(self, pool, redis_client):
        result = await resolve_profile_by_email(
            pool,
            redis_client,
            email="nobody@example.com",
        )

        assert result is None

    async def test_email_substring_match_but_no_exact_returns_none(
        self,
        pool,
        redis_client,
        profile_identity_factory,
    ):
        await profile_identity_factory(emails=["alice@example.com.au"])

        result = await resolve_profile_by_email(
            pool,
            redis_client,
            email="alice@example.com",
        )

        assert result is None

    async def test_no_profile_for_email_returns_none(self, pool, redis_client):
        async with pool.acquire() as conn:
            orphan_email = await create_email(
                conn,
                email="orphan@example.com",
                redis=redis_client,
            )

        result = await resolve_profile_by_email(
            pool,
            redis_client,
            email=orphan_email.email,
        )

        assert result is None
