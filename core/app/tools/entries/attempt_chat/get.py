"""attempt_chat/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_chat_mv"


async def get_attempt_chats(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptChatResponse]:
    """Get attempt_chat entries by IDs from attempt_chat_mv (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptChatResponse] = {}
    missing_ids: list[UUID] = list(ids)
    if not bypass_cache:
        missing_ids = []
        for cid in ids:
            cached = await read_back_row(redis, "attempt_chat", cid)
            if cached is not None:
                # Strip synthetic ``id``/``created_at`` aliases not on response.
                payload = {
                    k: v
                    for k, v in cached.items()
                    if k not in ("id", "created_at")
                }
                cached_results[str(cid)] = GetAttemptChatResponse.model_validate(payload)
            else:
                missing_ids.append(cid)

    if not missing_ids:
        return [cached_results[str(cid)] for cid in ids if str(cid) in cached_results]

    rows = await conn.fetch(
        f"""
        SELECT chat_id, attempt_id, chat_entry_id,
               profile_id, role_id, cohort_id, department_id, simulation_id,
               scenario_id, persona_ids, assistant_persona_ids, rubric_id,
               grade_score, grade_total_points, grade_pass_points,
               grade_passed, grade_time_taken,
               completed, attempt_number, chat_created_at, attempt_date,
               attempt_type, is_archived, infinite_mode, document_ids,
               copy_paste_allowed, text_enabled, audio_enabled,
               hints_enabled, show_images, show_objectives,
               show_problem_statement,
               analyses_enabled, strengths_enabled, improvements_enabled,
               problem_statement_enabled, objectives_enabled,
               video_enabled, images_enabled, questions_enabled,
               time_limit_seconds, negative,
               problem_statement_id, objective_ids, question_ids,
               option_ids, image_ids, video_ids,
               standard_group_ids, standard_ids
        FROM {MV_NAME}
        WHERE chat_id = ANY($1)
        """,
        missing_ids,
    )

    mv_results: dict[str, GetAttemptChatResponse] = {}
    for r in rows:
        mv_results[str(r["chat_id"])] = GetAttemptChatResponse(
            chat_id=r["chat_id"],
            attempt_id=r["attempt_id"],
            chat_entry_id=r["chat_entry_id"],
            group_id=None,
            profile_id=r["profile_id"],
            role_id=r["role_id"],
            cohort_id=r["cohort_id"],
            department_id=r["department_id"],
            simulation_id=r["simulation_id"],
            scenario_id=r["scenario_id"],
            persona_ids=r["persona_ids"],
            assistant_persona_ids=r["assistant_persona_ids"],
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
            analyses_enabled=r["analyses_enabled"],
            strengths_enabled=r["strengths_enabled"],
            improvements_enabled=r["improvements_enabled"],
            problem_statement_enabled=r["problem_statement_enabled"],
            objectives_enabled=r["objectives_enabled"],
            video_enabled=r["video_enabled"],
            images_enabled=r["images_enabled"],
            questions_enabled=r["questions_enabled"],
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

    out: list[GetAttemptChatResponse] = []
    for cid in ids:
        key = str(cid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
