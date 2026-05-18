"""Health CREATE — insert entry."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.health.types import CreateHealthResponse
from app.tools.entries.sessions.create import create_session


async def create_health(
    conn: asyncpg.Connection,
    service: str,
    ok: bool,
    latency_ms: float,
    id: UUID | None = None,
    ts: datetime | None = None,
    error: str = "",
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateHealthResponse:
    """Create a health entry."""
    if ts is None:
        ts = datetime.now(UTC)
    if session_id is None:
        session = await create_session(conn, mcp=mcp, soft=soft)
        session_id = session.id

    health_id = await conn.fetchval(
        """INSERT INTO health_entry (id, ts, service, ok, latency_ms, error, session_id, active, mcp, generated)
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, true) RETURNING id""",
        ts,
        service,
        ok,
        latency_ms,
        error,
        session_id,
        not soft,
        mcp,
        id,
    )

    if health_id is None:
        raise ValueError("Failed to create health entry")

    return CreateHealthResponse(id=health_id)
