"""Model artifact UPDATE — tool layer.

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
from app.tools.artifacts.model.types import UpdateModelResponse

_UNSET: Any = object()

OWNER_COL = "model_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("model_names_junction", "names_id", "model_names_pkey"),
    ("model_descriptions_junction", "descriptions_id", "model_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("model_departments_junction", "departments_id", "model_departments_pkey"),
    ("model_modalities_junction", "modalities_id", "model_modalities_pkey"),
    ("model_models_junction", "models_id", "model_models_junction_pkey"),
    ("model_pricing_junction", "pricing_id", "model_pricing_pkey"),
    ("model_providers_junction", "providers_id", "model_providers_junction_pkey"),
    ("model_qualities_junction", "qualities_id", "model_qualities_pkey"),
    (
        "model_reasoning_levels_junction",
        "reasoning_levels_id",
        "model_reasoning_levels_pkey",
    ),
    (
        "model_temperature_levels_junction",
        "temperature_levels_id",
        "model_temperature_levels_pkey",
    ),
    ("model_values_junction", "values_id", "model_values_pkey"),
    ("model_voices_junction", "voices_id", "model_voices_pkey"),
]


async def update_model(
    conn: asyncpg.Connection,
    model_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    pricing_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    value_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateModelResponse:
    """Update a model artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE model_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            model_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE model_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            model_id,
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
                owner_id=model_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        modality_ids,
        model_ids,
        pricing_ids,
        provider_ids,
        quality_ids,
        reasoning_level_ids,
        temperature_level_ids,
        value_ids,
        voice_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=model_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="model_flags_junction",
            owner_col=OWNER_COL,
            owner_id=model_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="model_flags_pkey",
            mcp=mcp,
        )

    return UpdateModelResponse(id=model_id)
