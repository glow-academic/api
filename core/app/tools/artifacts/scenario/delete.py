"""Scenario artifact DELETE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.delete.delete_artifact import delete_artifacts
from app.tools.artifacts.scenario.types import DeleteScenariosResponse

TABLE = "scenario_artifact"


async def delete_scenarios(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    soft: bool = False,
) -> DeleteScenariosResponse:
    """Delete scenario artifacts by IDs.

    soft=False (default): hard DELETE — junctions cascade.
    soft=True: sets active=false — data is recoverable.
    """
    deleted_ids = await delete_artifacts(conn, table=TABLE, ids=ids, soft=soft)
    return DeleteScenariosResponse(deleted_ids=deleted_ids)
