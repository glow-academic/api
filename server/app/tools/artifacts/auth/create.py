"""Auth artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.auth.types import CreateAuthResponse

OWNER_COL = "auth_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("auth_names_junction", "names_id"),
    ("auth_descriptions_junction", "descriptions_id"),
    ("auth_slugs_junction", "slugs_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("auth_departments_junction", "departments_id"),
    ("auth_items_junction", "items_id"),
    ("auth_protocols_junction", "protocols_id"),
    ("auth_auths_junction", "auths_id"),
]


async def create_auth(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    slug_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    protocol_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateAuthResponse:
    """Create an auth artifact with optional junction links."""
    is_active = not soft if active is None else active
    auth_id: UUID = await conn.fetchval(
        """
        INSERT INTO auth_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id, slug_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=auth_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [department_ids, item_ids, protocol_ids, auth_ids]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=auth_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="auth_flags_junction",
            owner_col=OWNER_COL,
            owner_id=auth_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateAuthResponse(id=auth_id)
