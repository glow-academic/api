"""Cohort artifact DELETE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.delete.delete_artifact import delete_artifacts
from app.tools.artifacts.cohort.types import DeleteCohortsResponse

TABLE = "cohort_artifact"


async def delete_cohorts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    soft: bool = False,
) -> DeleteCohortsResponse:
    """Delete cohort artifacts by IDs.

    soft=False (default): hard DELETE — junctions cascade.
    soft=True: sets active=false — data is recoverable.
    """
    deleted_ids = await delete_artifacts(conn, table=TABLE, ids=ids, soft=soft)
    return DeleteCohortsResponse(deleted_ids=deleted_ids)
