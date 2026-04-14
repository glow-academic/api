"""Persona artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.persona.types import CreatePersonaResponse

OWNER_COL = "persona_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("persona_names_junction", "names_id", "persona_names_pkey"),
    ("persona_descriptions_junction", "descriptions_id", "persona_descriptions_pkey"),
    ("persona_colors_junction", "colors_id", "persona_colors_pkey"),
    ("persona_icons_junction", "icons_id", "persona_icons_pkey"),
    ("persona_instructions_junction", "instructions_id", "persona_instructions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("persona_departments_junction", "departments_id", "persona_departments_pkey"),
    ("persona_parameter_fields_junction", "parameter_fields_id", "persona_parameter_fields_junction_pkey"),
    ("persona_personas_junction", "personas_id", "persona_personas_junction_pkey"),
    ("persona_voices_junction", "voices_id", "persona_voices_junction_pkey"),
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
    """Create a persona artifact with optional junction links.

    Idempotent: if id is provided and already exists, ON CONFLICT promotes
    the artifact. Junction rows use existing upsert_single/upsert_multi.
    """
    is_active = not soft if active is None else active
    persona_id: UUID = await conn.fetchval(
        """
        INSERT INTO persona_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions — upsert_single handles ON CONFLICT
    single_vals = [name_id, description_id, color_id, icon_id, instruction_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=persona_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # Multi-select junctions — upsert_multi handles ON CONFLICT
    multi_vals: list[list[UUID] | None] = [
        department_ids, parameter_field_ids, persona_ids, voice_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=persona_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # Examples
    if example_ids:
        await upsert_multi(
            conn,
            table="persona_examples_junction",
            owner_col=OWNER_COL,
            owner_id=persona_id,
            resource_col="examples_id",
            resource_ids=example_ids,
            constraint="persona_examples_pkey",
            mcp=mcp,
        )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="persona_flags_junction",
            owner_col=OWNER_COL,
            owner_id=persona_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="persona_flags_pkey",
            mcp=mcp,
        )

    return CreatePersonaResponse(id=persona_id)
