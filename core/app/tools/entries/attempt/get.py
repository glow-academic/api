"""attempt/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt.types import GetAttemptResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_mv"


async def get_attempts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptResponse]:
    """Get attempt entries by IDs from attempt_mv.

    Hedged: try the per-id write-back cache first for each id; fall through
    to the MV for any cache misses. Returns rows in MV insertion order
    followed by cached rows (callers historically don't rely on input
    ordering — both ``get_attempt`` (single) and bulk callers iterate the
    full list).
    """
    if not ids:
        return []

    cached_responses: list[GetAttemptResponse] = []
    missing_ids: list[UUID] = []

    if not bypass_cache:
        for attempt_id in ids:
            cached = await read_back_row(redis, "attempt", attempt_id)
            if cached is not None:
                try:
                    cached_responses.append(GetAttemptResponse.model_validate(cached))
                    continue
                except Exception:
                    # Malformed cache row — fall through to MV for this id.
                    pass
            missing_ids.append(attempt_id)
    else:
        missing_ids = list(ids)

    if not missing_ids:
        return cached_responses

    rows = await conn.fetch(
        f"""
        SELECT attempt_id, simulation_id, profile_id, role_id, user_persona_id,
               personas_id, cohort_id, department_id, practice,
               attempt_created_at, infinite_mode, num_chats, is_archived,
               scenario_ids, chat_entry_id, attempt_chat_id
        FROM {MV_NAME}
        WHERE attempt_id = ANY($1)
        """,
        missing_ids,
    )

    db_responses = [
        GetAttemptResponse(
            attempt_id=r["attempt_id"],
            simulation_id=r["simulation_id"],
            profile_id=r["profile_id"],
            role_id=r["role_id"],
            user_persona_id=r["user_persona_id"],
            personas_id=r["personas_id"],
            cohort_id=r["cohort_id"],
            department_id=r["department_id"],
            practice=r["practice"],
            attempt_created_at=r["attempt_created_at"],
            infinite_mode=r["infinite_mode"],
            num_chats=r["num_chats"],
            is_archived=r["is_archived"],
            scenario_ids=r["scenario_ids"] or [],
            chat_entry_id=r["chat_entry_id"],
            attempt_chat_id=r["attempt_chat_id"],
        )
        for r in rows
    ]

    return cached_responses + db_responses
