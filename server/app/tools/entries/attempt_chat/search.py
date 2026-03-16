"""Attempt chat search — filtered/paginated query against attempt_chat_mv."""

from datetime import date
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_chat.types import GetAttemptChatResponse

MV_NAME = "attempt_chat_mv"


async def search_attempt_chats(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID] | None = None,
    group_ids: list[UUID] | None = None,
    attempt_chat_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    user_persona_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    attempt_type: str | None = None,
    is_archived: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> tuple[list[GetAttemptChatResponse], int]:
    """Search attempt_chat entries from attempt_chat_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

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
               standard_group_ids, standard_ids,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR group_id = ANY($2))
          AND ($3::uuid[] IS NULL OR chat_id = ANY($3))
          AND ($4::uuid[] IS NULL OR profile_id = ANY($4))
          AND ($5::uuid[] IS NULL OR cohort_id = ANY($5))
          AND ($6::uuid[] IS NULL OR department_id = ANY($6))
          AND ($7::uuid[] IS NULL OR simulation_id = ANY($7))
          AND ($8::uuid[] IS NULL OR scenario_id = ANY($8))
          AND ($9::uuid[] IS NULL OR persona_ids && $9)
          AND ($10::uuid[] IS NULL OR rubric_id = ANY($10))
          AND ($11::text IS NULL OR attempt_type = $11)
          AND ($12::bool IS NULL OR is_archived = $12)
          AND ($13::date IS NULL OR attempt_date >= $13)
          AND ($14::date IS NULL OR attempt_date <= $14)
        ORDER BY chat_created_at {order}
        LIMIT $15 OFFSET $16
        """,
        attempt_ids,
        group_ids,
        attempt_chat_ids,
        profile_ids,
        cohort_ids,
        department_ids,
        simulation_ids,
        scenario_ids,
        user_persona_ids,
        rubric_ids,
        attempt_type,
        is_archived,
        date_from,
        date_to,
        limit,
        offset,
    )

    total_count = rows[0]["total_count"] if rows else 0
    items = [
        GetAttemptChatResponse(
            **{k: v for k, v in dict(r).items() if k != "total_count"}
        )
        for r in rows
    ]
    return (items, total_count)
