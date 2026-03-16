"""Provider artifact UPDATE — tool layer.

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
from app.tools.artifacts.provider.types import UpdateProviderResponse

_UNSET: Any = object()

OWNER_COL = "provider_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("provider_names_junction", "names_id", "provider_names_pkey"),
    ("provider_descriptions_junction", "descriptions_id", "provider_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("provider_departments_junction", "departments_id", "provider_departments_pkey"),
    ("provider_endpoints_junction", "endpoints_id", "provider_endpoints_junction_pkey"),
    ("provider_keys_junction", "keys_id", "provider_keys_junction_pkey"),
    ("provider_providers_junction", "providers_id", "provider_providers_junction_pkey"),
    ("provider_values_junction", "values_id", "provider_values_pkey"),
]


async def update_provider(
    conn: asyncpg.Connection,
    provider_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    endpoint_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    value_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateProviderResponse:
    """Update a provider artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE provider_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            provider_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE provider_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            provider_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=provider_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        endpoint_ids,
        key_ids,
        provider_ids,
        value_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=provider_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="provider_flags_junction",
            owner_col=OWNER_COL,
            owner_id=provider_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="provider_flags_pkey",
            mcp=mcp,
        )

    return UpdateProviderResponse(id=provider_id)
