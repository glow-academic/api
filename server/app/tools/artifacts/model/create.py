"""Model artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.model.types import CreateModelResponse

OWNER_COL = "model_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("model_names_junction", "names_id"),
    ("model_descriptions_junction", "descriptions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("model_departments_junction", "departments_id"),
    ("model_modalities_junction", "modalities_id"),
    ("model_models_junction", "models_id"),
    ("model_pricing_junction", "pricing_id"),
    ("model_providers_junction", "providers_id"),
    ("model_qualities_junction", "qualities_id"),
    ("model_reasoning_levels_junction", "reasoning_levels_id"),
    ("model_temperature_levels_junction", "temperature_levels_id"),
    ("model_values_junction", "values_id"),
    ("model_voices_junction", "voices_id"),
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
    provider_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    value_ids: list[UUID] | None = None,
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
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=model_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [
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
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=model_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="model_flags_junction",
            owner_col=OWNER_COL,
            owner_id=model_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateModelResponse(id=model_id)
