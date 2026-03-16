"""Chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.chat.types import CreateChatResponse


async def create_chat(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    scenario_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    position: int = 0,
    mcp: bool = False,
    soft: bool = False,
    # ── Chat-level scalar columns ──
    name: str = "",
    description: str = "",
    time_limit: int | None = None,
    negative_time: bool = False,
    # ── 13 flag booleans ──
    audio_enabled: bool = True,
    text_enabled: bool = True,
    hints_enabled: bool = True,
    copy_paste_allowed: bool = True,
    show_images: bool = True,
    show_objectives: bool = True,
    show_problem_statement: bool = True,
    analyses_enabled: bool = True,
    improvements_enabled: bool = True,
    replacements_enabled: bool = True,
    strengths_enabled: bool = True,
    use_custom: bool = False,
    use_previous: bool = False,
    # ── 5 content-enabled flags ──
    problem_statement_enabled: bool = False,
    objectives_enabled: bool = False,
    video_enabled: bool = False,
    images_enabled: bool = False,
    questions_enabled: bool = False,
    # ── 11 generate flags ──
    generate_problem_statements: bool = False,
    generate_objectives: bool = False,
    generate_videos: bool = False,
    generate_images: bool = False,
    generate_questions: bool = False,
    generate_personas: bool = False,
    generate_documents: bool = False,
    generate_options: bool = False,
    generate_parameter_fields: bool = False,
    generate_names: bool = False,
    generate_descriptions: bool = False,
    # ── Connection table IDs ──
    rubric_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    problem_statement_ids: list[UUID] | None = None,
    objective_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
    standard_ids: list[UUID] | None = None,
) -> CreateChatResponse:
    """Create a chat entry with optional connection tables."""
    chat_id = await conn.fetchval(
        """
        INSERT INTO chat_entry (
            id, session_id, "position", active, mcp, generated,
            name, description, time_limit, negative_time,
            audio_enabled, text_enabled, hints_enabled,
            copy_paste_allowed, show_images, show_objectives,
            show_problem_statement, analyses_enabled,
            improvements_enabled, replacements_enabled,
            strengths_enabled, use_custom, use_previous,
            problem_statement_enabled, objectives_enabled,
            video_enabled, images_enabled, questions_enabled,
            generate_problem_statements, generate_objectives,
            generate_videos, generate_images, generate_questions,
            generate_personas, generate_documents, generate_options,
            generate_parameter_fields, generate_names,
            generate_descriptions
        )
        VALUES (
            COALESCE($38, uuidv7()), $1, $2, $3, $4, true,
            $5, $6, $7, $8,
            $9, $10, $11,
            $12, $13, $14,
            $15, $16,
            $17, $18,
            $19, $20, $21,
            $22, $23,
            $24, $25, $26,
            $27, $28,
            $29, $30, $31,
            $32, $33, $34,
            $35, $36,
            $37
        )
        RETURNING id
        """,
        session_id,
        position,
        not soft,
        mcp,
        name,
        description,
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
        generate_problem_statements,
        generate_objectives,
        generate_videos,
        generate_images,
        generate_questions,
        generate_personas,
        generate_documents,
        generate_options,
        generate_parameter_fields,
        generate_names,
        generate_descriptions,
        id,
    )

    if chat_id is None:
        raise ValueError("Failed to create chat entry")

    # ── Connection tables ──
    for scenario_id in scenario_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_scenarios_connection (chat_id, scenarios_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            scenario_id,
        )

    for department_id in department_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_departments_connection (chat_id, departments_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            department_id,
        )

    for rubric_id in rubric_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_rubrics_connection (chat_id, rubrics_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            rubric_id,
        )

    for sf_id in scenario_flag_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_scenario_flags_connection (chat_id, scenario_flags_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            sf_id,
        )

    for sp_id in scenario_position_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_scenario_positions_connection (chat_id, scenario_positions_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            sp_id,
        )

    for st_id in scenario_time_limit_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_scenario_time_limits_connection (chat_id, scenario_time_limits_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            st_id,
        )

    for p_id in persona_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_personas_connection (chat_id, personas_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            p_id,
        )

    for d_id in document_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_documents_connection (chat_id, documents_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            d_id,
        )

    for i_id in image_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_images_connection (chat_id, images_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            i_id,
        )

    for v_id in video_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_videos_connection (chat_id, videos_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            v_id,
        )

    for q_id in question_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_questions_connection (chat_id, questions_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            q_id,
        )

    for o_id in option_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_options_connection (chat_id, options_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            o_id,
        )

    for ps_id in problem_statement_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_problem_statements_connection (chat_id, problem_statements_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            ps_id,
        )

    for obj_id in objective_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_objectives_connection (chat_id, objectives_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            obj_id,
        )

    for pf_id in parameter_field_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_parameter_fields_connection (chat_id, parameter_fields_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            pf_id,
        )

    for sg_id in standard_group_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_standard_groups_connection (chat_id, standard_groups_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            sg_id,
        )

    for s_id in standard_ids or []:
        await conn.execute(
            """
            INSERT INTO chat_standards_connection (chat_id, standards_id, generated)
            VALUES ($1, $2, true)
            """,
            chat_id,
            s_id,
        )

    return CreateChatResponse(id=chat_id)
