"""Test CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.test.types import CreateTestResponse
from app.utils.cache.hedged_row import write_back_row


async def create_test(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO test_entry (
            id, call_id, name, description, num_invocations,
            infinite_mode, is_dynamic, active, mcp, generated
        )
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, true)
        RETURNING id, created_at
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

    if row is None:
        raise ValueError("Failed to create test entry")

    test_id = row["id"]
    created_at = row["created_at"]

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

    # Write-back cache row matching test_mv GET response shape. Junction-joined
    # fields (eval_id, department_ids) and aggregate flags (archived) default
    # at create-time; the MV catches up on refresh.
    fresh_row = {
        "test_id": str(test_id),
        "call_id": str(call_id) if call_id else None,
        "eval_id": None,
        "profile_id": str(profiles_id) if profiles_id else None,
        "department_ids": [],
        "test_name": name,
        "test_description": description,
        "num_invocations": num_invocations,
        "infinite_mode": infinite_mode,
        "is_dynamic": is_dynamic,
        "archived": False,
        "test_created_at": created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "test",
        test_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestResponse(id=test_id)
