"""Problem Statements CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.problem_statements.get import get_problem_statements
from app.tools.resources.problem_statements.types import (
    GetProblemStatementResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_problem_statement(
    conn: asyncpg.Connection,
    name: str,
    problem_statement: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetProblemStatementResponse:
    """Create a problem statement resource."""
    problem_statement_id = await conn.fetchval(
        """
        INSERT INTO problem_statements_resource (id, name, problem_statement, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
    """,
        name,
        problem_statement,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "problem_statements"], redis=redis)
    items = await get_problem_statements(
        conn, [problem_statement_id], redis, bypass_cache=True
    )
    return items[0]
