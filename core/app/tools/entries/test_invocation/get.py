"""test_invocation/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_invocation.types import (
    GetTestInvocationResponse,
)

MV_NAME = "test_invocation_mv"


async def get_test_invocations(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetTestInvocationResponse]:
    """Fetch test_invocation entries by IDs from the MV."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT
            invocation_id, test_id, group_id, invocation_created_at,
            invocation_title, use_custom, "position", invocation_completed,
            grade_id, grade_score, grade_passed, grade_time_taken,
            rubric_id, agent_ids, quality_id, department_ids,
            run_agent_ids, group_agent_ids, voice_id,
            temperature_level_id, reasoning_level_id, modality_ids
        FROM {source}
        WHERE invocation_id = ANY($1)
        """,
        ids,
    )

    return [
        GetTestInvocationResponse(
            invocation_id=r["invocation_id"],
            test_id=r["test_id"],
            group_id=r["group_id"],
            invocation_created_at=r["invocation_created_at"],
            invocation_title=r["invocation_title"],
            use_custom=r["use_custom"],
            position=r["position"],
            invocation_completed=r["invocation_completed"],
            grade_id=r["grade_id"],
            grade_score=r["grade_score"],
            grade_passed=r["grade_passed"],
            grade_time_taken=r["grade_time_taken"],
            rubric_id=r["rubric_id"],
            agent_ids=r["agent_ids"],
            quality_id=r["quality_id"],
            department_ids=r["department_ids"],
            run_agent_ids=r["run_agent_ids"],
            group_agent_ids=r["group_agent_ids"],
            voice_id=r["voice_id"],
            temperature_level_id=r["temperature_level_id"],
            reasoning_level_id=r["reasoning_level_id"],
            modality_ids=r["modality_ids"],
        )
        for r in rows
    ]
