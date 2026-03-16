"""Profile artifact UPDATE — tool layer.

Efficient junction updates: only deactivate removed IDs, upsert new ones,
and touch (updated_at) unchanged ones.
"""

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.profile.types import UpdateProfileResponse
from app.tools.resources.emails.get import get_emails
from app.tools.resources.request_limits.get import get_request_limits

_UNSET: Any = object()

OWNER_COL = "profile_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("profile_names_junction", "names_id", "profile_names_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("profile_departments_junction", "departments_id", "profile_departments_pkey"),
    ("profile_roles_junction", "roles_id", "profile_roles_pkey"),
    ("profile_profiles_junction", "profiles_id", "profile_profiles_junction_pkey"),
]


async def _lookup_email_values(
    conn: asyncpg.Connection,
    email_ids: list[UUID],
    redis: Redis,
) -> list[tuple[UUID, str]]:
    items = await get_emails(conn, email_ids, redis, bypass_cache=True)
    return [(item.id, item.email) for item in items]


async def _upsert_profile_emails(
    conn: asyncpg.Connection,
    *,
    profile_id: UUID,
    email_ids: list[UUID],
    redis: Redis,
    mcp: bool,
) -> None:
    if not email_ids:
        await conn.execute(
            "UPDATE profile_emails_junction SET active = false WHERE profile_id = $1 AND active = true",
            profile_id,
        )
        return

    values = await _lookup_email_values(conn, email_ids, redis)
    new_ids = [email_id for email_id, _ in values]
    await conn.execute(
        """
        UPDATE profile_emails_junction
        SET active = false
        WHERE profile_id = $1 AND active = true AND emails_id != ALL($2::uuid[])
        """,
        profile_id,
        new_ids,
    )
    await conn.executemany(
        """
        INSERT INTO profile_emails_junction
            (profile_id, emails_id, email, mcp)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT ON CONSTRAINT profile_emails_pkey
        DO UPDATE SET email = EXCLUDED.email, active = true, mcp = EXCLUDED.mcp
        """,
        [(profile_id, email_id, email_value, mcp) for email_id, email_value in values],
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


async def _upsert_profile_request_limit(
    conn: asyncpg.Connection,
    *,
    profile_id: UUID,
    request_limit_id: UUID,
    redis: Redis,
    mcp: bool,
) -> None:
    requests_per_day = await _lookup_request_limit_value(conn, request_limit_id, redis)
    updated = await conn.execute(
        """
        UPDATE profile_request_limits_junction
        SET
            request_limits_id = $2,
            requests_per_day = $3,
            active = true,
            mcp = $4
        WHERE profile_id = $1
        """,
        profile_id,
        request_limit_id,
        requests_per_day,
        mcp,
    )
    if updated != "UPDATE 1":
        await conn.execute(
            """
        INSERT INTO profile_request_limits_junction
            (profile_id, request_limits_id, requests_per_day, mcp)
        VALUES ($1, $2, $3, $4)
        """,
            profile_id,
            request_limit_id,
            requests_per_day,
            mcp,
        )


async def update_profile(
    conn: asyncpg.Connection,
    profile_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    request_limit_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    email_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
    redis: Redis | None = None,
) -> UpdateProfileResponse:
    """Update a profile artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE profile_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            profile_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE profile_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            profile_id,
            mcp,
        )

    # 2. Single-select junctions
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, [name_id]):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=profile_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )
    if request_limit_id is not _UNSET:
        if request_limit_id is None:
            await conn.execute(
                """
                UPDATE profile_request_limits_junction
                SET active = false
                WHERE profile_id = $1 AND active = true
                """,
                profile_id,
            )
        else:
            if redis is None:
                raise ValueError("redis is required when request_limit_id is provided")
            await _upsert_profile_request_limit(
                conn,
                profile_id=profile_id,
                request_limit_id=request_limit_id,
                redis=redis,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        role_ids,
        profile_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=profile_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )
    if email_ids is not None:
        if redis is None:
            raise ValueError("redis is required when email_ids are provided")
        await _upsert_profile_emails(
            conn,
            profile_id=profile_id,
            email_ids=email_ids,
            redis=redis,
            mcp=mcp,
        )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="profile_flags_junction",
            owner_col=OWNER_COL,
            owner_id=profile_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="profile_flags_pkey",
            mcp=mcp,
        )

    return UpdateProfileResponse(id=profile_id)
