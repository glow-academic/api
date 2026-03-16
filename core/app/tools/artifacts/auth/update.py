"""Auth artifact UPDATE — tool layer.

Efficient junction updates: only deactivate removed IDs, upsert new ones,
and touch (updated_at) unchanged ones.
"""

from typing import Any
from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.auth.types import UpdateAuthResponse

_UNSET: Any = object()

OWNER_COL = "auth_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("auth_names_junction", "names_id", "auth_names_pkey"),
    ("auth_descriptions_junction", "descriptions_id", "auth_descriptions_pkey"),
    ("auth_slugs_junction", "slugs_id", "auth_slugs_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("auth_departments_junction", "departments_id", "auth_departments_pkey"),
    ("auth_items_junction", "items_id", "auth_items_pkey"),
    ("auth_protocols_junction", "protocols_id", "auth_protocols_pkey"),
    ("auth_auths_junction", "auths_id", "auth_auths_junction_pkey"),
]


async def update_auth(
    conn: asyncpg.Connection,
    auth_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    slug_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    protocol_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateAuthResponse:
    """Update an auth artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE auth_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            auth_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE auth_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            auth_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id, slug_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=auth_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        item_ids,
        protocol_ids,
        auth_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=auth_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="auth_flags_junction",
            owner_col=OWNER_COL,
            owner_id=auth_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="auth_flags_pkey",
            mcp=mcp,
        )

    return UpdateAuthResponse(id=auth_id)
