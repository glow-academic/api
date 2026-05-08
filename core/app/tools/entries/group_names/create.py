"""Group names CREATE — append a new name entry for a group."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.group_names.types import CreateGroupNameResponse


async def create_group_name(
    conn: asyncpg.Connection,
    group_id: UUID,
    name: str,
    session_id: UUID,
    id: UUID | None = None,
    generated: bool = False,
    mcp: bool = False,
    soft: bool = False,
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
    entry_id = await conn.fetchval(
        """
        INSERT INTO group_names_entry
                (id, group_id, name, session_id, generated, mcp, active)
        VALUES (COALESCE($1, uuidv7()), $2, $3, $4, $5, $6, $7)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        id,
        group_id,
        name,
        session_id,
        generated,
        mcp,
        not soft,
    )

    if entry_id is None:
        raise ValueError("Failed to create group_names entry")

    return CreateGroupNameResponse(id=entry_id)
