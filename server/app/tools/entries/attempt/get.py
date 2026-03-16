"""attempt/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt.types import GetAttemptResponse

MV_NAME = "attempt_mv"


async def get_attempts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptResponse]:
    """Get attempt entries by IDs from attempt_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT attempt_id, simulation_id, profile_id, user_persona_id,
               personas_id, cohort_id, department_id, practice,
               attempt_created_at, infinite_mode, num_chats, is_archived,
               scenario_ids, chat_entry_id, attempt_chat_id
        FROM {MV_NAME}
        WHERE attempt_id = ANY($1)
        """,
        ids,
    )

    return [
        GetAttemptResponse(
            attempt_id=r["attempt_id"],
            simulation_id=r["simulation_id"],
            profile_id=r["profile_id"],
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
