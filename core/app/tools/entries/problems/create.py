"""Problems CREATE — insert into problems_entry with profile link."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.problems.types import CreateProblemResponse


async def create_problem(
    conn: asyncpg.Connection,
    session_id: UUID,
    call_id: UUID,
    type: str,
    id: UUID | None = None,
    message: str = "No message provided",
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateProblemResponse:
    """Create a problem entry and optionally link to a profile."""
    problem_id = await conn.fetchval(
        """
        INSERT INTO problems_entry (id, call_id, type, message, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2::public.feedback_type, $3, $4, $5, true)
        RETURNING id
        """,
        call_id,
        type,
        message,
        not soft,
        mcp,
        id,
    )

    if problem_id is None:
        raise ValueError("Failed to create problem entry")

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_problems_connection (profiles_id, problem_id)
            VALUES ($1, $2)
            """,
            profile_id,
            problem_id,
        )

    return CreateProblemResponse(id=problem_id)
