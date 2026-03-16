"""Test get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.test.types import GetTestResponse

MV_NAME = "test_mv"


async def get_tests(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetTestResponse]:
    """Fetch test entries by IDs from the MV."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT
            test_id, eval_id, profile_id, department_ids,
            test_name, test_description,
            num_invocations, infinite_mode, is_dynamic, archived, test_created_at
        FROM {MV_NAME}
        WHERE test_id = ANY($1)
        """,
        ids,
    )

    return [
        GetTestResponse(
            test_id=r["test_id"],
            eval_id=r["eval_id"],
            profile_id=r["profile_id"],
            department_ids=r["department_ids"],
            test_name=r["test_name"],
            test_description=r["test_description"],
            num_invocations=r["num_invocations"],
            infinite_mode=r["infinite_mode"],
            is_dynamic=r["is_dynamic"],
            archived=r["archived"],
            test_created_at=r["test_created_at"],
        )
        for r in rows
    ]
