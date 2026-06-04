"""Setting artifact DELETE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.delete.delete_artifact import delete_artifacts
from app.infra.junctions import delete_junctions_by_owner
from app.tools.artifacts.setting.types import DeleteSettingsResponse

TABLE = "setting_artifact"

# Junctions whose ``setting_id`` FK was created WITHOUT ``ON DELETE CASCADE``
# (NO ACTION default). A hard DELETE of a populated setting_artifact would
# fail with a foreign_key_violation unless these rows are cleared first.
NON_CASCADING_JUNCTIONS = [
    "setting_logins_junction",
    "setting_mcp_junction",
    "setting_systems_junction",
]


async def delete_settings(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    soft: bool = False,
) -> DeleteSettingsResponse:
    """Delete setting artifacts by IDs.

    soft=False (default): hard DELETE — junctions cascade. Non-cascading
    junctions (``setting_logins/mcp/systems``) are cleared explicitly first
    so the delete does not fail with a foreign_key_violation.
    soft=True: sets active=false — data is recoverable (junctions untouched).
    """
    if not soft:
        await delete_junctions_by_owner(
            conn,
            tables=NON_CASCADING_JUNCTIONS,
            owner_col="setting_id",
            owner_ids=ids,
        )
    deleted_ids = await delete_artifacts(conn, table=TABLE, ids=ids, soft=soft)
    return DeleteSettingsResponse(deleted_ids=deleted_ids)
