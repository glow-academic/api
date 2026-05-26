"""Scenario drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.scenario_drafts.types import (
    CreateScenarioDraftResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_scenario_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
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
    pending_ids: set[UUID] | None = None,
) -> CreateScenarioDraftResponse:
    """Create a scenario_drafts entry with optional connection table links.

    pending_ids: resource IDs that should be created with active=false (pending acceptance).
    soft: when True, ALL connections are active=false (overrides pending_ids).
    """
    row = await conn.fetchrow(
        """
        INSERT INTO scenario_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active, mcp
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create scenario_drafts entry")
    draft_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]
    mcp_val = row["mcp"]

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

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            # soft=True → all inactive; otherwise check pending_ids per resource
            is_active = False if soft else (rid not in _pending)
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                is_active,
            )

    # Write-back cache row matching get response shape.
    _pending_strs = {str(x) for x in _pending}
    def _active_list(ids: list[UUID]) -> list[str]:
        if soft:
            return []
        return [str(rid) for rid in ids if str(rid) not in _pending_strs]

    def _pending_list(ids: list[UUID]) -> list[str]:
        if soft:
            return [str(rid) for rid in ids]
        return [str(rid) for rid in ids if str(rid) in _pending_strs]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp_val,
        "active": active_val,
        "session_id": str(session_id),
        "name": name,
        "department_ids": _active_list(department_ids or []),
        "description_ids": _active_list(description_ids or []),
        "document_ids": _active_list(document_ids or []),
        "flag_ids": _active_list(flag_ids or []),
        "image_ids": _active_list(image_ids or []),
        "name_ids": _active_list(name_ids or []),
        "objective_ids": _active_list(objective_ids or []),
        "option_ids": _active_list(option_ids or []),
        "parameter_field_ids": _active_list(parameter_field_ids or []),
        "persona_ids": _active_list(persona_ids or []),
        "problem_statement_ids": _active_list(problem_statement_ids or []),
        "profile_ids": _active_list(profile_ids or []),
        "question_ids": _active_list(question_ids or []),
        "video_ids": _active_list(video_ids or []),
        "pending_name_ids": _pending_list(name_ids or []),
        "pending_description_ids": _pending_list(description_ids or []),
        "pending_problem_statement_ids": _pending_list(problem_statement_ids or []),
        "pending_department_ids": _pending_list(department_ids or []),
        "pending_persona_ids": _pending_list(persona_ids or []),
        "pending_document_ids": _pending_list(document_ids or []),
        "pending_objective_ids": _pending_list(objective_ids or []),
        "pending_image_ids": _pending_list(image_ids or []),
        "pending_video_ids": _pending_list(video_ids or []),
        "pending_question_ids": _pending_list(question_ids or []),
        "pending_option_ids": _pending_list(option_ids or []),
        "pending_flag_ids": _pending_list(flag_ids or []),
        "pending_parameter_field_ids": _pending_list(parameter_field_ids or []),
    }
    await write_back_row(
        redis,
        "scenario_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateScenarioDraftResponse(id=draft_id)
