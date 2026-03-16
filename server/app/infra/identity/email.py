"""Resolve profile by email — composes canonical black boxes.

Given an email address and optional actor profile_id:
  1. search_emails → find email resource matching the address
  2. search_profiles → find profile artifact owning that email
  3. resolve_profile_identity_context → hydrate full profile identity
  4. resolve_profile_identity_context → actor name (if actor provided)

No inline SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.emails.search import search_emails


@dataclass(frozen=True)
class ProfileByEmailResult:
    """Result of a profile-by-email lookup."""

    profile_id: UUID
    name: str
    emails: list[str]
    primary_email: str | None
    role: str
    active: bool
    req_per_day: int | None
    primary_department_id: UUID | None
    actor_name: str | None


async def resolve_profile_by_email(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    email: str,
    actor_profile_id: UUID | None = None,
    bypass_cache: bool = False,
) -> ProfileByEmailResult | None:
    """Look up a profile by email using canonical black boxes.

    Returns None if no profile matches the email.
    """
    # Step 1: Find email resource matching the address
    async with pool.acquire() as conn:
        email_results = await search_emails(
            conn, redis, search=email, limit_count=100, bypass_cache=bypass_cache
        )

    # Filter to exact match (search_emails does ILIKE substring matching)
    matching_email_ids = [
        e.id for e in email_results if e.email.lower() == email.lower()
    ]
    if not matching_email_ids:
        return None

    # Step 2: Find profile artifact owning that email
    async with pool.acquire() as conn:
        artifact_ids, _total = await search_profiles(
            conn, email_ids=matching_email_ids, active_only=False, limit_count=1
        )
    if not artifact_ids:
        return None

    target_id = artifact_ids[0]

    # Step 3: Hydrate profile identity
    identity = await resolve_profile_identity_context(
        pool, target_id, redis, bypass_cache=bypass_cache
    )
    if not identity:
        return None

    # Step 4: Resolve actor name if actor_profile_id provided
    actor_name: str | None = None
    if actor_profile_id:
        actor_identity = await resolve_profile_identity_context(
            pool, actor_profile_id, redis, bypass_cache=bypass_cache
        )
        if actor_identity:
            actor_name = actor_identity.name

    return ProfileByEmailResult(
        profile_id=target_id,
        name=identity.name,
        emails=identity.emails,
        primary_email=identity.primary_email,
        role=identity.role,
        active=identity.is_active,
        req_per_day=identity.requests_per_day,
        primary_department_id=identity.primary_department_id,
        actor_name=actor_name,
    )
