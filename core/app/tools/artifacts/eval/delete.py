"""Eval artifact DELETE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.delete.delete_artifact import delete_artifacts
from app.infra.junctions import delete_junctions_by_owner
from app.tools.artifacts.eval.types import DeleteEvalsResponse

TABLE = "eval_artifact"

# Junctions whose ``eval_id`` FK was created WITHOUT ``ON DELETE CASCADE``
# (NO ACTION default). A hard DELETE of a populated eval_artifact would fail
# with a foreign_key_violation unless these rows are cleared first.
NON_CASCADING_JUNCTIONS = [
    "eval_model_flags_junction",
    "eval_model_positions_junction",
    "eval_model_rubrics_junction",
]


async def delete_evals(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    soft: bool = False,
) -> DeleteEvalsResponse:
    """Delete eval artifacts by IDs.

    soft=False (default): hard DELETE — junctions cascade. Non-cascading
    junctions (``eval_model_*``) are cleared explicitly first so the delete
    does not fail with a foreign_key_violation.
    soft=True: sets active=false — data is recoverable (junctions untouched).
    """
    if not soft:
        await delete_junctions_by_owner(
            conn,
            tables=NON_CASCADING_JUNCTIONS,
            owner_col="eval_id",
            owner_ids=ids,
        )
    deleted_ids = await delete_artifacts(conn, table=TABLE, ids=ids, soft=soft)
    return DeleteEvalsResponse(deleted_ids=deleted_ids)
