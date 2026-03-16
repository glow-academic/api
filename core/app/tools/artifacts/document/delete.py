"""Document artifact DELETE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.delete.delete_artifact import delete_artifacts
from app.tools.artifacts.document.types import DeleteDocumentsResponse

TABLE = "document_artifact"


async def delete_documents(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    soft: bool = False,
) -> DeleteDocumentsResponse:
    """Delete document artifacts by IDs.

    soft=False (default): hard DELETE — junctions cascade.
    soft=True: sets active=false — data is recoverable.
    """
    deleted_ids = await delete_artifacts(conn, table=TABLE, ids=ids, soft=soft)
    return DeleteDocumentsResponse(deleted_ids=deleted_ids)
