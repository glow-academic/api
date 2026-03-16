"""Department artifact DELETE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.delete.delete_artifact import delete_artifacts
from app.tools.artifacts.department.types import DeleteDepartmentsResponse

TABLE = "department_artifact"


async def delete_departments(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    soft: bool = False,
) -> DeleteDepartmentsResponse:
    """Delete department artifacts by IDs.

    soft=False (default): hard DELETE — junctions cascade.
    soft=True: sets active=false — data is recoverable.
    """
    deleted_ids = await delete_artifacts(conn, table=TABLE, ids=ids, soft=soft)
    return DeleteDepartmentsResponse(deleted_ids=deleted_ids)
