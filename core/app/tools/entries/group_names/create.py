"""Group names CREATE — append a new name entry for a group."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.group_names.types import CreateGroupNameResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_group_name(
    conn: asyncpg.Connection,
    redis: Redis,
    group_id: UUID,
    name: str,
    session_id: UUID,
    id: UUID | None = None,
    generated: bool = False,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateGroupNameResponse:
    """Create a group_names entry (append-only).

    Lifecycle:
      - ``soft=True``: write with ``active=False`` (dormant). Hidden from
        ``group_names_mv`` (which filters active=true), so the displayed
        title is unchanged until acked.
      - ``soft=False``: write with ``active=True`` (immediate).
      - ``id`` provided + already-existing dormant row (UPSERT): promote
        ``active`` to the new value via ``ON CONFLICT (id) DO UPDATE``.
        Lets the ack flow flip a dormant rename to active without
        re-rolling the row id.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO group_names_entry
                (id, group_id, name, session_id, generated, mcp, active, created_at)
        VALUES (COALESCE($1, uuidv7()), $2, $3, $4, $5, $6, $7, COALESCE($8, NOW()))
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at
        """,
        id,
        group_id,
        name,
        session_id,
        generated,
        mcp,
        not soft,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create group_names entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    # Cache key = group_id (MV is DISTINCT ON group_id; GET is keyed by group_id).
    # Only cache active rows — dormant (soft) rows are hidden from the MV.
    if not soft:
        fresh_row = {
            "id": str(entry_id),
            "group_id": str(group_id),
            "name": name,
            "created_at": actual_created_at.isoformat(),
            "generated": generated,
            "mcp": mcp,
        }
        await write_back_row(
            redis,
            "group_names",
            group_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )
    else:
        # Dormant write: previous cached active row may now be stale if this
        # upsert deactivated an existing active row. Best-effort invalidate.
        await invalidate_row(redis, "group_names", group_id)

    # The ``groups`` read-back row is seeded by ``create_group`` with an empty
    # ``name`` (the name is owned by this separate primitive). Naming a group
    # leaves that row stale, so any cached ``get_groups`` read — e.g. the
    # pricing export's ``group`` column — would surface a blank name until the
    # row's TTL lapsed. Invalidate it so the next ``get_groups`` rehydrates the
    # name from groups_mv. (Active or dormant: the displayed name may change.)
    await invalidate_row(redis, "groups", group_id)

    return CreateGroupNameResponse(id=entry_id)
