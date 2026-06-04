"""Home chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.home_chat.types import CreateHomeChatResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_home_chat(
    conn: asyncpg.Connection,
    redis: Redis,
    home_id: UUID,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateHomeChatResponse:
    """Create a home_chat_entry bridge row."""
    row = await conn.fetchrow(
        """
        INSERT INTO home_chat_entry (id, home_id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at, active, mcp
        """,
        home_id,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create home_chat_entry")
    row_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(row_id),
        "home_id": str(home_id),
        "chat_id": str(chat_id),
        "created_at": created_at.isoformat(),
        "active": row["active"],
        "generated": True,
        "mcp": row["mcp"],
        "session_id": str(session_id),
    }
    await write_back_row(
        redis,
        "home_chat",
        row_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    # The ``home`` read-back row is seeded by ``create_home`` with empty
    # ``chat_ids``/``scenario_ids`` (both are sourced from ``home_chat_entry``
    # joins in ``home_mv`` — the latter via ``chat_scenarios_connection``).
    # Linking a chat here leaves that row stale, so a cached ``get_homes``
    # read would surface an empty ``chat_ids``/``scenario_ids`` until the
    # row's TTL lapsed. Invalidate it so the next ``get_homes`` rehydrates
    # from ``home_mv``. Mirrors the #163 groups/group_names fix.
    await invalidate_row(redis, "home", home_id)

    return CreateHomeChatResponse(id=row_id)
