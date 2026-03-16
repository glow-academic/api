"""Persona artifact UPDATE — tool layer.

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
from app.tools.artifacts.persona.types import UpdatePersonaResponse

_UNSET: Any = object()

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
    (
        "persona_parameter_fields_junction",
        "parameter_fields_id",
        "persona_parameter_fields_junction_pkey",
    ),
    ("persona_personas_junction", "personas_id", "persona_personas_junction_pkey"),
    ("persona_voices_junction", "voices_id", "persona_voices_junction_pkey"),
]


async def update_persona(
    conn: asyncpg.Connection,
    persona_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    color_id: UUID | Any = _UNSET,
    icon_id: UUID | Any = _UNSET,
    instruction_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    example_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdatePersonaResponse:
    """Update a persona artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE persona_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            persona_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE persona_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            persona_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id, color_id, icon_id, instruction_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
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

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        parameter_field_ids,
        persona_ids,
        voice_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
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

    # 4. Examples with idx
    if example_ids is not None:
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

    # 5. Flags with value
    if flag_ids is not None:
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

    return UpdatePersonaResponse(id=persona_id)
