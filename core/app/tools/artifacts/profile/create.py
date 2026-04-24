"""Profile artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.profile.types import CreateProfileResponse
from app.tools.resources.emails.get import get_emails

OWNER_COL = "profile_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("profile_names_junction", "names_id", "profile_names_pkey"),
    (
        "profile_primary_departments_junction",
        "primary_departments_id",
        "profile_primary_departments_pkey",
    ),
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


async def _insert_profile_emails(
    conn: asyncpg.Connection,
    *,
    profile_id: UUID,
    email_ids: list[UUID],
    redis: Redis,
    generated: bool,
    mcp: bool,
    soft: bool,
) -> None:
    if not email_ids:
        return

    values = await _lookup_email_values(conn, email_ids, redis)
    await conn.executemany(
        """
        INSERT INTO profile_emails_junction
            (profile_id, emails_id, email, generated, mcp, active)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT ON CONSTRAINT profile_emails_pkey
        DO UPDATE SET
            email = EXCLUDED.email,
            generated = EXCLUDED.generated,
            mcp = EXCLUDED.mcp,
            active = EXCLUDED.active
        """,
        [
            (profile_id, email_id, email_value, generated, mcp, not soft)
            for email_id, email_value in values
        ],
    )


async def create_profile(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    primary_departments_id: UUID | None = None,
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
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    for (table, col, constraint), val in zip(
        SINGLE_JUNCTIONS, [name_id, primary_departments_id]
    ):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=profile_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )
    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        role_ids,
        profile_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=profile_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
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
            soft=soft,
        )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="profile_flags_junction",
            owner_col=OWNER_COL,
            owner_id=profile_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="profile_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateProfileResponse(id=profile_id)
