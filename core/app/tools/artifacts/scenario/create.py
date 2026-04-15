"""Scenario artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.scenario.types import CreateScenarioResponse

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
    ("scenario_parameter_fields_junction", "parameter_fields_id", "scenario_parameter_fields_pkey"),
    ("scenario_personas_junction", "personas_id", "scenario_personas_pkey"),
    ("scenario_problem_statements_junction", "problem_statements_id", "scenario_problem_statements_pkey"),
    ("scenario_questions_junction", "questions_id", "scenario_questions_pkey"),
    ("scenario_videos_junction", "videos_id", "scenario_videos_pkey"),
    ("scenario_scenarios_junction", "scenarios_id", "scenario_scenarios_junction_pkey"),
]


async def create_scenario(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
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
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateScenarioResponse:
    """Create a scenario artifact with optional junction links.

    Idempotent: if id is provided and already exists, ON CONFLICT promotes
    the artifact. Junction rows use existing upsert_single/upsert_multi.
    """
    is_active = not soft if active is None else active
    scenario_id: UUID = await conn.fetchval(
        """
        INSERT INTO scenario_artifact (id, active, generated, mcp)
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
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=scenario_id,
                resource_col=col,
                resource_id=val,
                mcp=mcp,
                constraint=constraint,
                soft=soft,
            )

    # Multi-select junctions — upsert_multi handles ON CONFLICT
    multi_vals = [
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
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=scenario_id,
                resource_col=col,
                resource_ids=vals,
                mcp=mcp,
                constraint=constraint,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="scenario_flags_junction",
            owner_col=OWNER_COL,
            owner_id=scenario_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            mcp=mcp,
            constraint="scenario_flags_pkey",
            soft=soft,
        )

    return CreateScenarioResponse(id=scenario_id)
