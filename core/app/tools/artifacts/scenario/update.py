"""Scenario artifact UPDATE — tool layer.

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
from app.tools.artifacts.scenario.types import UpdateScenarioResponse

_UNSET: Any = object()

OWNER_COL = "scenario_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("scenario_names_junction", "names_id", "scenario_names_pkey"),
    ("scenario_descriptions_junction", "descriptions_id", "scenario_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("scenario_departments_junction", "departments_id", "scenario_departments_pkey"),
    ("scenario_documents_junction", "documents_id", "scenario_documents_pkey"),
    ("scenario_images_junction", "images_id", "scenario_images_pkey"),
    ("scenario_objectives_junction", "objectives_id", "scenario_objectives_pkey"),
    ("scenario_options_junction", "options_id", "scenario_options_pkey"),
    (
        "scenario_parameter_fields_junction",
        "parameter_fields_id",
        "scenario_parameter_fields_pkey",
    ),
    ("scenario_personas_junction", "personas_id", "scenario_personas_pkey"),
    (
        "scenario_problem_statements_junction",
        "problem_statements_id",
        "scenario_problem_statements_pkey",
    ),
    ("scenario_questions_junction", "questions_id", "scenario_questions_pkey"),
    ("scenario_videos_junction", "videos_id", "scenario_videos_pkey"),
    ("scenario_scenarios_junction", "scenarios_id", "scenario_scenarios_junction_pkey"),
]


async def update_scenario(
    conn: asyncpg.Connection,
    scenario_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    objective_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    problem_statement_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateScenarioResponse:
    """Update a scenario artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE scenario_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            scenario_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE scenario_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            scenario_id,
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
                owner_id=scenario_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        document_ids,
        image_ids,
        objective_ids,
        option_ids,
        parameter_field_ids,
        persona_ids,
        problem_statement_ids,
        question_ids,
        video_ids,
        scenario_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=scenario_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="scenario_flags_junction",
            owner_col=OWNER_COL,
            owner_id=scenario_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="scenario_flags_pkey",
            mcp=mcp,
        )

    return UpdateScenarioResponse(id=scenario_id)
