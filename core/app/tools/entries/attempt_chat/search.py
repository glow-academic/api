"""Attempt chat search — filtered/paginated query against attempt_chat_mv."""

from datetime import date
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "attempt_chat_mv"


async def search_attempt_chats(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    group_ids: list[UUID] | None = None,
    attempt_chat_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
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
    bypass_cache: bool = False,
) -> tuple[list[GetAttemptChatResponse], int]:
    """Search attempt_chat entries from attempt_chat_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

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
               standard_group_ids, standard_ids,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR TRUE)
          AND ($3::uuid[] IS NULL OR chat_id = ANY($3))
          AND ($4::uuid[] IS NULL OR profile_id = ANY($4))
          AND ($5::uuid[] IS NULL OR role_id = ANY($5))
          AND ($6::uuid[] IS NULL OR cohort_id = ANY($6))
          AND ($7::uuid[] IS NULL OR department_id = ANY($7))
          AND ($8::uuid[] IS NULL OR simulation_id = ANY($8))
          AND ($9::uuid[] IS NULL OR scenario_id = ANY($9))
          AND ($10::uuid[] IS NULL OR persona_ids && $10)
          AND ($11::uuid[] IS NULL OR rubric_id = ANY($11))
          AND ($12::text IS NULL OR attempt_type = $12)
          AND ($13::bool IS NULL OR is_archived = $13)
          AND ($14::date IS NULL OR attempt_date >= $14)
          AND ($15::date IS NULL OR attempt_date <= $15)
        ORDER BY chat_created_at {order}
        LIMIT $16 OFFSET $17
        """,
        attempt_ids,
        group_ids,
        attempt_chat_ids,
        profile_ids,
        role_ids,
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
        limit + offset + 1000,
        0,
    )

    total_count = rows[0]["total_count"] if rows else 0
    mv_dicts: list[dict] = []
    for r in rows:
        d = {k: v for k, v in dict(r).items() if k != "total_count"}
        # Synthetic alias keys so hedged_search can sort by created_at and
        # dedupe by chat_id.
        d["id"] = str(r["chat_id"])
        d["created_at"] = r["chat_created_at"]
        mv_dicts.append(d)

    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None
    attempt_chat_ids_str = (
        {str(c) for c in attempt_chat_ids} if attempt_chat_ids else None
    )
    profile_ids_str = {str(p) for p in profile_ids} if profile_ids else None
    role_ids_str = {str(r) for r in role_ids} if role_ids else None
    cohort_ids_str = {str(c) for c in cohort_ids} if cohort_ids else None
    department_ids_str = (
        {str(d) for d in department_ids} if department_ids else None
    )
    simulation_ids_str = (
        {str(s) for s in simulation_ids} if simulation_ids else None
    )
    scenario_ids_str = {str(s) for s in scenario_ids} if scenario_ids else None
    user_persona_ids_str = (
        {str(p) for p in user_persona_ids} if user_persona_ids else None
    )
    rubric_ids_str = {str(r) for r in rubric_ids} if rubric_ids else None

    def matches(row: dict) -> bool:
        # Cache rows lack many MV-derived fields (attempt_id, profile_id,
        # rubric_id, etc.). If a filter is set on a field the cache row
        # doesn't know, exclude it — the MV will catch up on next refresh.
        if attempt_ids_str is not None:
            v = row.get("attempt_id")
            if v is None or str(v) not in attempt_ids_str:
                return False
        if attempt_chat_ids_str is not None:
            v = row.get("chat_id")
            if v is None or str(v) not in attempt_chat_ids_str:
                return False
        if profile_ids_str is not None:
            v = row.get("profile_id")
            if v is None or str(v) not in profile_ids_str:
                return False
        if role_ids_str is not None:
            v = row.get("role_id")
            if v is None or str(v) not in role_ids_str:
                return False
        if cohort_ids_str is not None:
            v = row.get("cohort_id")
            if v is None or str(v) not in cohort_ids_str:
                return False
        if department_ids_str is not None:
            v = row.get("department_id")
            if v is None or str(v) not in department_ids_str:
                return False
        if simulation_ids_str is not None:
            v = row.get("simulation_id")
            if v is None or str(v) not in simulation_ids_str:
                return False
        if scenario_ids_str is not None:
            v = row.get("scenario_id")
            if v is None or str(v) not in scenario_ids_str:
                return False
        if user_persona_ids_str is not None:
            pids = row.get("persona_ids") or []
            if not any(str(p) in user_persona_ids_str for p in pids):
                return False
        if rubric_ids_str is not None:
            v = row.get("rubric_id")
            if v is None or str(v) not in rubric_ids_str:
                return False
        if attempt_type is not None and row.get("attempt_type") != attempt_type:
            return False
        if is_archived is not None and row.get("is_archived") != is_archived:
            return False
        # date_from/date_to filter attempt_date; cache rows lack it.
        if date_from is not None and row.get("attempt_date") is None:
            return False
        if date_to is not None and row.get("attempt_date") is None:
            return False
        return True

    from datetime import datetime as _dt

    def sort_key(row: dict) -> _dt:
        ts = row.get("chat_created_at") or row.get("created_at")
        if ts is None:
            return _dt.min
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    # hedged_search_with_total only sorts DESC; when caller asks for ASC, the
    # merge can't preserve order — bypass the cache in that case.
    effective_bypass = bypass_cache or order == "ASC"
    merged, total = await hedged_search_with_total(
        redis,
        "attempt_chat",
        mv_rows=mv_dicts,
        mv_total=total_count,
        matches_filter=matches,
        sort_key=sort_key,
        limit=limit,
        offset=offset,
        bypass_cache=effective_bypass,
    )
    items = [
        GetAttemptChatResponse.model_validate(
            {k: v for k, v in r.items() if k not in ("id", "created_at")}
        )
        for r in merged
    ]
    return (items, total)
