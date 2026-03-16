"""Profile artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.profile.types import CreateProfileResponse
from app.tools.resources.emails.get import get_emails
from app.tools.resources.request_limits.get import get_request_limits

OWNER_COL = "profile_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [("profile_names_junction", "names_id")]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("profile_departments_junction", "departments_id"),
    ("profile_roles_junction", "roles_id"),
    ("profile_profiles_junction", "profiles_id"),
]


async def _lookup_email_values(
    conn: asyncpg.Connection,
    email_ids: list[UUID],
    redis: Redis,
) -> list[tuple[UUID, str]]:
    items = await get_emails(conn, email_ids, redis, bypass_cache=True)
    return [(item.id, item.email) for item in items]


async def _insert_profile_emails(
    conn: asyncpg.Connection,
    *,
    profile_id: UUID,
    email_ids: list[UUID],
    redis: Redis,
    generated: bool,
    mcp: bool,
) -> None:
    if not email_ids:
        return

    values = await _lookup_email_values(conn, email_ids, redis)
    await conn.executemany(
        """
        INSERT INTO profile_emails_junction
            (profile_id, emails_id, email, generated, mcp)
        VALUES ($1, $2, $3, $4, $5)
        """,
        [
            (profile_id, email_id, email_value, generated, mcp)
            for email_id, email_value in values
        ],
    )


async def _lookup_request_limit_value(
    conn: asyncpg.Connection,
    request_limit_id: UUID,
    redis: Redis,
) -> int:
    items = await get_request_limits(conn, [request_limit_id], redis, bypass_cache=True)
    if not items:
        raise ValueError(f"Unknown request_limit_id: {request_limit_id}")
    return items[0].requests_per_day


async def _insert_profile_request_limit(
    conn: asyncpg.Connection,
    *,
    profile_id: UUID,
    request_limit_id: UUID,
    redis: Redis,
    generated: bool,
    mcp: bool,
) -> None:
    requests_per_day = await _lookup_request_limit_value(conn, request_limit_id, redis)
    await conn.execute(
        """
        INSERT INTO profile_request_limits_junction
            (profile_id, request_limits_id, requests_per_day, generated, mcp)
        VALUES ($1, $2, $3, $4, $5)
        """,
        profile_id,
        request_limit_id,
        requests_per_day,
        generated,
        mcp,
    )


async def create_profile(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    request_limit_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    email_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
    redis: Redis | None = None,
) -> CreateProfileResponse:
    """Create a profile artifact with optional junction links."""
    is_active = not soft if active is None else active
    profile_id: UUID = await conn.fetchval(
        """
        INSERT INTO profile_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    for (table, col), val in zip(SINGLE_JUNCTIONS, [name_id]):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=profile_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )
    if request_limit_id is not None:
        if redis is None:
            raise ValueError("redis is required when request_limit_id is provided")
        await _insert_profile_request_limit(
            conn,
            profile_id=profile_id,
            request_limit_id=request_limit_id,
            redis=redis,
            generated=generated,
            mcp=mcp,
        )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        role_ids,
        profile_ids,
    ]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=profile_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )
    if email_ids:
        if redis is None:
            raise ValueError("redis is required when email_ids are provided")
        await _insert_profile_emails(
            conn,
            profile_id=profile_id,
            email_ids=email_ids,
            redis=redis,
            generated=generated,
            mcp=mcp,
        )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="profile_flags_junction",
            owner_col=OWNER_COL,
            owner_id=profile_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateProfileResponse(id=profile_id)
