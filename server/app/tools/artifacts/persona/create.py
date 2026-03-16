"""Persona artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.persona.types import CreatePersonaResponse

OWNER_COL = "persona_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("persona_names_junction", "names_id"),
    ("persona_descriptions_junction", "descriptions_id"),
    ("persona_colors_junction", "colors_id"),
    ("persona_icons_junction", "icons_id"),
    ("persona_instructions_junction", "instructions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("persona_departments_junction", "departments_id"),
    ("persona_parameter_fields_junction", "parameter_fields_id"),
    ("persona_personas_junction", "personas_id"),
    ("persona_voices_junction", "voices_id"),
]


async def create_persona(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    color_id: UUID | None = None,
    icon_id: UUID | None = None,
    instruction_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    example_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreatePersonaResponse:
    """Create a persona artifact with optional junction links."""
    is_active = not soft if active is None else active
    persona_id: UUID = await conn.fetchval(
        """
        INSERT INTO persona_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id, color_id, icon_id, instruction_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=persona_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [department_ids, parameter_field_ids, persona_ids, voice_ids]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=persona_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Examples with idx
    if example_ids:
        await insert_multi(
            conn,
            table="persona_examples_junction",
            owner_col=OWNER_COL,
            owner_id=persona_id,
            resource_col="examples_id",
            resource_ids=example_ids,
            generated=generated,
            mcp=mcp,
        )

    # Flags with value
    if flag_ids:
        await insert_multi(
            conn,
            table="persona_flags_junction",
            owner_col=OWNER_COL,
            owner_id=persona_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreatePersonaResponse(id=persona_id)
