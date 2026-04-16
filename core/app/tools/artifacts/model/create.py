"""Model artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.model.types import CreateModelResponse

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
    ("model_reasoning_levels_junction", "reasoning_levels_id", "model_reasoning_levels_pkey"),
    ("model_temperature_levels_junction", "temperature_levels_id", "model_temperature_levels_pkey"),
    ("model_values_junction", "values_id", "model_values_pkey"),
    ("model_voices_junction", "voices_id", "model_voices_pkey"),
]


async def create_model(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    pricing_ids: list[UUID] | None = None,
    provider_id: UUID | None = None,
    quality_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    value_id: UUID | None = None,
    voice_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateModelResponse:
    """Create a model artifact with optional junction links."""
    is_active = not soft if active is None else active
    model_id: UUID = await conn.fetchval(
        """
        INSERT INTO model_artifact (id, active, generated, mcp)
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
                owner_id=model_id,
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
        modality_ids,
        model_ids,
        pricing_ids,
        [provider_id] if provider_id else None,
        quality_ids,
        reasoning_level_ids,
        temperature_level_ids,
        [value_id] if value_id else None,
        voice_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=model_id,
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
            table="model_flags_junction",
            owner_col=OWNER_COL,
            owner_id=model_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="model_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateModelResponse(id=model_id)
