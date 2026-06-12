"""attempt_chat session lookup — bridge-independent ownership resolution.

The ``attempt_chat_mv`` derives ``profile_id`` through the bridge → attempt →
session chain, so a freshly-created-but-NOT-yet-bridged attempt_chat (the real
"advance to next chat" flow — see ``test_chat_create_route_bridges_chat_into_attempt``)
carries no MV ``profile_id``. The raw ``attempt_chat_entry`` row, however, always
records the ``session_id`` of the session that created it — the bridge-independent
owner signal. This getter exposes that ``session_id`` so an ownership gate can
resolve ``attempt_chat → session → profile`` regardless of bridge state (mirrors
``get_file`` exposing ``files_entry.session_id`` for ``enforce_upload_owner``).
"""

from uuid import UUID

import asyncpg  # type: ignore


async def get_attempt_chat_session_id(
    conn: asyncpg.Connection,
    attempt_chat_id: UUID,
) -> UUID | None:
    """Return the ``session_id`` that created an attempt_chat (or ``None``)."""
    row = await conn.fetchrow(
        """
        SELECT session_id
        FROM attempt_chat_entry
        WHERE id = $1 AND active = true
        """,
        attempt_chat_id,
    )
    return row["session_id"] if row else None
