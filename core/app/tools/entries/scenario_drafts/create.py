"""Scenario drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.scenario_drafts.types import (
    CreateScenarioDraftResponse,
)


async def create_scenario_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    objective_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    problem_statement_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
) -> CreateScenarioDraftResponse:
    """Create a scenario_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO scenario_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        group_id,
        session_id,
        version,
        not soft,
        mcp,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create scenario_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "scenario_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "scenario_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("scenario_drafts_documents_connection", "documents_id", document_ids or []),
        ("scenario_drafts_flags_connection", "flags_id", flag_ids or []),
        ("scenario_drafts_images_connection", "images_id", image_ids or []),
        ("scenario_drafts_names_connection", "names_id", name_ids or []),
        ("scenario_drafts_objectives_connection", "objectives_id", objective_ids or []),
        ("scenario_drafts_options_connection", "options_id", option_ids or []),
        (
            "scenario_drafts_parameter_fields_connection",
            "parameter_fields_id",
            parameter_field_ids or [],
        ),
        ("scenario_drafts_personas_connection", "personas_id", persona_ids or []),
        (
            "scenario_drafts_problem_statements_connection",
            "problem_statements_id",
            problem_statement_ids or [],
        ),
        ("scenario_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("scenario_drafts_questions_connection", "questions_id", question_ids or []),
        ("scenario_drafts_videos_connection", "videos_id", video_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateScenarioDraftResponse(id=draft_id)
