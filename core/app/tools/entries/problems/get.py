"""Problems GET — batch get from problems_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.problems.types import GetProblemResponse

MV_NAME = "problems_mv"


async def get_problems(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetProblemResponse]:
    """Get problems by IDs from problems_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
    source_alias = "mv" if bypass_mv else "p"
    from_source = source if bypass_mv else f"{source} {source_alias}"

    rows = await conn.fetch(
        f"""
        SELECT {source_alias}.problem_id, {source_alias}.profile_id, c.session_id, {source_alias}.type, {source_alias}.message, {source_alias}.resolved, {source_alias}.created_at, {source_alias}.active, {source_alias}.mcp, {source_alias}.generated
        FROM {from_source}
        JOIN problems_entry pe ON pe.id = {source_alias}.problem_id
        LEFT JOIN calls_entry c ON c.id = pe.call_id
        WHERE {source_alias}.problem_id = ANY($1)
        """,
        ids,
    )

    return [
        GetProblemResponse(
            id=r["problem_id"],
            profile_id=r["profile_id"],
            session_id=r["session_id"],
            type=r["type"],
            message=r["message"],
            resolved=r["resolved"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
