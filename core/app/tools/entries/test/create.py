"""Test CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.test.types import CreateTestResponse


async def create_test(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    call_id: UUID | None = None,
    profiles_id: UUID | None = None,
    name: str = "",
    description: str = "",
    num_invocations: int = 0,
    infinite_mode: bool = False,
    is_dynamic: bool = True,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestResponse:
    """Create a test entry with profiles connection."""
    test_id = await conn.fetchval(
        """
        INSERT INTO test_entry (
            id, call_id, name, description, num_invocations,
            infinite_mode, is_dynamic, active, mcp, generated
        )
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, true)
        RETURNING id
        """,
        call_id,
        name,
        description,
        num_invocations,
        infinite_mode,
        is_dynamic,
        not soft,
        mcp,
        id,
    )

    if test_id is None:
        raise ValueError("Failed to create test entry")

    # test_profiles_connection (LEFT JOIN in test_mv — optional)
    if profiles_id is not None:
        await conn.execute(
            """
            INSERT INTO test_profiles_connection (attempt_id, profiles_id, generated)
            VALUES ($1, $2, true)
            """,
            test_id,
            profiles_id,
        )

    return CreateTestResponse(id=test_id)
