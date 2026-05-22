"""Chat drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.chat_drafts.types import CreateChatDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_chat_draft(
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
    field_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    objective_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    problem_statement_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateChatDraftResponse:
    """Create or update a chat_drafts entry with optional connection table links."""
    row = await conn.fetchrow(
        """
        INSERT INTO chat_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create chat_drafts entry")

    draft_id = row["id"]
    created_at = row["created_at"]
    actual_active = row["active"]

    connections: list[tuple[str, str, list[UUID]]] = [
        ("chat_drafts_departments_connection", "departments_id", department_ids or []),
        (
            "chat_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("chat_drafts_documents_connection", "documents_id", document_ids or []),
        ("chat_drafts_fields_connection", "fields_id", field_ids or []),
        ("chat_drafts_flags_connection", "flags_id", flag_ids or []),
        ("chat_drafts_images_connection", "images_id", image_ids or []),
        ("chat_drafts_names_connection", "names_id", name_ids or []),
        ("chat_drafts_objectives_connection", "objectives_id", objective_ids or []),
        ("chat_drafts_options_connection", "options_id", option_ids or []),
        (
            "chat_drafts_parameter_fields_connection",
            "parameter_fields_id",
            parameter_field_ids or [],
        ),
        ("chat_drafts_parameters_connection", "parameters_id", parameter_ids or []),
        ("chat_drafts_personas_connection", "personas_id", persona_ids or []),
        (
            "chat_drafts_problem_statements_connection",
            "problem_statements_id",
            problem_statement_ids or [],
        ),
        ("chat_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("chat_drafts_questions_connection", "questions_id", question_ids or []),
        ("chat_drafts_scenarios_connection", "scenarios_id", scenario_ids or []),
        ("chat_drafts_videos_connection", "videos_id", video_ids or []),
    ]

    _pending = pending_ids or set()
    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in _pending),
            )

    def _committed(ids: list[UUID] | None) -> list[str]:
        return [str(rid) for rid in (ids or [])]

    def _pending_only(ids: list[UUID] | None) -> list[str]:
        if soft:
            return [str(rid) for rid in (ids or [])]
        return [str(rid) for rid in (ids or []) if rid in _pending]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": actual_active,
        "session_id": str(session_id),
        "name": name,
        "department_ids": _committed(department_ids),
        "pending_department_ids": _pending_only(department_ids),
        "description_ids": _committed(description_ids),
        "pending_description_ids": _pending_only(description_ids),
        "document_ids": _committed(document_ids),
        "pending_document_ids": _pending_only(document_ids),
        "field_ids": _committed(field_ids),
        "pending_field_ids": _pending_only(field_ids),
        "flag_ids": _committed(flag_ids),
        "pending_flag_ids": _pending_only(flag_ids),
        "image_ids": _committed(image_ids),
        "pending_image_ids": _pending_only(image_ids),
        "name_ids": _committed(name_ids),
        "pending_name_ids": _pending_only(name_ids),
        "objective_ids": _committed(objective_ids),
        "pending_objective_ids": _pending_only(objective_ids),
        "option_ids": _committed(option_ids),
        "pending_option_ids": _pending_only(option_ids),
        "parameter_field_ids": _committed(parameter_field_ids),
        "pending_parameter_field_ids": _pending_only(parameter_field_ids),
        "parameter_ids": _committed(parameter_ids),
        "pending_parameter_ids": _pending_only(parameter_ids),
        "persona_ids": _committed(persona_ids),
        "pending_persona_ids": _pending_only(persona_ids),
        "problem_statement_ids": _committed(problem_statement_ids),
        "pending_problem_statement_ids": _pending_only(problem_statement_ids),
        "profile_ids": _committed(profile_ids),
        "question_ids": _committed(question_ids),
        "pending_question_ids": _pending_only(question_ids),
        "scenario_ids": _committed(scenario_ids),
        "pending_scenario_ids": _pending_only(scenario_ids),
        "video_ids": _committed(video_ids),
        "pending_video_ids": _pending_only(video_ids),
    }
    await write_back_row(
        redis,
        "chat_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateChatDraftResponse(id=draft_id)
