"""Attempt chat CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_chat.types import CreateAttemptChatResponse
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_chat(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    chat_id: UUID,
    id: UUID | None = None,
    assistant_persona_ids: list[UUID] | None = None,
    title: str = "",
    position: int = 0,
    time_limit: int | None = None,
    negative_time: bool = False,
    audio_enabled: bool = False,
    text_enabled: bool = False,
    hints_enabled: bool = False,
    copy_paste_allowed: bool = False,
    show_images: bool = False,
    show_objectives: bool = False,
    show_problem_statement: bool = False,
    analyses_enabled: bool = False,
    improvements_enabled: bool = False,
    strengths_enabled: bool = False,
    use_custom: bool = False,
    use_previous: bool = False,
    problem_statement_enabled: bool = False,
    objectives_enabled: bool = False,
    video_enabled: bool = False,
    images_enabled: bool = False,
    questions_enabled: bool = False,
    rubrics_ids: list[UUID] | None = None,
    standards_ids: list[UUID] | None = None,
    standard_groups_ids: list[UUID] | None = None,
    departments_ids: list[UUID] | None = None,
    personas_ids: list[UUID] | None = None,
    problem_statements_ids: list[UUID] | None = None,
    objectives_ids: list[UUID] | None = None,
    questions_ids: list[UUID] | None = None,
    options_ids: list[UUID] | None = None,
    videos_ids: list[UUID] | None = None,
    images_ids: list[UUID] | None = None,
    documents_ids: list[UUID] | None = None,
    parameter_fields_ids: list[UUID] | None = None,
    names_ids: list[UUID] | None = None,
    descriptions_ids: list[UUID] | None = None,
    parameters_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptChatResponse:
    """Create an attempt_chat entry with optional connection tables."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_chat_entry (
            id, session_id, chat_id, title, "position", time_limit,
            negative_time, audio_enabled, text_enabled, hints_enabled,
            copy_paste_allowed, show_images, show_objectives,
            show_problem_statement, analyses_enabled, improvements_enabled,
            strengths_enabled, use_custom, use_previous,
            problem_statement_enabled, objectives_enabled, video_enabled,
            images_enabled, questions_enabled,
            assistant_persona_ids, active, mcp, generated, created_at
        )
        VALUES (
            COALESCE($27, uuidv7()), $1, $2, $3, $4, $5,
            $6, $7, $8, $9,
            $10, $11, $12,
            $13, $14, $15,
            $16, $17, $18,
            $19, $20, $21,
            $22, $23,
            $24, $25, $26, true, COALESCE($28, NOW())
        )
        RETURNING id, created_at
        """,
        session_id,
        chat_id,
        title,
        position,
        time_limit,
        negative_time,
        audio_enabled,
        text_enabled,
        hints_enabled,
        copy_paste_allowed,
        show_images,
        show_objectives,
        show_problem_statement,
        analyses_enabled,
        improvements_enabled,
        strengths_enabled,
        use_custom,
        use_previous,
        problem_statement_enabled,
        objectives_enabled,
        video_enabled,
        images_enabled,
        questions_enabled,
        assistant_persona_ids or [],
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create attempt_chat entry")

    attempt_chat_id = row["id"]
    actual_created_at = row["created_at"]

    # Connection tables (all optional)
    _connections: list[tuple[str, str, list[UUID] | None]] = [
        ("attempt_chat_rubrics_connection", "rubrics_id", rubrics_ids),
        ("attempt_chat_standards_connection", "standards_id", standards_ids),
        (
            "attempt_chat_standard_groups_connection",
            "standard_groups_id",
            standard_groups_ids,
        ),
        ("attempt_chat_departments_connection", "departments_id", departments_ids),
        ("attempt_chat_personas_connection", "personas_id", personas_ids),
        (
            "attempt_chat_problem_statements_connection",
            "problem_statements_id",
            problem_statements_ids,
        ),
        ("attempt_chat_objectives_connection", "objectives_id", objectives_ids),
        ("attempt_chat_questions_connection", "questions_id", questions_ids),
        ("attempt_chat_options_connection", "options_id", options_ids),
        ("attempt_chat_videos_connection", "videos_id", videos_ids),
        ("attempt_chat_images_connection", "images_id", images_ids),
        ("attempt_chat_documents_connection", "documents_id", documents_ids),
        (
            "attempt_chat_parameter_fields_connection",
            "parameter_fields_id",
            parameter_fields_ids,
        ),
        ("attempt_chat_names_connection", "names_id", names_ids),
        ("attempt_chat_descriptions_connection", "descriptions_id", descriptions_ids),
        ("attempt_chat_parameters_connection", "parameters_id", parameters_ids),
    ]

    for table, col, ids in _connections:
        for resource_id in ids or []:
            await conn.execute(
                f"""
                INSERT INTO {table} (attempt_chat_id, {col}, generated)
                VALUES ($1, $2, true)
                """,
                attempt_chat_id,
                resource_id,
            )

    # Write-back cache row matching get/search MV shape. The MV is keyed by
    # ``chat_id`` (the chat_entry id this attempt_chat points at), so the
    # cache slot is keyed by chat_id too. Heavy MV-derived fields (attempt_id,
    # profile_id, grade_*, resource arrays from chat_mv joins) aren't known at
    # create-time; default to None/[]. The MV row will hydrate them once the
    # next concurrent refresh picks up the insert. Personas come from connection
    # rows that we just wrote; surface those into persona_ids so the cache row
    # is at least directionally useful for filters.
    fresh_row = {
        "chat_id": str(chat_id),
        "attempt_id": None,
        "chat_entry_id": str(chat_id),
        "group_id": None,
        "profile_id": None,
        "role_id": None,
        "cohort_id": None,
        "department_id": None,
        "simulation_id": None,
        "scenario_id": None,
        "persona_ids": [str(p) for p in (personas_ids or [])] or None,
        "assistant_persona_ids": [str(p) for p in (assistant_persona_ids or [])] or None,
        "rubric_id": None,
        "grade_score": None,
        "grade_total_points": None,
        "grade_pass_points": None,
        "grade_passed": None,
        "grade_time_taken": None,
        "completed": None,
        "attempt_number": None,
        "chat_created_at": actual_created_at.isoformat() if actual_created_at else None,
        "attempt_date": None,
        "attempt_type": None,
        "is_archived": None,
        "infinite_mode": None,
        "document_ids": [str(d) for d in (documents_ids or [])] or None,
        "copy_paste_allowed": copy_paste_allowed,
        "text_enabled": text_enabled,
        "audio_enabled": audio_enabled,
        "hints_enabled": hints_enabled,
        "show_images": show_images,
        "show_objectives": show_objectives,
        "show_problem_statement": show_problem_statement,
        "analyses_enabled": analyses_enabled,
        "strengths_enabled": strengths_enabled,
        "improvements_enabled": improvements_enabled,
        "problem_statement_enabled": problem_statement_enabled,
        "objectives_enabled": objectives_enabled,
        "video_enabled": video_enabled,
        "images_enabled": images_enabled,
        "questions_enabled": questions_enabled,
        "time_limit_seconds": time_limit,
        "negative": negative_time,
        "problem_statement_id": (
            str(problem_statements_ids[0]) if problem_statements_ids else None
        ),
        "objective_ids": [str(o) for o in (objectives_ids or [])] or None,
        "question_ids": [str(q) for q in (questions_ids or [])] or None,
        "option_ids": [str(o) for o in (options_ids or [])] or None,
        "image_ids": [str(i) for i in (images_ids or [])] or None,
        "video_ids": [str(v) for v in (videos_ids or [])] or None,
        "standard_group_ids": [str(s) for s in (standard_groups_ids or [])] or None,
        "standard_ids": [str(s) for s in (standards_ids or [])] or None,
        # Synthetic alias so hedged_search id_key can dedupe by chat_id.
        "id": str(chat_id),
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_chat",
            chat_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptChatResponse(id=attempt_chat_id)
