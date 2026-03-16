"""attempt/search — filtered/paginated query against attempt_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt.types import GetAttemptResponse

MV_NAME = "attempt_mv"


async def search_attempts(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    practice: bool | None = None,
    is_archived: bool | None = None,
    infinite_mode: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> tuple[list[GetAttemptResponse], int]:
    """Search attempt entries from attempt_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order == "asc" else "DESC"
    rows = await conn.fetch(
        f"""
        SELECT attempt_id, simulation_id, profile_id, user_persona_id,
               personas_id, cohort_id, department_id, practice,
               attempt_created_at, infinite_mode, num_chats, is_archived,
               scenario_ids, chat_entry_id, attempt_chat_id,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR simulation_id = ANY($2))
          AND ($3::uuid[] IS NULL OR profile_id = ANY($3))
          AND ($4::uuid[] IS NULL OR cohort_id = ANY($4))
          AND ($5::uuid[] IS NULL OR department_id = ANY($5))
          AND ($6::uuid[] IS NULL OR scenario_ids && $6)
          AND ($7::boolean IS NULL OR practice = $7)
          AND ($8::boolean IS NULL OR is_archived = $8)
          AND ($9::boolean IS NULL OR infinite_mode = $9)
          AND ($10::timestamptz IS NULL OR attempt_created_at >= $10)
          AND ($11::timestamptz IS NULL OR attempt_created_at <= $11)
        ORDER BY attempt_created_at {order}
        LIMIT $12 OFFSET $13
        """,
        attempt_ids,
        simulation_ids,
        profile_ids,
        cohort_ids,
        department_ids,
        scenario_ids,
        practice,
        is_archived,
        infinite_mode,
        date_from,
        date_to,
        limit,
        offset,
    )

    total_count = rows[0]["total_count"] if rows else 0
    items = [
        GetAttemptResponse(**{k: v for k, v in dict(r).items() if k != "total_count"})
        for r in rows
    ]
    return (items, total_count)
