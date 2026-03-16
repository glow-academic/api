"""Attempt chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_chat.types import CreateAttemptChatResponse


async def create_attempt_chat(
    conn: asyncpg.Connection,
    call_id: UUID,
    group_id: UUID,
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
    replacements_enabled: bool = False,
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
) -> CreateAttemptChatResponse:
    """Create an attempt_chat entry with optional connection tables."""
    attempt_chat_id = await conn.fetchval(
        """
        INSERT INTO attempt_chat_entry (
            id, call_id, group_id, chat_id, title, "position", time_limit,
            negative_time, audio_enabled, text_enabled, hints_enabled,
            copy_paste_allowed, show_images, show_objectives,
            show_problem_statement, analyses_enabled, improvements_enabled,
            replacements_enabled, strengths_enabled, use_custom, use_previous,
            problem_statement_enabled, objectives_enabled, video_enabled,
            images_enabled, questions_enabled,
            assistant_persona_ids, active, mcp, generated
        )
        VALUES (
            COALESCE($29, uuidv7()), $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10,
            $11, $12, $13,
            $14, $15, $16,
            $17, $18, $19, $20,
            $21, $22, $23,
            $24, $25,
            $26, $27, $28, true
        )
        RETURNING id
        """,
        call_id,
        group_id,
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
        replacements_enabled,
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
    )

    if attempt_chat_id is None:
        raise ValueError("Failed to create attempt_chat entry")

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

    return CreateAttemptChatResponse(id=attempt_chat_id)
