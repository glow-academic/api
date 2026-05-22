"""Attempt CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt.types import CreateAttemptResponse
from app.utils.cache.hedged_row import write_back_row


async def create_attempt(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    user_persona_id: UUID,
    profiles_id: UUID,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    infinite_mode: bool = False,
    num_chats: int = 1,
    practice: bool = False,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptResponse:
    """Create an attempt entry with profiles connection."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_entry (
            id, session_id, user_persona_id, name, description,
            infinite_mode, num_chats, practice, active, mcp, generated, created_at
        )
        VALUES (COALESCE($10, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, $9, true, COALESCE($11, NOW()))
        RETURNING id, created_at
        """,
        session_id,
        user_persona_id,
        name,
        description,
        infinite_mode,
        num_chats,
        practice,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create attempt entry")

    attempt_id = row["id"]
    actual_created_at = row["created_at"]

    # attempt_profiles_connection (INNER JOIN in attempt_mv — required)
    await conn.execute(
        """
        INSERT INTO attempt_profiles_connection (attempt_id, profiles_id, generated)
        VALUES ($1, $2, true)
        """,
        attempt_id,
        profiles_id,
    )

    # Cache-row superset: matches GetAttemptResponse / search response shape.
    # At create-time we know attempt_id, profile_id (from the junction we
    # just inserted), user_persona_id, infinite_mode, num_chats, and
    # attempt_created_at. Everything else is derived from child entries /
    # junctions that this function does NOT write:
    #   - simulation_id, cohort_id, department_id: from attempt_home_entry
    #     or attempt_practice_entry + home/practice_*_connection (not here)
    #   - role_id: from profiles_resource.role_id (lookup, not done here)
    #   - personas_id: from personas_personas_connection (not here)
    #   - practice (MV col): derived as `attempt_practice_entry exists` —
    #     at create-time the ape row hasn't been written, so False.
    #     NOTE: this is DIFFERENT from the `practice` param/column on
    #     attempt_entry; the MV `practice` is junction-derived.
    #   - is_archived / is_completed: child entries (archive / completion)
    #   - scenario_ids: derived from attempt_chat_bridge -> chat_scenarios
    #   - chat_entry_id / attempt_chat_id: from attempt_chat_bridge_entry
    # Child-entry creates (attempt_home, attempt_practice, attempt_archive,
    # attempt_completion, attempt_chat bridge) MUST invalidate_row("attempt",
    # attempt_id) so the next read falls through to the MV.
    fresh_row = {
        "attempt_id": str(attempt_id),
        "simulation_id": None,
        "profile_id": str(profiles_id),
        "role_id": None,
        "user_persona_id": str(user_persona_id),
        "personas_id": None,
        "cohort_id": None,
        "department_id": None,
        "practice": False,
        "attempt_created_at": actual_created_at.isoformat(),
        "infinite_mode": infinite_mode,
        "num_chats": num_chats,
        "is_archived": False,
        "is_completed": False,
        "scenario_ids": [],
        "chat_entry_id": None,
        "attempt_chat_id": None,
        # extra: id mirror so hedged_search id_key="attempt_id" works
        "id": str(attempt_id),
    }
    await write_back_row(
        redis,
        "attempt",
        attempt_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAttemptResponse(id=attempt_id)
