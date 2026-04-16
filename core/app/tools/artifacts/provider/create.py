"""Provider artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.provider.types import CreateProviderResponse

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


async def create_provider(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    endpoint_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    value_id: UUID | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateProviderResponse:
    """Create a provider artifact with optional junction links."""
    is_active = not soft if active is None else active
    provider_id: UUID = await conn.fetchval(
        """
        INSERT INTO provider_artifact (id, active, generated, mcp)
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
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=provider_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions (simple)
    multi_vals = [department_ids, endpoint_ids, key_ids, provider_ids, [value_id] if value_id else None]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=provider_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="provider_flags_junction",
            owner_col=OWNER_COL,
            owner_id=provider_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="provider_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateProviderResponse(id=provider_id)
