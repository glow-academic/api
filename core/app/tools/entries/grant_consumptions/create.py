"""Grant consumptions CREATE — insert into grant_consumptions_entry."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.grant_consumptions.types import (
    CreateGrantConsumptionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_grant_consumption(
    conn: asyncpg.Connection,
    redis: Redis,
    grant_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateGrantConsumptionResponse | None:
    """Atomically consume a grant exactly once.

    A grant is single-use: at most one *active* consumption may exist per
    ``grant_id``. The partial-unique index
    ``grant_consumptions_entry_grant_uidx (grant_id) WHERE active`` is the hard
    backstop, and this INSERT uses ``ON CONFLICT DO NOTHING`` so a concurrent
    second consumer (the race-loser) writes 0 rows.

    Returns the ``CreateGrantConsumptionResponse`` on success, or ``None`` when
    the grant was already consumed (an active consumption exists / a concurrent
    committer won the race). Callers gating a single-use side effect (e.g. the
    emulation login-consume in ``default_idp``) MUST reject on ``None`` so an
    impersonation grant cannot be replayed.

    ``soft=True`` (inactive) consumptions are exempt from the index predicate
    (``WHERE active``) and never conflict.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO grant_consumptions_entry (id, grant_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        ON CONFLICT (grant_id) WHERE active = true DO NOTHING
        RETURNING id, created_at
        """,
        grant_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        # ON CONFLICT DO NOTHING wrote no row: the grant already has an active
        # consumption — already consumed (race-loser). Not an error.
        return None

    consumption_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(consumption_id),
        "grant_id": str(grant_id),
        "created_at": created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
    }
    await write_back_row(
        redis,
        "grant_consumptions",
        consumption_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateGrantConsumptionResponse(id=consumption_id)
