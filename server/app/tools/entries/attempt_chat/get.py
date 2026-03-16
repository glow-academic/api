"""attempt_chat/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_chat.types import GetAttemptChatResponse

MV_NAME = "attempt_chat_mv"


async def get_attempt_chats(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptChatResponse]:
    """Get attempt_chat entries by IDs from attempt_chat_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT chat_id, attempt_id, chat_entry_id, group_id,
               profile_id, cohort_id, department_id, simulation_id,
               scenario_id, persona_ids, rubric_id,
               grade_score, grade_total_points, grade_pass_points,
               grade_passed, grade_time_taken,
               completed, attempt_number, chat_created_at, attempt_date,
               attempt_type, is_archived, infinite_mode, document_ids,
               copy_paste_allowed, text_enabled, audio_enabled,
               hints_enabled, show_images, show_objectives,
               show_problem_statement, time_limit_seconds, negative,
               problem_statement_id, objective_ids, question_ids,
               option_ids, image_ids, video_ids,
               standard_group_ids, standard_ids
        FROM {MV_NAME}
        WHERE chat_id = ANY($1)
        """,
        ids,
    )

    return [
        GetAttemptChatResponse(
            chat_id=r["chat_id"],
            attempt_id=r["attempt_id"],
            chat_entry_id=r["chat_entry_id"],
            group_id=r["group_id"],
            profile_id=r["profile_id"],
            cohort_id=r["cohort_id"],
            department_id=r["department_id"],
            simulation_id=r["simulation_id"],
            scenario_id=r["scenario_id"],
            persona_ids=r["persona_ids"],
            rubric_id=r["rubric_id"],
            grade_score=r["grade_score"],
            grade_total_points=r["grade_total_points"],
            grade_pass_points=r["grade_pass_points"],
            grade_passed=r["grade_passed"],
            grade_time_taken=r["grade_time_taken"],
            completed=r["completed"],
            attempt_number=r["attempt_number"],
            chat_created_at=r["chat_created_at"],
            attempt_date=r["attempt_date"],
            attempt_type=r["attempt_type"],
            is_archived=r["is_archived"],
            infinite_mode=r["infinite_mode"],
            document_ids=r["document_ids"],
            copy_paste_allowed=r["copy_paste_allowed"],
            text_enabled=r["text_enabled"],
            audio_enabled=r["audio_enabled"],
            hints_enabled=r["hints_enabled"],
            show_images=r["show_images"],
            show_objectives=r["show_objectives"],
            show_problem_statement=r["show_problem_statement"],
            time_limit_seconds=r["time_limit_seconds"],
            negative=r["negative"],
            problem_statement_id=r["problem_statement_id"],
            objective_ids=r["objective_ids"],
            question_ids=r["question_ids"],
            option_ids=r["option_ids"],
            image_ids=r["image_ids"],
            video_ids=r["video_ids"],
            standard_group_ids=r["standard_group_ids"],
            standard_ids=r["standard_ids"],
        )
        for r in rows
    ]
